import datetime
import httpx
from langgraph.graph import StateGraph, START, END
from app.state import ShipmentState

ERP_URL = "http://localhost:8001"
RISK_URL = "http://localhost:8003"
FREIGHT_URL = "http://localhost:8002"

# ---------------------------------------------------------------------------
# Phase 4 — Composite scoring weights
# These are named constants so they can be tuned/explained live during a demo.
# All three weights must sum to 1.0.
#   WEIGHT_COST         — penalises more expensive routes
#   WEIGHT_TIME         — penalises slower routes (transit days)
#   WEIGHT_RISK         — penalises routes with higher operational risk
#
# Current defaults reflect a supply-chain-SLA-first posture: risk is weighted
# highest because an unreliable route can cause both delay AND cost overruns,
# cost comes second (freight premium is real money), and time is weighted
# lowest because penalty_exposure (below) already captures the SLA impact of
# slowness — we don't double-count time twice.
# ---------------------------------------------------------------------------
WEIGHT_COST = 0.30
WEIGHT_TIME = 0.20
WEIGHT_RISK = 0.50

# ---------------------------------------------------------------------------
# Risk keyword mapping  (qualitative → numeric, 0.0 = low, 1.0 = very high)
#
# SIMPLIFICATION NOTE: This is a keyword-based heuristic, not an ML model.
# It is intentionally explicit and auditable so the mapping can be explained
# during a live demo.  Keywords are checked in order from HIGH → LOW so that
# the most severe signal wins if multiple keywords appear in the same note.
# ---------------------------------------------------------------------------
_RISK_KEYWORD_MAP = [
    # (substring_to_match_case_insensitive, numeric_risk_value)
    ("dangerous goods",          1.0),   # DG-certified cargo — highest operational risk
    ("very high cost",           0.85),  # proxy: cost pressure often tracks risk exposure
    ("higher congestion",        0.75),  # port congestion = delay AND damage risk
    ("wait out",                 0.65),  # weather-hold at origin — moderate uncertainty
    ("lowest cost but highest",  0.70),  # explicit "highest delay" language
    ("avoids",                   0.30),  # route explicitly designed to avoid hazard
    ("proven reliability",       0.20),  # carrier's own confidence claim
    ("bypassing",                0.25),  # complete avoidance of disruption zone
    ("expedited",                0.40),  # faster but operationally complex
    ("fallback",                 0.50),  # generic fallback — unknown reliability
]
_RISK_DEFAULT = 0.55  # applied when no keyword matches (assume moderate risk)


def _risk_note_to_numeric(risk_note: str) -> float:
    """Convert a qualitative risk_note string to a numeric value [0.0, 1.0].

    Uses ordered keyword matching (first match wins, highest-risk keywords
    listed first).  This is a deliberate simplification — the mapping is
    documented here so it can be reviewed and tuned independently of the
    scoring weights above.
    """
    lower = risk_note.lower()
    for keyword, value in _RISK_KEYWORD_MAP:
        if keyword in lower:
            return value
    return _RISK_DEFAULT


def _estimate_penalty_exposure(transit_time_days: int, penalty_terms: dict) -> float:
    """Estimate how much SLA penalty this route would incur.

    Logic:
      - Parse the SLA deadline from penalty_terms.
      - Assume the route departs NOW and arrives in transit_time_days.
      - Any days past the deadline incur penalty_per_day_late.
      - Returns 0.0 if the route arrives on time.

    Returns USD penalty exposure as a float.
    """
    try:
        deadline_str = penalty_terms.get("sla_deadline", "")
        penalty_per_day = float(penalty_terms.get("penalty_per_day_late", 0))
        if not deadline_str or penalty_per_day == 0:
            return 0.0

        # Strip trailing 'Z' and parse — Python < 3.11 fromisoformat doesn't handle 'Z'
        deadline = datetime.datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        # Assume departure is right now (UTC) and arrival is transit_time_days later
        arrival = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=transit_time_days)
        days_late = max(0.0, (arrival - deadline).total_seconds() / 86400)
        return days_late * penalty_per_day
    except Exception:
        return 0.0  # fail-safe: if we can't parse, don't penalise this route


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalise value to [0.0, 1.0].  Returns 0.5 if all values equal."""
    if max_val == min_val:
        return 0.5
    return (value - min_val) / (max_val - min_val)


def signal_ingestion(state: ShipmentState):
    shipment_id = state.get("shipment_id")
    # For reactive, we might not have lane info initially unless we fetch it or it's passed.
    # The requirement says: call risk_server.get_disruption_for_lane() to attach disruption_context.
    # But wait, we need origin and destination.
    # If the state doesn't have it, we might skip or use dummy?
    # Let's see... the hardcoded list can be used.
    WATCHED_LANES = {
        "SHP-2026-001": {"origin": "CNSHA", "destination": "USLAX"},
        "SHP-2026-002": {"origin": "CNSHA", "destination": "USSEA"}
    }
    lane = WATCHED_LANES.get(shipment_id)
    
    disruption_context = state.get("disruption_context", {})
    
    if lane:
        try:
            resp = httpx.get(f"{RISK_URL}/disruptions/lane", params={"origin": lane["origin"], "destination": lane["destination"]})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("disruptions"):
                    disruption_context = data["disruptions"][0] # Just take the first active disruption
        except Exception:
            pass

    return {
        "disruption_context": disruption_context,
        "status": "context_gathering",
        "notes": [f"[{datetime.datetime.now().isoformat()}] Signal ingested. Trigger: {state.get('trigger_type')}"]
    }

def context_gathering(state: ShipmentState):
    shipment_id = state.get("shipment_id")
    try:
        details_resp = httpx.get(f"{ERP_URL}/shipment/{shipment_id}/details")
        if details_resp.status_code != 200:
            return {
                "status": "error",
                "notes": [f"[{datetime.datetime.now().isoformat()}] Context gathering failed: Shipment not found in ERP."]
            }
        shipment_details = details_resp.json()

        bom_resp = httpx.get(f"{ERP_URL}/shipment/{shipment_id}/bom").json()
        inv_resp = httpx.get(f"{ERP_URL}/shipment/{shipment_id}/inventory_impact").json()
        pen_resp = httpx.get(f"{ERP_URL}/shipment/{shipment_id}/penalty_terms").json()

        return {
            "shipment_details": shipment_details,
            "bill_of_materials": bom_resp,
            "inventory_impact": inv_resp,
            "penalty_terms": pen_resp,
            "status": "ready_for_routing",
            "notes": [f"[{datetime.datetime.now().isoformat()}] Context gathered successfully."]
        }
    except Exception as e:
        return {
            "status": "error",
            "notes": [f"[{datetime.datetime.now().isoformat()}] Context gathering failed: {str(e)}"]
        }


def generate_alternatives(state: ShipmentState) -> dict:
    """Phase 4 node — fetch alternative routes and score them.

    Steps:
      1. Call the freight mock server using the shipment_id and the
         disruption_context already captured in Phase 3 (no re-fetch).
      2. Pull penalty_terms and inventory_impact already in state.
      3. For each returned route, compute a composite_score using a
         weighted formula (see constants at the top of this file).
      4. Sort ascending by composite_score; lowest score = best option.
      5. Set recommended_option to the top-ranked entry.
      6. Set status = "routes_ready" and append a summary note.
    """
    shipment_id = state.get("shipment_id", "")
    disruption_context = state.get("disruption_context", {})
    penalty_terms = state.get("penalty_terms", {})

    # ------------------------------------------------------------------
    # Step 1: Fetch alternative routes from the freight mock server.
    # We pass the disruption_context summary as a query string so the
    # freight server can (in future) return context-aware options.
    # The mock server currently ignores the context, but the call
    # signature is already correct for the real integration.
    # ------------------------------------------------------------------
    disruption_summary = disruption_context.get("title", str(disruption_context))[:200]
    try:
        resp = httpx.get(
            f"{FREIGHT_URL}/shipment/{shipment_id}/alternative_routes",
            params={"disruption_context": disruption_summary},
            timeout=10.0,
        )
        resp.raise_for_status()
        raw_routes = resp.json().get("alternative_routes", [])
    except Exception as e:
        return {
            "status": "error",
            "notes": [f"[{datetime.datetime.now().isoformat()}] generate_alternatives failed: {str(e)}"],
        }

    if not raw_routes:
        return {
            "route_options": [],
            "recommended_option": None,
            "status": "routes_ready",
            "notes": [f"[{datetime.datetime.now().isoformat()}] No alternative routes returned by freight server."],
        }

    # ------------------------------------------------------------------
    # Step 2: Enrich each route with derived fields.
    # ------------------------------------------------------------------
    enriched: list[dict] = []
    for r in raw_routes:
        cost = float(r.get("estimated_cost_usd", 0))
        transit_days = int(r.get("estimated_transit_time_days", 0))
        risk_note = r.get("qualitative_risk_note", "")

        risk_numeric = _risk_note_to_numeric(risk_note)
        penalty_exposure = _estimate_penalty_exposure(transit_days, penalty_terms)

        enriched.append({
            "route_id":        r.get("route_id", ""),
            "carrier":         r.get("carrier", ""),
            "cost":            cost,
            "transit_time_days": transit_days,
            "risk_note":       risk_note,
            "risk_numeric":    risk_numeric,
            "penalty_exposure": penalty_exposure,
            # composite_score will be filled in Step 3
            "composite_score": 0.0,
        })

    # ------------------------------------------------------------------
    # Step 3: Compute composite_score using min-max normalisation.
    #
    # Effective cost = freight_cost + penalty_exposure.
    # This means a slow/cheap route that misses the SLA will have its
    # total cost inflated by the penalty, making it score worse than a
    # faster (potentially pricier) route that arrives on time.
    #
    # composite_score = WEIGHT_COST * norm(effective_cost)
    #                 + WEIGHT_TIME * norm(transit_time_days)
    #                 + WEIGHT_RISK * risk_numeric
    #
    # Lower composite_score = better option.
    # ------------------------------------------------------------------
    effective_costs   = [e["cost"] + e["penalty_exposure"] for e in enriched]
    transit_times     = [e["transit_time_days"] for e in enriched]

    min_cost, max_cost   = min(effective_costs), max(effective_costs)
    min_time, max_time   = min(transit_times),   max(transit_times)
    # risk_numeric is already in [0, 1] so no normalisation needed

    for i, e in enumerate(enriched):
        norm_cost   = _normalize(effective_costs[i], min_cost, max_cost)
        norm_time   = _normalize(transit_times[i],   min_time, max_time)
        norm_risk   = e["risk_numeric"]  # already [0, 1]

        e["composite_score"] = round(
            WEIGHT_COST * norm_cost +
            WEIGHT_TIME * norm_time +
            WEIGHT_RISK * norm_risk,
            4,
        )

    # ------------------------------------------------------------------
    # Step 4: Sort ascending (lowest score = best) and pick top option.
    # ------------------------------------------------------------------
    enriched.sort(key=lambda x: x["composite_score"])
    recommended = enriched[0]

    # ------------------------------------------------------------------
    # Step 5: Build a human-readable summary note.
    # ------------------------------------------------------------------
    penalty_str = (
        f", avoids ~USD{recommended['penalty_exposure']:,.0f} SLA penalty exposure"
        if recommended["penalty_exposure"] > 0
        else ", no SLA penalty exposure"
    )
    summary_note = (
        f"[{datetime.datetime.now().isoformat()}] "
        f"Recommended {recommended['carrier']} ({recommended['route_id']}): "
        f"score={recommended['composite_score']}, "
        f"cost=USD{recommended['cost']:,.0f}, "
        f"transit={recommended['transit_time_days']}d, "
        f"risk={recommended['risk_numeric']}"
        f"{penalty_str}."
    )

    return {
        "route_options":      enriched,
        "recommended_option": recommended,
        "status":             "routes_ready",
        "notes":              [summary_note],
    }


# ---------------------------------------------------------------------------
# Graph wiring
# Phase 3: signal_ingestion → context_gathering
# Phase 4: → generate_alternatives → END   (Phase 5 replaces END with branch)
# ---------------------------------------------------------------------------
builder = StateGraph(ShipmentState)
builder.add_node("signal_ingestion", signal_ingestion)
builder.add_node("context_gathering", context_gathering)
builder.add_node("generate_alternatives", generate_alternatives)

builder.add_edge(START, "signal_ingestion")
builder.add_edge("signal_ingestion", "context_gathering")
builder.add_edge("context_gathering", "generate_alternatives")
builder.add_edge("generate_alternatives", END)
