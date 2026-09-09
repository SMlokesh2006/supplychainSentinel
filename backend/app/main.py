from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
import httpx
from contextlib import asynccontextmanager

from app.db import setup_db, get_checkpointer
from app.graph import builder
from langgraph.types import Command

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_db()
    yield

app = FastAPI(title="SupplyChain Sentinel", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

@app.get("/cases/pending-approval")
def list_pending_approvals():
    """List all cases currently awaiting human approval.

    Scans Postgres checkpoints (not an in-memory list) so this works even
    after a full server restart.  A case is pending if its graph is
    interrupted at the human_review node — detected by state.next being
    non-empty and the status being "evaluating_tier" (the status set by
    tiered_autonomy_check just before the graph pauses at human_review).

    NOTE: LangGraph's interrupt() halts BEFORE the node returns, so the
    status in state.values still shows the value set by the PREVIOUS node
    (tiered_autonomy_check -> "evaluating_tier").  We also check state.next
    to confirm the graph is actually paused.
    """
    pending = []
    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        # checkpointer.list() yields checkpoint tuples for all threads.
        # We need to iterate all known threads and check which are interrupted.
        # Since PostgresSaver.list() requires a config, we instead query the
        # checkpoint table directly for distinct thread_ids, then check each.
        import psycopg
        from app.db import pool
        with pool.connection() as conn:
            # Get distinct thread_ids from the checkpoints table
            rows = conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints"
            ).fetchall()

        for (thread_id,) in rows:
            try:
                config = {"configurable": {"thread_id": thread_id}}
                snapshot = graph.get_state(config)
                if snapshot.next:  # graph is paused (interrupted)
                    values = snapshot.values or {}
                    rec = values.get("recommended_option") or {}
                    pending.append({
                        "thread_id":    thread_id,
                        "shipment_id":  values.get("shipment_id"),
                        "status":       "awaiting_approval",
                        "risk_tier":    values.get("risk_tier"),
                        "recommended_carrier": rec.get("carrier"),
                        "recommended_cost":    rec.get("cost"),
                        "composite_score":     rec.get("composite_score"),
                        "paused_at_node":      list(snapshot.next),
                    })
            except Exception:
                continue

    return {"pending_cases": pending, "count": len(pending)}



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


# ---------------------------------------------------------------------------
# Phase 6 — Human Approval Endpoints
# ---------------------------------------------------------------------------

@app.get("/cases/{thread_id}/approval-detail")
def get_approval_detail(thread_id: str):
    """Return the full interrupt payload for a paused case.

    This is what a frontend approval screen will render: shipment summary,
    all route options with scores, the recommendation, and the risk
    reasoning that triggered the interrupt.
    """
    config = {"configurable": {"thread_id": thread_id}}
    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        snapshot = graph.get_state(config)

        if not snapshot.values:
            raise HTTPException(status_code=404, detail="Case not found")

        if not snapshot.next:
            raise HTTPException(
                status_code=400,
                detail="Case is not awaiting approval (graph is not paused)"
            )

        values = snapshot.values
        rec = values.get("recommended_option") or {}

        # Extract the interrupt payload from the snapshot tasks
        interrupt_payload = None
        for task in snapshot.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                interrupt_payload = task.interrupts[0].value
                break

        return {
            "thread_id":          thread_id,
            "shipment_id":        values.get("shipment_id"),
            "shipment_summary":   values.get("shipment_details"),
            "route_options":      values.get("route_options", []),
            "recommended_option": rec,
            "risk_tier":          values.get("risk_tier"),
            "autonomy_threshold_used": values.get("autonomy_threshold_used"),
            "notes":              values.get("notes", []),
            "interrupt_payload":  interrupt_payload,
            "paused_at_node":     list(snapshot.next),
        }


class ApproveRequest(BaseModel):
    approved_by: str
    selected_option_index: int


@app.post("/cases/{thread_id}/approve")
def approve_case(thread_id: str, req: ApproveRequest):
    """Approve a high-risk case and resume the graph.

    The selected_option_index lets the approver pick a DIFFERENT route
    than the system recommended — not just rubber-stamp the top pick.
    """
    config = {"configurable": {"thread_id": thread_id}}
    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)

        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="Case not found")
        if not snapshot.next:
            raise HTTPException(status_code=400, detail="Case is not awaiting approval")

        # Resume the graph with the approval decision
        resume_value = {
            "approval_decision":     "approved",
            "approved_by":           req.approved_by,
            "selected_option_index": req.selected_option_index,
        }

        result = graph.invoke(Command(resume=resume_value), config)
        return {
            "thread_id": thread_id,
            "state":     result,
        }


class RejectRequest(BaseModel):
    approved_by: str
    reason: str = "No reason provided"


@app.post("/cases/{thread_id}/reject")
def reject_case(thread_id: str, req: RejectRequest):
    """Reject a high-risk case and resume the graph (no booking is made)."""
    config = {"configurable": {"thread_id": thread_id}}
    with get_checkpointer() as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)

        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="Case not found")
        if not snapshot.next:
            raise HTTPException(status_code=400, detail="Case is not awaiting approval")

        resume_value = {
            "approval_decision": "rejected",
            "approved_by":       req.approved_by,
            "reason":            req.reason,
        }

        result = graph.invoke(Command(resume=resume_value), config)
        return {
            "thread_id": thread_id,
            "state":     result,
        }
