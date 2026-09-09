ROUTES_DB = {
    "SHP-2026-001": [
        {
            "route_id": "ALT-1",
            "carrier": "AirBridge Cargo",
            "estimated_cost_usd": 15000,
            "estimated_transit_time_days": 2,
            "qualitative_risk_note": "Air freight bypassing sea port completely. High reliability, high cost."
        },
        {
            "route_id": "ALT-2",
            "carrier": "Trans-Pacific Alternate",
            "estimated_cost_usd": 3500,
            "estimated_transit_time_days": 18,
            "qualitative_risk_note": "Reroute via South Korea port. Adds time but avoids immediate typhoon zone."
        },
        {
            "route_id": "ALT-3",
            "carrier": "Oceanic Freight (Expedited)",
            "estimated_cost_usd": 4000,
            "estimated_transit_time_days": 14,
            "qualitative_risk_note": "Wait out the storm at origin then run on expedited steaming speed."
        }
    ],
    "SHP-2026-002": [
        {
            "route_id": "ALT-1",
            "carrier": "Air Freight Economy",
            "estimated_cost_usd": 12000,
            "estimated_transit_time_days": 4,
            "qualitative_risk_note": "Air freight bypassing sea port. High cost compared to cargo value."
        },
        {
            "route_id": "ALT-2",
            "carrier": "Global Sea Logistics (Reroute)",
            "estimated_cost_usd": 1800,
            "estimated_transit_time_days": 25,
            "qualitative_risk_note": "Reroute via alternate southern port. Lowest cost but highest delay."
        }
    ],
    "SHP-2026-003": [
        {
            "route_id": "ALT-1",
            "carrier": "Air Freight DG",
            "estimated_cost_usd": 25000,
            "estimated_transit_time_days": 3,
            "qualitative_risk_note": "Dangerous Goods certified air freight. Very high cost but fast."
        },
        {
            "route_id": "ALT-2",
            "carrier": "Pacific Movers (Southern Route)",
            "estimated_cost_usd": 6000,
            "estimated_transit_time_days": 16,
            "qualitative_risk_note": "Avoids northern storm tracks. Proven reliability."
        }
    ]
}

def get_alternatives(shipment_id: str, context: str):
    # Returns predefined alternates or generic ones if not explicitly mocked
    if shipment_id in ROUTES_DB:
        return ROUTES_DB[shipment_id]
    
    # Generic fallback alternates for other shipments
    return [
        {
            "route_id": "GEN-ALT-1",
            "carrier": "Generic Air Freight",
            "estimated_cost_usd": 10000,
            "estimated_transit_time_days": 3,
            "qualitative_risk_note": "Air freight fallback. Fast but expensive."
        },
        {
            "route_id": "GEN-ALT-2",
            "carrier": "Generic Ocean Reroute",
            "estimated_cost_usd": 2000,
            "estimated_transit_time_days": 20,
            "qualitative_risk_note": "Standard ocean reroute avoiding disruption zone."
        }
    ]
