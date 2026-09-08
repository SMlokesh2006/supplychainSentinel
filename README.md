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
