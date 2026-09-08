from typing import TypedDict, Annotated, Optional
import operator

class ShipmentState(TypedDict):
    shipment_id: str
    disruption_type: str
    status: str
    risk_score: Optional[float]
    notes: Annotated[list[str], operator.add]
