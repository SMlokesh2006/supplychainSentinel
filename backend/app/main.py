from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid
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
        "disruption_type": req.disruption_type,
        "status": "created",
        "risk_score": None,
        "notes": []
    }

    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer, interrupt_after=["pause"])
        result = graph.invoke(initial_state, config)
        return {
            "thread_id": thread_id,
            "state": result
        }

@app.get("/cases/{thread_id}")
def get_case(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer, interrupt_after=["pause"])
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
        graph = builder.compile(checkpointer=checkpointer, interrupt_after=["pause"])
        
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
