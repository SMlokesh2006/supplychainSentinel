"""
Phase 6 Acceptance Test -- Human Interrupt + Resume Path
==========================================================
Run:
    python test_phase6.py

Requires the 3 mock servers running:
  ERP mock    : http://localhost:8001
  Freight mock: http://localhost:8002
  Risk mock   : http://localhost:8003

IMPORTANT: 
  DO NOT run the main API (port 8000) yourself before running this test.
  This script will start, kill, and restart the main API process to prove
  that the LangGraph interrupt state survives process restarts.
"""
import requests
import sys
import time
import subprocess
import os

API_URL = "http://127.0.0.1:8000"
ERP_URL = "http://127.0.0.1:8001"

server_process = None

def start_server():
    global server_process
    print("  [Server] Starting FastAPI server on port 8000...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            resp = requests.get(f"{API_URL}/docs", timeout=1)
            if resp.status_code == 200:
                print("  [Server] Server is UP.")
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.5)
    raise RuntimeError("Failed to start FastAPI server.")

def stop_server():
    global server_process
    if server_process:
        print("  [Server] Killing FastAPI server...")
        server_process.kill()
        server_process.wait()
        server_process = None
        print("  [Server] Server is DOWN.")

def trigger_reactive(shipment_id, description="Disruption during testing"):
    resp = requests.post(
        f"{API_URL}/cases/trigger/reactive",
        json={"shipment_id": shipment_id, "disruption_description": description},
        timeout=30,
    )
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    d = resp.json()
    return d["thread_id"], d["state"]

def section(t):
    sep = '='*72
    print(f"\n{sep}\n  {t}\n{sep}")

def test_interrupt_and_resume():
    section("Test 1: Trigger high-risk case, interrupt, restart server, approve alternate route")
    start_server()
    try:
        print("\n  1. Triggering high-risk case (SHP-2026-001)...")
        thread_id, state = trigger_reactive("SHP-2026-001", "Typhoon blocking primary lane")
        print(f"     Thread ID: {thread_id}")
        print(f"     Initial Status: {state.get('status')}")
        assert state.get("status") == "awaiting_approval", f"Expected 'awaiting_approval', got {state.get('status')}"
        
        resp = requests.get(f"{API_URL}/cases/pending-approval")
        assert resp.status_code == 200
        pending = resp.json().get("pending_cases", [])
        assert any(c["thread_id"] == thread_id for c in pending), "Case not found in pending-approval list!"
        print("     ✓ Case is successfully interrupted and listed in pending approvals.")

        print("\n  2. Simulating process crash/restart...")
        stop_server()
        time.sleep(1)
        start_server()

        print("\n  3. Verifying state survived the restart...")
        resp = requests.get(f"{API_URL}/cases/pending-approval")
        assert resp.status_code == 200
        pending = resp.json().get("pending_cases", [])
        assert any(c["thread_id"] == thread_id for c in pending), "Case vanished from pending-approval after restart!"
        print("     ✓ Case is STILL in pending approvals after restart.")
        
        resp = requests.get(f"{API_URL}/cases/{thread_id}/approval-detail")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["thread_id"] == thread_id
        assert detail["interrupt_payload"] is not None, "Interrupt payload is missing!"
        payload = detail["interrupt_payload"]
        print(f"     ✓ Approval detail retrieved. Message: {payload.get('message')}")
        
        print("\n  4. Approving case with alternate route (index 1)...")
        options = detail["route_options"]
        selected_idx = 1 if len(options) > 1 else 0
        selected_route_id = options[selected_idx]["route_id"]
        
        resp = requests.post(
            f"{API_URL}/cases/{thread_id}/approve",
            json={"approved_by": "Test Operator", "selected_option_index": selected_idx}
        )
        assert resp.status_code == 200, f"Approve failed: {resp.text}"
        final_state = resp.json()["state"]
        
        assert final_state.get("status") == "executed", f"Expected 'executed', got {final_state.get('status')}"
        assert final_state.get("approval_decision") == "approved"
        
        exec_res = final_state.get("execution_result")
        assert exec_res is not None, "Execution result missing!"
        assert exec_res.get("confirmed_route_id") == selected_route_id, \
            f"Expected booked route {selected_route_id}, got {exec_res.get('confirmed_route_id')}"
        print(f"     ✓ Case successfully executed with alternate route ({selected_route_id}).")
    finally:
        stop_server()

def test_reject_flow():
    section("Test 2: Trigger high-risk case, reject, confirm no execution")
    start_server()
    try:
        print("\n  1. Triggering second high-risk case (SHP-2026-003)...")
        thread_id, state = trigger_reactive("SHP-2026-003", "Testing reject flow")
        assert state.get("status") == "awaiting_approval"
        
        print("\n  2. Rejecting the case...")
        resp = requests.post(
            f"{API_URL}/cases/{thread_id}/reject",
            json={"approved_by": "Test Operator", "reason": "Too expensive"}
        )
        assert resp.status_code == 200, f"Reject failed: {resp.text}"
        final_state = resp.json()["state"]
        
        assert final_state.get("status") == "rejected", f"Expected 'rejected', got {final_state.get('status')}"
        assert final_state.get("approval_decision") == "rejected"
        assert final_state.get("execution_result") is None, "Execution result should be None for rejected cases!"
        print("     ✓ Case status is 'rejected' and no execution result exists.")
        
        print("\n  3. Verifying ERP ledger...")
        ledger = requests.get(f"{ERP_URL}/bookings", timeout=10)
        if ledger.status_code == 200:
            bad = [b for b in ledger.json().get("bookings",[]) if b.get("shipment_id")=="SHP-2026-003"]
            assert not bad, f"REJECTED case produced an ERP booking: {bad}"
            print(f"     ✓ ERP ledger: 0 bookings for SHP-2026-003 -- correct.")
    finally:
        stop_server()

if __name__ == "__main__":
    print("\nPhase 6 Acceptance Tests -- Human Interrupt + Resume Path")
    try:
        requests.get(f"{API_URL}/docs", timeout=1)
        print("\n[ERROR] Port 8000 is currently in use.")
        print("This test needs to start and stop the main API server itself.")
        print("Please kill your 'uvicorn app.main:app' process before running this test.")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        pass
        
    failures = []
    for fn in [test_interrupt_and_resume, test_reject_flow]:
        try:
            fn()
            print(f"\n  PASSED: {fn.__name__}")
        except AssertionError as e:
            print(f"\n  FAILED: {fn.__name__}\n     {e}")
            failures.append(fn.__name__)
        except Exception as e:
            print(f"\n  ERROR: {fn.__name__}\n     {type(e).__name__}: {e}")
            failures.append(fn.__name__)
            
    sep = '='*72
    print(f"\n{sep}")
    if failures:
        print(f"  {len(failures)} FAILED: {failures}")
        sys.exit(1)
    else:
        print("  All Phase 6 acceptance tests PASSED.")
