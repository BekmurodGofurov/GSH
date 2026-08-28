from pydantic import BaseModel
from shared_schemas.models import MetricPayload, EventPayload, ServerMetric

class ServerCreate(BaseModel):
    server_id: str  # Format: "188.212.101.109:27015"
    server_name: str
    region: str     # "Vienna", "Warsaw"