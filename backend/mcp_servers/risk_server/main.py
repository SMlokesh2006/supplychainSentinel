from fastapi import FastAPI, Query
from .data import DISRUPTIONS

app = FastAPI(title="Risk Mock Server")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "risk_server"}

@app.get("/disruptions/active")
def get_active_disruptions():
    return {"disruptions": DISRUPTIONS}

@app.get("/disruptions/lane")
def get_disruption_for_lane(origin: str, destination: str):
    affected = []
    for d in DISRUPTIONS:
        regions = d.get("affected_regions", [])
        if origin in regions or destination in regions:
            affected.append(d)
    return {
        "lane": {"origin": origin, "destination": destination},
        "disruptions": affected
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
