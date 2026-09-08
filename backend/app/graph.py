import datetime
from langgraph.graph import StateGraph, START, END
from app.state import ShipmentState

def start_node(state: ShipmentState):
    return {
        "status": "ingested",
        "notes": [f"[{datetime.datetime.now().isoformat()}] Case ingested"]
    }

def pause_node(state: ShipmentState):
    return {
        "status": "awaiting_approval",
        "notes": [f"[{datetime.datetime.now().isoformat()}] Pausing for human approval"]
    }

def resume_node(state: ShipmentState):
    return {
        "status": "executed",
        "notes": [f"[{datetime.datetime.now().isoformat()}] Resumed and executed"]
    }

builder = StateGraph(ShipmentState)
builder.add_node("start", start_node)
builder.add_node("pause", pause_node)
builder.add_node("resume", resume_node)

builder.add_edge(START, "start")
builder.add_edge("start", "pause")
builder.add_edge("pause", "resume")
builder.add_edge("resume", END)
