import requests
import json
import time

ERP_URL = "http://localhost:8001"
FREIGHT_URL = "http://localhost:8002"
RISK_URL = "http://localhost:8003"

SHIPMENTS_TO_TEST = ["SHP-2026-001", "SHP-2026-002"]

def print_section(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

def fetch_and_print(method, url, params=None):
    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=5)
        print(f"Request: {method} {url}")
        if params:
            print(f"Params: {params}")
        response.raise_for_status()
        print(f"Response ({response.status_code}):\n{json.dumps(response.json(), indent=2)}\n")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}\n")

def run_tests():
    print_section("Health Checks")
    fetch_and_print("GET", f"{ERP_URL}/health")
    fetch_and_print("GET", f"{FREIGHT_URL}/health")
    fetch_and_print("GET", f"{RISK_URL}/health")

    print_section("ERP Server Endpoints")
    for shipment_id in SHIPMENTS_TO_TEST:
        print(f"--- Testing Shipment: {shipment_id} ---")
        fetch_and_print("GET", f"{ERP_URL}/shipment/{shipment_id}/details")
        fetch_and_print("GET", f"{ERP_URL}/shipment/{shipment_id}/bom")
        fetch_and_print("GET", f"{ERP_URL}/shipment/{shipment_id}/inventory_impact")
        fetch_and_print("GET", f"{ERP_URL}/shipment/{shipment_id}/penalty_terms")

    print_section("Freight Server Endpoints")
    for shipment_id in SHIPMENTS_TO_TEST:
        print(f"--- Testing Shipment: {shipment_id} ---")
        fetch_and_print("GET", f"{FREIGHT_URL}/shipment/{shipment_id}/alternative_routes", params={"disruption_context": "Typhoon Kong-rey"})

    print_section("Risk Server Endpoints")
    fetch_and_print("GET", f"{RISK_URL}/disruptions/active")
    fetch_and_print("GET", f"{RISK_URL}/disruptions/lane", params={"origin": "CNSHA", "destination": "USLAX"})
    fetch_and_print("GET", f"{RISK_URL}/disruptions/lane", params={"origin": "NLRTM", "destination": "USNYC"})

if __name__ == "__main__":
    print("Waiting for servers to be up...")
    # Give it a moment to ensure servers have started before making requests.
    time.sleep(2)
    run_tests()
