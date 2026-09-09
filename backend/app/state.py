from typing import TypedDict, Annotated, Optional
import operator

class ShipmentState(TypedDict):
    shipment_id: str
    trigger_type: str
    disruption_context: dict
    shipment_details: dict
    bill_of_materials: dict
    inventory_impact: dict
    penalty_terms: dict
    # Phase 4 additions
    # route_options: list of dicts, each containing:
    #   - carrier (str)
    #   - cost (float)             — USD from freight server
    #   - transit_time_days (int)  — from freight server
    #   - risk_note (str)          — qualitative text from freight server
    #   - composite_score (float)  — computed by generate_alternatives; lower = better
    #   - risk_numeric (float)     — derived numeric risk (0.0 low … 1.0 high)
    #   - penalty_exposure (float) — estimated penalty USD if this route is chosen
    route_options: list
    # recommended_option: the route_options entry with the lowest composite_score
    recommended_option: Optional[dict]
    # status lifecycle (all phases):
    #   "created" → "context_gathering" → "ready_for_routing"
    #   → "generating_routes" (Phase 4 in-progress)
    #   → "routes_ready"      (Phase 4 done)
    #   → (Phase 5 adds tiered-autonomy branch)
    #   → "error"
    status: str
    notes: Annotated[list[str], operator.add]
