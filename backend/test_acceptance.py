import subprocess
import time
import httpx

API_URL = "http://127.0.0.1:8000"

def wait_for_server():
    for _ in range(30):
        try:
            httpx.get(f"{API_URL}/docs")
            return
        except httpx.RequestError:
            time.sleep(0.5)
    raise RuntimeError("Server failed to start")

def test_durability():
    print("Starting API server...")
    server = subprocess.Popen(["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
    wait_for_server()

    try:
        print("1. Starting a case...")
        resp = httpx.post(f"{API_URL}/cases/start", json={
            "shipment_id": "SHIP-123",
            "disruption_type": "weather"
        })
        resp.raise_for_status()
        data = resp.json()
        thread_id = data["thread_id"]
        state = data["state"]
        
        assert state["status"] == "awaiting_approval", f"Expected awaiting_approval, got {state['status']}"
        print(f"Case started. Thread ID: {thread_id}. Status: {state['status']}")
        
    finally:
        print("2. Simulating a crash by killing the server...")
        server.terminate()
        server.wait()

    print("Restarting API server...")
    server = subprocess.Popen(["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"])
    wait_for_server()

    try:
        print("3. Checking case state after restart...")
        resp = httpx.get(f"{API_URL}/cases/{thread_id}")
        resp.raise_for_status()
        data = resp.json()
        
        assert data["state"]["status"] == "awaiting_approval", f"Expected awaiting_approval, got {data['state']['status']}"
        print(f"State preserved! Status: {data['state']['status']}")
        
        print("4. Resuming the case...")
        resp = httpx.post(f"{API_URL}/cases/{thread_id}/resume")
        resp.raise_for_status()
        data = resp.json()
        
        assert data["state"]["status"] == "executed", f"Expected executed, got {data['state']['status']}"
        print(f"Case resumed and completed! Final status: {data['state']['status']}")
        for note in data["state"]["notes"]:
            print(f" - {note}")
        
        print("\n✅ Acceptance test passed successfully!")
    finally:
        server.terminate()
        server.wait()

if __name__ == "__main__":
    test_durability()
