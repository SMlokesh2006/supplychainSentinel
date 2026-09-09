from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import datetime
import uuid
from .data import SHIPMENTS

app = FastAPI(title="ERP Mock Server")

# ---------------------------------------------------------------------------
# In-memory bookings ledger — persists for the lifetime of the mock server
# process.  Lets the acceptance test verify that high-risk cases never produce
# a booking entry.
# ---------------------------------------------------------------------------
_BOOKINGS: dict[str, dict] = {}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "erp_server"}


@app.get("/shipment/{shipment_id}/details")
def get_shipment_details(shipment_id: str):
    shipment = SHIPMENTS.get(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {
        "shipment_id": shipment_id,
        "origin": shipment["origin"],
        "destination": shipment["destination"],
        "carrier": shipment["carrier"],
        "current_status": shipment["current_status"],
        "cargo_description": shipment["cargo_description"]
    }


@app.get("/shipment/{shipment_id}/bom")
def get_bill_of_materials(shipment_id: str):
    shipment = SHIPMENTS.get(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {
        "shipment_id": shipment_id,
        "bom": shipment["bom"]
    }


@app.get("/shipment/{shipment_id}/inventory_impact")
def get_inventory_impact(shipment_id: str):
    shipment = SHIPMENTS.get(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {
        "shipment_id": shipment_id,
        "inventory_impact": shipment["inventory_impact"]
    }


@app.get("/shipment/{shipment_id}/penalty_terms")
def get_penalty_terms(shipment_id: str):
    shipment = SHIPMENTS.get(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {
        "shipment_id": shipment_id,
        "penalty_terms": shipment["penalty_terms"]
    }


# ---------------------------------------------------------------------------
# Phase 5 — execute_reroute
# Called by auto_execute_node when tiered_autonomy_check classifies a case as
# low-risk.  Records the booking and returns a confirmation payload.
# ---------------------------------------------------------------------------

class ExecuteRerouteRequest(BaseModel):
    shipment_id: str
    route_id: str
    carrier: str
    cost_usd: float
    transit_time_days: int
    # Optional free-text context; passed through for audit purposes only.
    context_note: Optional[str] = None


@app.post("/shipment/execute_reroute")
def execute_reroute(req: ExecuteRerouteRequest):
    """Simulate finalising a reroute booking in the ERP system.

    Generates a deterministic booking_id, calculates a nominal confirmed
    delivery date (today + transit_time_days), records the booking in the
    in-memory ledger, and returns a confirmation dict.
    """
    if req.shipment_id not in SHIPMENTS:
        raise HTTPException(status_code=404, detail=f"Shipment {req.shipment_id} not found")

    booking_id = f"BK-{req.shipment_id}-{req.route_id}-{uuid.uuid4().hex[:6].upper()}"
    confirmed_delivery = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=req.transit_time_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    confirmation = {
        "booking_id":               booking_id,
        "shipment_id":              req.shipment_id,
        "confirmed_carrier":        req.carrier,
        "confirmed_route_id":       req.route_id,
        "confirmed_cost_usd":       req.cost_usd,
        "confirmed_transit_days":   req.transit_time_days,
        "confirmed_delivery_date":  confirmed_delivery,
        "booked_at":                datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # Persist in ledger so tests can verify only low-risk cases appear here.
    _BOOKINGS[booking_id] = confirmation
    return confirmation


@app.get("/bookings")
def list_bookings():
    """Return all bookings recorded this session (for test verification)."""
    return {"bookings": list(_BOOKINGS.values())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
