import datetime
import httpx
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
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

import os
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

# ---------------------------------------------------------------------------
# Risk Evaluation via Groq LLM
#
# This function dynamically calls a Llama 3 model via Groq to evaluate
# the operational risk of a route based on the qualitative note.
# ---------------------------------------------------------------------------
_RISK_DEFAULT = 0.55  # applied as fallback if LLM call fails

def _risk_note_to_numeric(risk_note: str) -> float:
    """Convert a qualitative risk_note string to a numeric value [0.0, 1.0].

    Uses a fast LLM to rate the risk based on the nuanced meaning of the text.
    """
    if not risk_note or not risk_note.strip():
        return _RISK_DEFAULT

    try:
        # Initialize Groq LLM
        # Requires GROQ_API_KEY in the environment
        llm = ChatGroq(model="llama3-8b-8192", temperature=0.0, max_tokens=10)
        
        system_prompt = (
            "You are an expert supply chain risk evaluator. "
            "You will be given a qualitative risk note from a freight carrier. "
            "Your job is to rate the operational risk of this route on a scale from 0.0 to 1.0, "
            "where 0.0 is completely safe and reliable, and 1.0 is extremely high risk "
            "(e.g., dangerous goods, active storms, severe congestion). "
            "Return ONLY a single float number between 0.0 and 1.0. Do not include any other text."
        )
        
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Risk note: {risk_note}")
        ])
        
        # Parse the output
        content = response.content.strip()
        risk_value = float(content)
        
        # Clamp between 0.0 and 1.0
        return max(0.0, min(1.0, risk_value))
    except Exception as e:
        print(f"LLM risk evaluation failed: {e}")
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
# Phase 5 — Tiered-autonomy thresholds
#
# Two independent checks gate the auto-execute path:
#
#   AUTO_EXECUTE_SCORE_THRESHOLD  — composite_score of recommended_option.
#       The composite_score already blends cost, transit time, risk level, AND
#       penalty exposure into a single 0-1 value, so this is the primary gate.
#       "Anything with a composite score below 0.40 is low enough complexity
#       that the agent can proceed without human sign-off."
#
#   AUTO_EXECUTE_COST_THRESHOLD   — raw freight cost of recommended_option (USD).
#       A second, independently legible check a non-technical stakeholder can
#       immediately understand: "we never auto-book anything over $8,000 in
#       freight cost, full stop, regardless of score."
#
# BOTH conditions must be satisfied for auto-execute.  Either threshold
# exceeded → high risk → human review.  The thresholds are named constants so
# they can be changed in one place and demonstrated live without touching logic.
# ---------------------------------------------------------------------------
AUTO_EXECUTE_SCORE_THRESHOLD: float = 0.40   # composite_score upper bound for auto-execute
AUTO_EXECUTE_COST_THRESHOLD:  float = 8000.0 # raw freight cost (USD) upper bound


def tiered_autonomy_check(state: ShipmentState) -> dict:
    """Phase 5 — classify the recommended route as low or high risk.

    Reads recommended_option from state (computed in Phase 4) and compares its
    composite_score and raw freight cost against the named threshold constants.

    Returns:
      - risk_tier: "low" | "high"
      - autonomy_threshold_used: the composite_score threshold applied
        (recorded for the audit trail)
      - status: "evaluating_tier"  (momentary; the conditional edge then routes
        to auto_execute_node or human_review_node which set the final status)
      - notes: one sentence explaining exactly which threshold was checked and
        which direction the decision went, so the audit log is self-contained.
    """
    ts = datetime.datetime.now().isoformat()
    rec = state.get("recommended_option") or {}

    score = float(rec.get("composite_score", 1.0))
    cost  = float(rec.get("cost", 0.0))
    carrier = rec.get("carrier", "unknown")
    route_id = rec.get("route_id", "?")
    risk_note = rec.get("risk_note", "")

    score_ok = score < AUTO_EXECUTE_SCORE_THRESHOLD
    cost_ok  = cost  < AUTO_EXECUTE_COST_THRESHOLD

    if score_ok and cost_ok:
        tier = "low"
        note = (
            f"[{ts}] Tiered autonomy: LOW RISK — auto-execute approved. "
            f"Recommended route {carrier} ({route_id}): "
            f"composite_score={score} < threshold {AUTO_EXECUTE_SCORE_THRESHOLD}, "
            f"cost=USD{cost:,.0f} < threshold USD{AUTO_EXECUTE_COST_THRESHOLD:,.0f}. "
            f"Risk note: '{risk_note}'. Proceeding to auto-execute."
        )
    else:
        tier = "high"
        reasons = []
        if not score_ok:
            reasons.append(
                f"composite_score={score} >= threshold {AUTO_EXECUTE_SCORE_THRESHOLD}"
            )
        if not cost_ok:
            reasons.append(
                f"cost=USD{cost:,.0f} >= threshold USD{AUTO_EXECUTE_COST_THRESHOLD:,.0f}"
            )
        note = (
            f"[{ts}] Tiered autonomy: HIGH RISK — human review required. "
            f"Recommended route {carrier} ({route_id}): "
            f"{'; '.join(reasons)}. "
            f"Risk note: '{risk_note}'. Routing to human_review_node."
        )

    return {
        "risk_tier":               tier,
        "autonomy_threshold_used": AUTO_EXECUTE_SCORE_THRESHOLD,
        "status":                  "evaluating_tier",
        "notes":                   [note],
    }


def _route_after_tier_check(state: ShipmentState) -> str:
    """Conditional edge function — returns the name of the next node.

    LangGraph calls this after tiered_autonomy_check completes and uses the
    return value to select the next node.  The two possible targets are:
      "auto_execute"   — risk_tier is "low"
      "human_review"   — risk_tier is "high" (or missing / unexpected)
    """
    return "auto_execute" if state.get("risk_tier") == "low" else "human_review"


def auto_execute_node(state: ShipmentState) -> dict:
    """Phase 5 — finalise the booking with the ERP mock server.

    Called only on the low-risk path.  Posts the recommended route to the ERP
    server's execute_reroute endpoint and records the confirmation in state.
    """
    ts = datetime.datetime.now().isoformat()
    shipment_id = state.get("shipment_id", "")
    rec = state.get("recommended_option") or {}

    payload = {
        "shipment_id":       shipment_id,
        "route_id":          rec.get("route_id", ""),
        "carrier":           rec.get("carrier", ""),
        "cost_usd":          rec.get("cost", 0.0),
        "transit_time_days": rec.get("transit_time_days", 0),
        "context_note":      f"Auto-executed by SupplyChain Sentinel. score={rec.get('composite_score')}",
    }

    try:
        resp = httpx.post(
            f"{ERP_URL}/shipment/execute_reroute",
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        confirmation = resp.json()
    except Exception as e:
        return {
            "status": "error",
            "notes": [f"[{ts}] auto_execute_node failed to book reroute: {str(e)}"],
        }

    note = (
        f"[{ts}] Auto-executed: booking confirmed. "
        f"Booking ID: {confirmation.get('booking_id')}, "
        f"carrier: {confirmation.get('confirmed_carrier')}, "
        f"cost: USD{confirmation.get('confirmed_cost_usd', 0):,.0f}, "
        f"estimated delivery: {confirmation.get('confirmed_delivery_date')}."
    )

    return {
        "execution_result": confirmation,
        "status":           "auto_executed",
        "notes":            [note],
    }


def human_review_node(state: ShipmentState) -> dict:
    """Phase 6 — real interrupt for human approval.

    This node genuinely pauses graph execution using LangGraph's interrupt().
    The graph state is checkpointed to Postgres and can survive a full process
    restart.  Execution resumes only when the API posts a Command(resume=...)
    to this thread.

    Behaviour:
      1. First execution (before interrupt):
         - Sets approval_requested_at and status = "awaiting_approval"
         - Appends an audit note
         - Calls interrupt() with a rich JSON payload for the approval UI
         - Execution HALTS here — nothing below the interrupt() runs

      2. Second execution (after resume via Command(resume={...})):
         - The node re-executes from the top (LangGraph re-execution semantics)
         - interrupt() returns the resume value (the human's decision)
         - The node stores approval_decision and approved_by in state
         - Returns updated state; graph continues to finalize_execution_node
    """
    ts = datetime.datetime.now().isoformat()
    rec = state.get("recommended_option") or {}
    shipment_id = state.get("shipment_id", "")
    route_options = state.get("route_options", [])
    shipment_details = state.get("shipment_details", {})
    risk_tier_note = ""
    # Find the tier-check note for the approval payload
    for n in reversed(state.get("notes", [])):
        if "Tiered autonomy" in n:
            risk_tier_note = n
            break

    # Build the approval payload — contains enough info for an approval UI
    # to render without re-fetching state
    approval_payload = {
        "shipment_id":       shipment_id,
        "shipment_summary":  shipment_details,
        "route_options":     route_options,
        "recommended_option": rec,
        "risk_tier":         state.get("risk_tier"),
        "risk_reasoning":    risk_tier_note,
        "approval_requested_at": ts,
        "message": (
            f"High-risk reroute requires approval for shipment {shipment_id}. "
            f"Recommended: {rec.get('carrier', '?')} ({rec.get('route_id', '?')}), "
            f"cost=USD{rec.get('cost', 0):,.0f}, "
            f"score={rec.get('composite_score', '?')}. "
            f"Select an option index (0-based) from route_options to approve, "
            f"or reject."
        ),
    }

    # -----------------------------------------------------------------------
    # THE INTERRUPT — graph execution genuinely halts here on first call.
    # On resume, interrupt() returns the value from Command(resume=...).
    # -----------------------------------------------------------------------
    human_decision = interrupt(approval_payload)

    # -----------------------------------------------------------------------
    # AFTER RESUME — human_decision is the dict from Command(resume=...)
    # Expected shape: {"approval_decision": "approved"|"rejected",
    #                  "approved_by": str,
    #                  "selected_option_index": int (for approved),
    #                  "reason": str (for rejected)}
    # -----------------------------------------------------------------------
    decision = human_decision.get("approval_decision", "rejected")
    approved_by = human_decision.get("approved_by", "unknown")

    if decision == "approved":
        idx = int(human_decision.get("selected_option_index", 0))
        if 0 <= idx < len(route_options):
            selected = route_options[idx]
        else:
            selected = rec  # fallback to recommendation if index invalid
        note = (
            f"[{datetime.datetime.now().isoformat()}] Human APPROVED reroute. "
            f"Approved by: {approved_by}. "
            f"Selected option: {selected.get('carrier')} ({selected.get('route_id')}), "
            f"cost=USD{selected.get('cost', 0):,.0f}, "
            f"transit={selected.get('transit_time_days')}d."
        )
        return {
            "approval_decision":    "approved",
            "approved_by":          approved_by,
            "approval_requested_at": ts,
            "recommended_option":   selected,  # override with the human's pick
            "status":               "approved",
            "notes":                [note],
        }
    else:
        reason = human_decision.get("reason", "No reason provided")
        note = (
            f"[{datetime.datetime.now().isoformat()}] Human REJECTED reroute. "
            f"Rejected by: {approved_by}. Reason: {reason}. "
            f"No booking will be submitted."
        )
        return {
            "approval_decision":     "rejected",
            "approved_by":           approved_by,
            "approval_requested_at": ts,
            "status":                "rejected",
            "notes":                 [note],
        }


def finalize_execution_node(state: ShipmentState) -> dict:
    """Phase 6 — execute or finalize based on the approval decision.

    This node runs after human_review_node resumes. It checks
    approval_decision to decide whether to book or skip.
    """
    ts = datetime.datetime.now().isoformat()
    decision = state.get("approval_decision")
    shipment_id = state.get("shipment_id", "")

    if decision == "rejected":
        # Nothing to do — human already set status to "rejected"
        return {
            "status": "rejected",
            "notes":  [f"[{ts}] Finalize: skipped booking (decision was 'rejected')."],
        }

    # decision == "approved" — call ERP to book the selected route
    rec = state.get("recommended_option") or {}
    payload = {
        "shipment_id":       shipment_id,
        "route_id":          rec.get("route_id", ""),
        "carrier":           rec.get("carrier", ""),
        "cost_usd":          rec.get("cost", 0.0),
        "transit_time_days": rec.get("transit_time_days", 0),
        "context_note": (
            f"Human-approved reroute by {state.get('approved_by', '?')}. "
            f"score={rec.get('composite_score')}"
        ),
    }

    try:
        resp = httpx.post(
            f"{ERP_URL}/shipment/execute_reroute",
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
        confirmation = resp.json()
    except Exception as e:
        return {
            "status": "error",
            "notes":  [f"[{ts}] finalize_execution_node failed: {str(e)}"],
        }

    note = (
        f"[{ts}] Booking confirmed after human approval. "
        f"Booking ID: {confirmation.get('booking_id')}, "
        f"carrier: {confirmation.get('confirmed_carrier')}, "
        f"cost: USD{confirmation.get('confirmed_cost_usd', 0):,.0f}, "
        f"delivery: {confirmation.get('confirmed_delivery_date')}."
    )

    return {
        "execution_result": confirmation,
        "status":           "executed",
        "notes":            [note],
    }


# ---------------------------------------------------------------------------
# Graph wiring
# Phase 3: signal_ingestion -> context_gathering
# Phase 4: -> generate_alternatives
# Phase 5: -> tiered_autonomy_check -> [conditional]
#               low  -> auto_execute          -> END
# Phase 6:     high -> human_review (interrupt) -> finalize_execution -> END
# ---------------------------------------------------------------------------
builder = StateGraph(ShipmentState)
builder.add_node("signal_ingestion",      signal_ingestion)
builder.add_node("context_gathering",     context_gathering)
builder.add_node("generate_alternatives", generate_alternatives)
builder.add_node("tiered_autonomy_check", tiered_autonomy_check)
builder.add_node("auto_execute",          auto_execute_node)
builder.add_node("human_review",          human_review_node)
builder.add_node("finalize_execution",    finalize_execution_node)

builder.add_edge(START,                   "signal_ingestion")
builder.add_edge("signal_ingestion",      "context_gathering")
builder.add_edge("context_gathering",     "generate_alternatives")
builder.add_edge("generate_alternatives", "tiered_autonomy_check")

# Conditional branch: low-risk -> auto_execute, high-risk -> human_review
builder.add_conditional_edges(
    "tiered_autonomy_check",
    _route_after_tier_check,
    {"auto_execute": "auto_execute", "human_review": "human_review"},
)

builder.add_edge("auto_execute",       END)
builder.add_edge("human_review",       "finalize_execution")
builder.add_edge("finalize_execution", END)
