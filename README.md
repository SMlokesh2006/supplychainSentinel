# SupplyChain Sentinel (Phase 1)

This project demonstrates the durable execution mechanism using a LangGraph-based agent system. In this phase, we prove that a LangGraph graph can pause mid-execution, persist its state to PostgreSQL, and resume from the exact same state even after the process restarts.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (to run the PostgreSQL instance)
- Node.js (for the frontend scaffold)

## Setup and Installation

1. Start the PostgreSQL database:
   ```bash
   docker-compose up -d
   ```

2. Navigate to the backend directory and set up the Python environment:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create the `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

## Running the Backend Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Running the Acceptance Test

To prove the durability of the system, we have provided an acceptance test script that programmatically starts the API, triggers a case, forces a simulated crash, restarts the API, and completes the case.

While the database is running (via `docker-compose up -d`), run:

```bash
cd backend
python test_acceptance.py
```

## Manual Verification Flow (via cURL)

You can manually verify the system's pause and resume behavior using `curl`:

1. Start a new case:
   ```bash
   curl -X POST http://127.0.0.1:8000/cases/start \
     -H "Content-Type: application/json" \
     -d '{"shipment_id": "SHIP-001", "disruption_type": "weather"}'
   ```
   *Note the `thread_id` returned in the response.*

2. Manually kill the `uvicorn` server (Ctrl+C).

3. Start the `uvicorn` server again:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

4. Retrieve the case state to verify it survived the crash:
   ```bash
   curl -X GET http://127.0.0.1:8000/cases/<YOUR_THREAD_ID>
   ```
   *The state should still show `"status": "awaiting_approval"`.*

5. Resume the case to completion:
   ```bash
   curl -X POST http://127.0.0.1:8000/cases/<YOUR_THREAD_ID>/resume
   ```
   *The response will show `"status": "executed"` and a complete log of notes.*

## Phase 2: Mock MCP Servers

Phase 2 introduces three standalone FastAPI services simulating external data providers: ERP, Freight, and Risk. These services will be integrated as MCP tools in Phase 3.

### Running the Mock Servers

From the `backend` directory, run:
```bash
docker-compose up --build
```
This starts three independent servers on ports 8001, 8002, and 8003.

### Endpoints & Examples

#### ERP Server (Port 8001)
- `GET /health` : Health check
- `GET /shipment/{shipment_id}/details` : Origin, destination, carrier, status, cargo description.
- `GET /shipment/{shipment_id}/bom` : Bill of materials (components & quantities).
- `GET /shipment/{shipment_id}/inventory_impact` : Downstream dependent lines and buffer stock days.
- `GET /shipment/{shipment_id}/penalty_terms` : SLA deadline and late penalty details.

**Example Request:**
```bash
curl http://localhost:8001/shipment/SHP-2026-001/details
```
**Example Response:**
```json
{
  "shipment_id": "SHP-2026-001",
  "origin": "CNSHA",
  "destination": "USLAX",
  "carrier": "Oceanic Freight",
  "current_status": "In Transit",
  "cargo_description": "High-value consumer electronics (Laptops, Smartphones)"
}
```

#### Freight Server (Port 8002)
- `GET /health` : Health check
- `GET /shipment/{shipment_id}/alternative_routes?disruption_context={context}` : Returns alternative routing options with cost, time, and risk note.

**Example Request:**
```bash
curl http://localhost:8002/shipment/SHP-2026-001/alternative_routes
```
**Example Response:**
```json
{
  "shipment_id": "SHP-2026-001",
  "disruption_context_provided": "None",
  "alternative_routes": [
    {
      "route_id": "ALT-1",
      "carrier": "AirBridge Cargo",
      "estimated_cost_usd": 15000,
      "estimated_transit_time_days": 2,
      "qualitative_risk_note": "Air freight bypassing sea port completely. High reliability, high cost."
    }
  ]
}
```

#### Risk Server (Port 8003)
- `GET /health` : Health check
- `GET /disruptions/active` : List of current active disruptions globally.
- `GET /disruptions/lane?origin={origin}&destination={destination}` : Disruptions specifically affecting the given lane.

**Example Request:**
```bash
curl "http://localhost:8003/disruptions/lane?origin=CNSHA&destination=USLAX"
```
**Example Response:**
```json
{
  "lane": { "origin": "CNSHA", "destination": "USLAX" },
  "disruptions": [
    {
      "disruption_id": "EVT-001",
      "type": "Weather",
      "title": "Super Typhoon Kong-rey",
      "affected_regions": ["CNSHA", "CNSZX", "East China Sea"],
      "severity": "CRITICAL",
      "estimated_duration_days": 5,
      "description": "A category 5 typhoon is approaching..."
    }
  ]
}
```

### Testing the Endpoints

A simple Python script is provided to test the mock endpoints and visually sanity-check the data:
```bash
python backend/mcp_servers/test_endpoints.py
```
