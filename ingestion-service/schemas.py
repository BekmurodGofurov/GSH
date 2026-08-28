import sys
from pathlib import Path
from pydantic import BaseModel

# Support standalone and container imports for shared_schemas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared_schemas.models import MetricPayload, EventPayload, ServerMetric

class ServerCreate(BaseModel):
    server_id: str  # Format: "188.212.101.109:27015"
    server_name: str
    region: str     # "Vienna", "Warsaw", "EU-East"