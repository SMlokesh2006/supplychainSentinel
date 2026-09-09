"""
Phase 5 Acceptance Test -- Tiered Autonomy + Auto-Execute
==========================================================
Run:
    python test_phase5.py
    pytest test_phase5.py -v

Requires all 4 servers running:
  Main API    : http://localhost:8000
  ERP mock    : http://localhost:8001
  Freight mock: http://localhost:8002
  Risk mock   : http://localhost:8003

Tests
-----
1. LOW-RISK  (SHP-2026-005, textiles, loose SLA): status=auto_executed,
   execution_result populated, ERP booking created.
2. HIGH-RISK (SHP-2026-001, electronics, tight SLA $50k/day): status=
   pending_human_review, execution_result=None, ERP ledger empty for shipment.
3. autonomy_threshold_used recorded in both cases.
4. Notes trail is self-contained: each note names carrier + threshold value.
"""
import requests
import sys

API_URL = "http://127.0.0.1:8000"
ERP_URL = "http://127.0.0.1:8001"


def trigger_reactive(shipment_id, description="Disruption during testing"):
    resp = requests.post(
        f"{API_URL}/cases/trigger/reactive",
        json={"shipment_id": shipment_id, "disruption_description": description},
        timeout=30,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    d = resp.json()
    return d["thread_id"], d["state"]


def find_note(notes, kw):
    return next((n for n in notes if kw.lower() in n.lower()), None)


def pnotes(notes):
    for n in notes:
        print(f"    {n}")


def section(t):
    sep = "=" * 72
    print(f"\n{sep}\n  {t}\n{sep}")


def test_low_risk_auto_executes():
    section("Test 1 -- LOW-RISK path (SHP-2026-005 textiles loose SLA Sept-30)")
    tid, state = trigger_reactive(
        "SHP-2026-005",
        "Minor route disruption on Indian Ocean corridor",
    )
    rec = state.get("recommended_option") or {}
    print(f"  Thread : {tid}")
    print(f"  Status : {state.get('status')}")
    print(f"  Tier   : {state.get('risk_tier')}")
    print(f"  Threshold used: {state.get('autonomy_threshold_used')}")
    print(f"  Recommended: {rec.get('carrier')} ({rec.get('route_id')})")
    print(f"    composite_score={rec.get('composite_score')}  cost_usd={rec.get('cost',0):,.0f}")
    print("  Notes:")
    pnotes(state.get("notes", []))

    assert state["status"] == "auto_executed", (
        f"Expected auto_executed, got '{state['status']}'. "
        "Check thresholds vs route scores."
    )
    assert state.get("risk_tier") == "low", (
        f"Expected risk_tier=low, got '{state.get('risk_tier')}'"
    )
    assert state.get("execution_result") is not None, "execution_result must be set"
    res = state["execution_result"]
    for field in ["booking_id", "confirmed_carrier", "confirmed_cost_usd", "confirmed_delivery_date"]:
        assert field in res, f"execution_result missing: {field}"
    print(f"  Booking ID: {res['booking_id']}")
    assert find_note(state["notes"], "LOW RISK"), "Missing LOW RISK note"
    assert find_note(state["notes"], "booking confirmed"), "Missing booking confirmed note"
    print("  OK")


def test_high_risk_halts_for_review():
    section("Test 2 -- HIGH-RISK path (SHP-2026-001 electronics tight SLA Sept-12)")
    tid, state = trigger_reactive(
        "SHP-2026-001",
        "Typhoon blocking primary shipping lane",
    )
    rec = state.get("recommended_option") or {}
    print(f"  Thread : {tid}")
    print(f"  Status : {state.get('status')}")
    print(f"  Tier   : {state.get('risk_tier')}")
    print(f"  Threshold used: {state.get('autonomy_threshold_used')}")
    print(f"  Recommended: {rec.get('carrier')} ({rec.get('route_id')})")
    print(f"    composite_score={rec.get('composite_score')}  cost_usd={rec.get('cost',0):,.0f}")
    print("  Notes:")
    pnotes(state.get("notes", []))

    assert state["status"] == "pending_human_review", (
        f"Expected pending_human_review, got '{state['status']}'"
    )
    assert state.get("risk_tier") == "high", (
        f"Expected risk_tier=high, got '{state.get('risk_tier')}'"
    )
    assert state.get("execution_result") is None, (
        "execution_result MUST be None -- ERP booking must NOT have been called"
    )
    assert find_note(state["notes"], "HIGH RISK"), "Missing HIGH RISK note"
    assert find_note(state["notes"], "Awaiting human approval"), "Missing Awaiting human approval note"

    ledger = requests.get(f"{ERP_URL}/bookings", timeout=10)
    if ledger.status_code == 200:
        bad = [b for b in ledger.json().get("bookings", []) if b.get("shipment_id") == "SHP-2026-001"]
        assert not bad, f"HIGH-RISK case produced ERP booking: {bad}"
        print("  ERP ledger: 0 bookings for SHP-2026-001 -- correct.")
    print("  OK")


def test_threshold_recorded_in_state():
    section("Test 3 -- autonomy_threshold_used recorded for both cases")
    for sid, lbl in [("SHP-2026-005", "LOW"), ("SHP-2026-001", "HIGH")]:
        _, state = trigger_reactive(sid, "threshold test")
        t = state.get("autonomy_threshold_used")
        assert t is not None, f"autonomy_threshold_used missing for {sid}"
        assert isinstance(t, (int, float)), f"Must be numeric, got {type(t)}"
        print(f"  {lbl} ({sid}): autonomy_threshold_used={t}")
    print("  OK")


def test_notes_are_self_contained_audit_trail():
    section("Test 4 -- Notes audit trail (self-contained human-readable)")
    for sid, lbl in [("SHP-2026-005", "LOW-RISK"), ("SHP-2026-001", "HIGH-RISK")]:
        _, state = trigger_reactive(sid, "audit trail test")
        notes = state.get("notes", [])
        print(f"\n  --- {lbl} ({sid}) ---")
        pnotes(notes)
        tn = find_note(notes, "threshold")
        assert tn, f"No note mentioning threshold for {sid}"
        carrier = (state.get("recommended_option") or {}).get("carrier", "")
        assert carrier, "recommended_option carrier must be set"
        assert carrier in tn, f"Tier note must name the carrier; got: {tn}"
    print("\n  OK")


if __name__ == "__main__":
    print("\nPhase 5 Acceptance Tests -- Tiered Autonomy + Auto-Execute")
    failures = []
    for fn in [
        test_low_risk_auto_executes,
        test_high_risk_halts_for_review,
        test_threshold_recorded_in_state,
        test_notes_are_self_contained_audit_trail,
    ]:
        try:
            fn()
            print(f"  PASSED: {fn.__name__}")
        except AssertionError as exc:
            print(f"\n  FAILED: {fn.__name__}\n     {exc}")
            failures.append(fn.__name__)
        except Exception as exc:
            print(f"\n  ERROR: {fn.__name__}\n     {type(exc).__name__}: {exc}")
            failures.append(fn.__name__)
    sep = "=" * 72
    print(f"\n{sep}")
    if failures:
        print(f"  {len(failures)} FAILED: {failures}")
        sys.exit(1)
    else:
        print("  All Phase 5 acceptance tests PASSED.")
