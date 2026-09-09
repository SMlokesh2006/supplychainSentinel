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
    # Phase 5 additions
    # risk_tier: classification produced by tiered_autonomy_check
    #   "low"  — composite_score AND raw cost both below thresholds → auto-execute
    #   "high" — one or both thresholds exceeded → requires human approval
    risk_tier: Optional[str]
    # autonomy_threshold_used: records which threshold values were in effect at
    # decision time so the audit trail is self-contained (thresholds are tunable,
    # so recording the actual value applied is important for reproducibility).
    autonomy_threshold_used: Optional[float]
    # execution_result: populated by auto_execute_node once the ERP booking call
    # succeeds.  Contains booking_id, confirmed_carrier, confirmed_cost,
    # confirmed_delivery_date.  None for high-risk cases that await human approval.
    execution_result: Optional[dict]
    # Phase 6 additions — human-in-the-loop interrupt/resume
    # approval_requested_at: ISO timestamp when the interrupt was raised
    approval_requested_at: Optional[str]
    # approved_by: identifier of the human who approved/rejected (from API payload)
    approved_by: Optional[str]
    # approval_decision: "approved" | "rejected" | None
    approval_decision: Optional[str]
    # status lifecycle (all phases):
    #   "created" -> "context_gathering" -> "ready_for_routing"
    #   -> "routes_ready"          (Phase 4 done)
    #   -> "evaluating_tier"       (Phase 5 — tiered_autonomy_check)
    #   Low-risk path:
    #     -> "auto_executed"       (Phase 5 — booking confirmed)
    #   High-risk path:
    #     -> "awaiting_approval"   (Phase 6 — real interrupt, graph paused)
    #     -> "approved"            (Phase 6 — human approved, about to execute)
    #     -> "executed"            (Phase 6 — booking confirmed after approval)
    #     -> "rejected"            (Phase 6 — human rejected, no booking)
    #   -> "error"
    status: str
    notes: Annotated[list[str], operator.add]

