from fastapi import FastAPI, HTTPException
from .data import SHIPMENTS

app = FastAPI(title="ERP Mock Server")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
