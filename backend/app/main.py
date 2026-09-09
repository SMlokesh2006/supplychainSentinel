from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
import httpx
from contextlib import asynccontextmanager

from app.db import setup_db, get_checkpointer
from app.graph import builder

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_db()
    yield

app = FastAPI(title="SupplyChain Sentinel", lifespan=lifespan)

class StartCaseRequest(BaseModel):
    shipment_id: str
    disruption_type: str

@app.post("/cases/start")
def start_case(req: StartCaseRequest):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "shipment_id": req.shipment_id,
        "trigger_type": "manual",
        "status": "created",
        "notes": []
    }

    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        result = graph.invoke(initial_state, config)
        return {
            "thread_id": thread_id,
            "state": result
        }

@app.get("/cases/{thread_id}")
def get_case(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        state = graph.get_state(config)
        if not state.values:
            raise HTTPException(status_code=404, detail="Case not found")
        return {
            "thread_id": thread_id,
            "state": state.values,
            "next": list(state.next)
        }

@app.post("/cases/{thread_id}/resume")
def resume_case(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        
        state = graph.get_state(config)
        if not state.values:
            raise HTTPException(status_code=404, detail="Case not found")
        
        if not state.next:
            raise HTTPException(status_code=400, detail="Graph is not paused")
            
        result = graph.invoke(None, config)
        return {
            "thread_id": thread_id,
            "state": result
        }

class ReactiveTriggerRequest(BaseModel):
    shipment_id: str
    disruption_description: str

@app.post("/cases/trigger/reactive")
def trigger_reactive(req: ReactiveTriggerRequest):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "shipment_id": req.shipment_id,
        "trigger_type": "reactive",
        "disruption_context": {"description": req.disruption_description},
        "status": "created",
        "notes": []
    }

    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        result = graph.invoke(initial_state, config)
        return {
            "thread_id": thread_id,
            "state": result
        }

@app.post("/cases/trigger/proactive-scan")
def trigger_proactive_scan():
    # Poll risk server
    try:
        resp = httpx.get("http://localhost:8003/disruptions/active")
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch active disruptions from risk server")
        disruptions = resp.json().get("disruptions", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Risk server error: {e}")

    # Small hardcoded list of watched shipments
    WATCHED_LANES = {
        "SHP-2026-001": {"origin": "CNSHA", "destination": "USLAX"},
        "SHP-2026-002": {"origin": "CNSHA", "destination": "USSEA"}
    }
    
    created_cases = []
    
    for shipment_id, lane in WATCHED_LANES.items():
        # Check if lane is affected by any disruption
        for disruption in disruptions:
            regions = disruption.get("affected_regions", [])
            if lane["origin"] in regions or lane["destination"] in regions:
                # Trigger case
                thread_id = str(uuid.uuid4())
                config = {"configurable": {"thread_id": thread_id}}
                initial_state = {
                    "shipment_id": shipment_id,
                    "trigger_type": "proactive",
                    "disruption_context": disruption,
                    "status": "created",
                    "notes": []
                }
                with get_checkpointer() as checkpointer:
                    graph = builder.compile(checkpointer=checkpointer)
                    graph.invoke(initial_state, config)
                created_cases.append({"shipment_id": shipment_id, "thread_id": thread_id, "disruption": disruption["title"]})
                break # Move to next shipment once triggered
                
    return {"created_cases": created_cases}
