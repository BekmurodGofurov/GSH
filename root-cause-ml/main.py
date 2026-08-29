"""
Root-Cause Classifier Service (Dual Mode: FastAPI Microservice + CLI)

Endpoints:
  - GET  /health               Liveness and model status check
  - POST /predict/root-cause   Classify incident root cause from telemetry metrics
  - POST /train                Trigger model retraining

CLI Usage:
  python main.py train [--generate-dataset]
  python main.py predict --players 0 --ping 5 --score 0.95 --region Warsaw
  python main.py serve --port 8003
"""

import argparse
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from predict import load_model, predict_root_cause
from train import train

# ============================================================
# PYDANTIC SCHEMAS
# ============================================================

class IncidentRequest(BaseModel):
    server_id: str = Field(..., description="Server IP:port identifier")
    region: str = Field(default="EU-East", description="Server region (Vienna, Warsaw, EU-East)")
    player_count: int = Field(..., ge=0, description="Active connected players")
    max_players: int = Field(default=32, ge=0, description="Server max slot capacity")
    ping_ms: float = Field(default=50.0, ge=0.0, description="Server network roundtrip latency in ms")
    anomaly_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Anomaly detection score (0..1)")
    ping_delta: float = Field(default=0.0, description="Change in ping compared to previous baseline (ms)")
    player_delta: int = Field(default=0, description="Change in players compared to previous baseline")
    servers_affected_same_region: int = Field(default=1, ge=1, description="Number of servers currently degraded in region")
    timestamp: Optional[datetime] = Field(default=None, description="Event timestamp (defaults to now)")
    top_k: int = Field(default=3, ge=1, le=6, description="Number of ranked predictions to return")


class RootCauseItem(BaseModel):
    rank: int
    root_cause: str
    probability: float
    confidence: str


class IncidentResponse(BaseModel):
    server_id: str
    timestamp: str
    primary_cause: str
    confidence: str
    explanation: Optional[str] = None
    recommendation: Optional[str] = None
    predictions: List[RootCauseItem]


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Game Server Root-Cause Classifier",
    version="2.0.0",
    description="ML-powered root-cause diagnosis for game server health anomalies"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Service health and model loading check."""
    try:
        artifact = load_model()
        model_name = artifact.get("model_name", "unknown")
        accuracy = artifact.get("accuracy", 0.0)
        return {
            "status": "ok",
            "service": "root-cause-ml",
            "model_loaded": True,
            "model_name": model_name,
            "validation_accuracy": round(accuracy * 100, 2),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "root-cause-ml",
            "model_loaded": False,
            "error": str(e)
        }


@app.post("/predict/root-cause", response_model=IncidentResponse)
def predict_endpoint(request: IncidentRequest):
    """Predict root-cause classification and real-world explanation for an anomaly incident."""
    try:
        ts = request.timestamp or datetime.now(timezone.utc)
        diagnosis = predict_root_cause(
            server_id=request.server_id,
            player_count=request.player_count,
            max_players=request.max_players,
            ping_ms=request.ping_ms,
            anomaly_score=request.anomaly_score,
            ping_delta=request.ping_delta,
            player_delta=request.player_delta,
            servers_affected_same_region=request.servers_affected_same_region,
            region=request.region,
            timestamp=ts,
            top_k=request.top_k,
        )

        return IncidentResponse(
            server_id=request.server_id,
            timestamp=ts.isoformat(),
            primary_cause=diagnosis["primary_cause"],
            confidence=diagnosis["confidence"],
            explanation=diagnosis.get("explanation"),
            recommendation=diagnosis.get("recommendation"),
            predictions=[RootCauseItem(**item) for item in diagnosis["predictions"]],
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Model artifact not yet trained. Run train.py first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.post("/train")
async def trigger_training():
    """Retrain from manually labelled anomaly incidents in server_events."""
    return await train()


# ============================================================
# CLI INTERFACE
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Root Cause ML System")
    subparsers = parser.add_subparsers(dest="command")

    # TRAIN
    train_p = subparsers.add_parser("train", help="Train ML model")

    # PREDICT
    pred_p = subparsers.add_parser("predict", help="Predict root cause from CLI")
    pred_p.add_argument("--server-id", default="51.77.47.223:27015", help="Server identifier")
    pred_p.add_argument("--region", default="Warsaw", help="Server region (Vienna, Warsaw, EU-East)")
    pred_p.add_argument("--players", type=int, required=True, help="Player count")
    pred_p.add_argument("--max-players", type=int, default=32, help="Max players")
    pred_p.add_argument("--ping", type=float, required=True, help="Ping in ms")
    pred_p.add_argument("--score", type=float, default=0.85, help="Anomaly score")
    pred_p.add_argument("--ping-delta", type=float, default=0.0, help="Ping delta")
    pred_p.add_argument("--player-delta", type=int, default=0, help="Player delta")
    pred_p.add_argument("--servers-affected", type=int, default=1, help="Servers affected in region")

    # SERVE
    serve_p = subparsers.add_parser("serve", help="Run FastAPI microservice")
    serve_p.add_argument("--host", default="0.0.0.0", help="Bind host")
    serve_p.add_argument("--port", type=int, default=8003, help="Bind port")

    args = parser.parse_args()

    if args.command == "train":
        asyncio.run(train())

    elif args.command == "predict":
        try:
            results = predict_root_cause(
                server_id=args.server_id,
                player_count=args.players,
                max_players=args.max_players,
                ping_ms=args.ping,
                anomaly_score=args.score,
                ping_delta=args.ping_delta,
                player_delta=args.player_delta,
                servers_affected_same_region=args.servers_affected,
                region=args.region,
            )

            print("\n" + "=" * 60)
            print(f"ROOT CAUSE DIAGNOSIS ({args.server_id} - {args.region})")
            print("=" * 60)
            for item in results:
                print(f" {item['rank']}. {item['root_cause']:<22} | Prob: {item['probability'] * 100:.1f}% | Confidence: {item['confidence']}")
            print("=" * 60 + "\n")
        except FileNotFoundError:
            print("❌ Model artifact not found. Please train first with `python main.py train`.")

    elif args.command == "serve":
        import uvicorn
        uvicorn.run("main:app", host=args.host, port=args.port, reload=True)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
