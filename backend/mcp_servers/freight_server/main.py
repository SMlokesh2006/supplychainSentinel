from fastapi import FastAPI, Query
from .data import get_alternatives

app = FastAPI(title="Freight Mock Server")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "freight_server"}

@app.get("/shipment/{shipment_id}/alternative_routes")
def get_alternative_routes(shipment_id: str, disruption_context: str = Query(default="None")):
    routes = get_alternatives(shipment_id, disruption_context)
    return {
        "shipment_id": shipment_id,
        "disruption_context_provided": disruption_context,
        "alternative_routes": routes
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
