import requests
import time
import json

API_URL = "http://127.0.0.1:8000"

def print_section(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")

def test_reactive_trigger():
    print_section("1. Testing /cases/trigger/reactive with valid shipment")
    payload = {
        "shipment_id": "SHP-2026-001",
        "disruption_description": "Container fell overboard during storm"
    }
    
    resp = requests.post(f"{API_URL}/cases/trigger/reactive", json=payload)
    if resp.status_code == 200:
        data = resp.json()
        state = data.get("state", {})
        print(f"Thread ID: {data.get('thread_id')}")
        print(f"Status: {state.get('status')}")
        print("Shipment Details:", state.get("shipment_details"))
        print("BOM:", state.get("bill_of_materials"))
        print("Inventory Impact:", state.get("inventory_impact"))
        print("Penalty Terms:", state.get("penalty_terms"))
        print("Notes:\n  - " + "\n  - ".join(state.get("notes", [])))
        
        assert state.get("status") == "ready_for_routing", "Status should be ready_for_routing"
        assert state.get("shipment_details") is not None, "shipment_details missing"
        print("-> SUCCESS")
    else:
        print(f"-> FAILED: {resp.status_code} {resp.text}")

def test_proactive_scan():
    print_section("2. Testing /cases/trigger/proactive-scan")
    
    resp = requests.post(f"{API_URL}/cases/trigger/proactive-scan")
    if resp.status_code == 200:
        data = resp.json()
        cases = data.get("created_cases", [])
        print(f"Created {len(cases)} cases:")
        for c in cases:
            print(f"  - Shipment: {c.get('shipment_id')}, Thread: {c.get('thread_id')}, Disruption: {c.get('disruption')}")
        
        # Verify state of one of the created cases
        if cases:
            thread_id = cases[0].get("thread_id")
            print(f"\nFetching state for thread {thread_id} to verify context gathering...")
            get_resp = requests.get(f"{API_URL}/cases/{thread_id}")
            if get_resp.status_code == 200:
                state = get_resp.json().get("state", {})
                print(f"Status: {state.get('status')}")
                print("Disruption Context:", state.get("disruption_context"))
                print("Shipment Details:", state.get("shipment_details"))
                print("Notes:\n  - " + "\n  - ".join(state.get("notes", [])))
                assert state.get("status") == "ready_for_routing", "Status should be ready_for_routing"
                print("-> SUCCESS")
            else:
                print(f"-> FAILED fetching case: {get_resp.status_code}")
    else:
        print(f"-> FAILED: {resp.status_code} {resp.text}")

def test_invalid_shipment():
    print_section("3. Testing with invalid shipment_id (graceful error handling)")
    payload = {
        "shipment_id": "INVALID-999",
        "disruption_description": "Unknown shipment issue"
    }
    
    resp = requests.post(f"{API_URL}/cases/trigger/reactive", json=payload)
    if resp.status_code == 200:
        data = resp.json()
        state = data.get("state", {})
        print(f"Status: {state.get('status')}")
        print("Notes:\n  - " + "\n  - ".join(state.get("notes", [])))
        
        assert state.get("status") == "error", "Status should be error"
        assert "Context gathering failed" in state.get("notes", [])[-1], "Error note should be present"
        print("-> SUCCESS")
    else:
        print(f"-> FAILED: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    print("Waiting for servers to be up...")
    time.sleep(2)
    test_reactive_trigger()
    test_proactive_scan()
    test_invalid_shipment()
