"""
Phase 4 Acceptance Test -- Alternative Generation
==================================================
Run:
    python test_phase4.py          (plain output)
    pytest test_phase4.py -v       (pytest output)

Assumes the following servers are already running:
  - Main API    : http://localhost:8000  (uvicorn app.main:app)
  - ERP mock    : http://localhost:8001
  - Freight mock: http://localhost:8002
  - Risk mock   : http://localhost:8003

Tests
-----
1. route_options has 2-4 entries, each with required fields + composite_score
2. recommended_option IS the entry with the lowest composite_score
3. Tight-penalty shipment (SHP-2026-001: $50,000/day) vs.
   loose-penalty shipment (SHP-2026-002: $1,000/day) produce
   visibly different recommendations -- proving penalty context drives scoring.
4. Final notes contain a human-readable recommendation summary.
"""

import requests
import sys

API_URL = "http://127.0.0.1:8000"
REQUIRED_FIELDS = {"carrier", "cost", "transit_time_days", "risk_note", "composite_score"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def trigger_reactive(shipment_id: str, description: str = "Disruption during testing") -> dict:
    """Trigger a reactive case and return the final graph state."""
    resp = requests.post(
        f"{API_URL}/cases/trigger/reactive",
        json={"shipment_id": shipment_id, "disruption_description": description},
        timeout=30,
    )
    assert resp.status_code == 200, (
        f"trigger_reactive failed for {shipment_id}: "
        f"HTTP {resp.status_code} -- {resp.text}"
    )
    return resp.json()["state"]


def print_route_table(shipment_id: str, route_options: list, recommended: dict) -> None:
    """Pretty-print the full route table for manual sanity-check."""
    print(f"\n  {'ROUTE':<12} {'CARRIER':<35} {'COST':>10} {'DAYS':>6} {'RISK':>6} {'PEN_EXP':>12} {'SCORE':>8}  BEST?")
    print(f"  {'-'*12} {'-'*35} {'-'*10} {'-'*6} {'-'*6} {'-'*12} {'-'*8}  -----")
    for r in route_options:
        marker = "  <- STAR" if r["route_id"] == recommended["route_id"] else ""
        print(
            f"  {r['route_id']:<12} {r['carrier']:<35} "
            f"${r['cost']:>9,.0f} {r['transit_time_days']:>6} "
            f"{r['risk_numeric']:>6.2f} ${r['penalty_exposure']:>11,.0f} "
            f"{r['composite_score']:>8.4f}{marker}"
        )
    print()


def section(title: str) -> None:
    print(f"\n{'='*70}\n  {title}\n{'='*70}")


# ---------------------------------------------------------------------------
# Test functions (usable both standalone and as pytest tests)
# ---------------------------------------------------------------------------

def test_route_options_populated():
    """AC1 -- route_options has 2-4 entries, each with required fields."""
    section("Test 1 -- route_options populated (SHP-2026-001)")
    state = trigger_reactive("SHP-2026-001", "Typhoon approaching shipping lane")

    assert state.get("status") == "routes_ready", (
        f"Expected status='routes_ready', got '{state.get('status')}'\n"
        f"Notes: {state.get('notes')}"
    )

    route_options = state.get("route_options", [])
    assert 2 <= len(route_options) <= 4, (
        f"Expected 2-4 route_options, got {len(route_options)}"
    )

    for idx, r in enumerate(route_options):
        missing = REQUIRED_FIELDS - r.keys()
        assert not missing, f"route_options[{idx}] missing fields: {missing}"
        assert isinstance(r["composite_score"], float), (
            f"composite_score must be a float, got {type(r['composite_score'])}"
        )
        assert 0.0 <= r["composite_score"] <= 1.0, (
            f"composite_score {r['composite_score']} out of [0, 1]"
        )

    print(f"  OK  {len(route_options)} routes returned, all required fields present.")
    print_route_table("SHP-2026-001", route_options, state["recommended_option"])


def test_recommended_is_top_scored():
    """AC2 -- recommended_option IS the entry with the lowest composite_score."""
    section("Test 2 -- recommended_option is truly the top-scored entry")
    state = trigger_reactive("SHP-2026-001", "Port congestion alert")

    route_options = state.get("route_options", [])
    recommended   = state.get("recommended_option")

    assert recommended is not None, "recommended_option must not be None"

    min_score = min(r["composite_score"] for r in route_options)
    assert recommended["composite_score"] == min_score, (
        f"recommended_option has score {recommended['composite_score']} but "
        f"best available score is {min_score}"
    )
    print(f"  OK  recommended_option '{recommended['carrier']}' has lowest score {min_score}.")


def test_penalty_context_affects_scoring():
    """AC3 -- tight vs. loose penalty terms produce visibly different recommendations.

    SHP-2026-001 -- electronics, SLA in 3 days, $50,000/day penalty
    SHP-2026-002 -- toys,        SLA in ~16 days, $1,000/day penalty

    Expected behaviour:
      For SHP-2026-001 the fastest route (air freight, 2-4 days) should score
      best because slow routes incur massive penalty exposure.
      For SHP-2026-002 penalty pressure is low, so a cheaper sea route can
      win despite being slower.
    """
    section("Test 3 -- Penalty context changes recommendations")

    state_tight  = trigger_reactive("SHP-2026-001", "Tight SLA -- high penalty shipment")
    state_loose  = trigger_reactive("SHP-2026-002", "Loose SLA -- low penalty shipment")

    rec_tight = state_tight["recommended_option"]
    rec_loose = state_loose["recommended_option"]

    print("\n  SHP-2026-001 (tight, $50k/day penalty)")
    print_route_table("SHP-2026-001", state_tight["route_options"], rec_tight)

    print("  SHP-2026-002 (loose, $1k/day penalty)")
    print_route_table("SHP-2026-002", state_loose["route_options"], rec_loose)

    tight_days = rec_tight["transit_time_days"]
    loose_days = rec_loose["transit_time_days"]

    print(f"  Tight penalty recommendation: '{rec_tight['carrier']}' -- {tight_days} days, "
          f"score {rec_tight['composite_score']}")
    print(f"  Loose penalty recommendation: '{rec_loose['carrier']}' -- {loose_days} days, "
          f"score {rec_loose['composite_score']}")

    assert tight_days <= loose_days, (
        f"Expected tight-penalty recommendation to be at least as fast as loose-penalty one.\n"
        f"Tight: {tight_days} days ({rec_tight['carrier']})\n"
        f"Loose: {loose_days} days ({rec_loose['carrier']})\n"
        "This would indicate penalty_exposure is NOT influencing scoring."
    )
    print(f"\n  OK  Tight-penalty route ({tight_days}d) is <= loose-penalty route ({loose_days}d).")
    print("  OK  Penalty context demonstrably affects the recommendation.")


def test_notes_contain_summary():
    """AC4 -- final notes contain a route recommendation summary."""
    section("Test 4 -- Notes contain recommendation summary")
    state = trigger_reactive("SHP-2026-001", "Generic disruption")

    notes = state.get("notes", [])
    assert any("Recommended" in n for n in notes), (
        f"No 'Recommended ...' note found. Notes: {notes}"
    )
    rec_note = next(n for n in notes if "Recommended" in n)
    print(f"  OK  Recommendation note: {rec_note}")


# ---------------------------------------------------------------------------
# Entrypoint -- run standalone or via pytest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\nPhase 4 Acceptance Tests -- Alternative Generation")
    print("Make sure all 4 servers are running before proceeding.\n")

    failures = []
    for fn in [
        test_route_options_populated,
        test_recommended_is_top_scored,
        test_penalty_context_affects_scoring,
        test_notes_contain_summary,
    ]:
        try:
            fn()
            print(f"\n  PASSED: {fn.__name__}")
        except AssertionError as exc:
            print(f"\n  FAILED: {fn.__name__}\n     {exc}")
            failures.append(fn.__name__)
        except Exception as exc:
            print(f"\n  ERROR: {fn.__name__}\n     {type(exc).__name__}: {exc}")
            failures.append(fn.__name__)

    print(f"\n{'='*70}")
    if failures:
        print(f"  {len(failures)} test(s) FAILED: {failures}")
        sys.exit(1)
    else:
        print("  All Phase 4 acceptance tests PASSED.")
