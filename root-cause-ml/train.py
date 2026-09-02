import os
import argparse
import asyncio
from pathlib import Path
import asyncpg
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from scipy.sparse import hstack

ROOT_DIR = Path(__file__).resolve().parent
MODELS_DIR = ROOT_DIR / "models"
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise ValueError("DB_URL environment variable is not set. Please provide it in the .env file.")

NUMERIC_FEATURES = [
    "player_count", "max_players", "ping_ms", "anomaly_score",
    "ping_delta", "player_delta", "servers_affected_same_region",
]

TIME_FEATURES = [
    "hour_sin", "hour_cos", "minute_sin", "minute_cos", "day_sin", "day_cos",
]


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df["hour"] = df["time"].dt.hour
    df["minute"] = df["time"].dt.minute
    df["day_of_week"] = df["time"].dt.dayofweek

    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["minute_sin"] = np.sin(2 * np.pi * df["minute"] / 60)
    df["minute_cos"] = np.cos(2 * np.pi * df["minute"] / 60)
    df["day_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["day_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    df["player_ratio"] = df["player_count"] / df["max_players"].clip(lower=1)
    df["is_empty"] = (df["player_count"] == 0).astype(int)
    df["is_high_ping"] = (df["ping_ms"] > 200).astype(int)
    return df


def generate_synthetic_bootstrap_data(n_samples: int = 300) -> pd.DataFrame:
    """Generates baseline data for instant bootstrap if DB has no historical labels."""
    np.random.seed(42)
    records = []
    causes = ["SERVER_CRASH", "HIGH_LATENCY", "DDOS_ATTACK", "REGIONAL_OUTAGE", "PLAYER_DROP", "MAINTENANCE"]
    regions = ["Warsaw", "Vienna", "EU-East", "Frankfurt"]

    for _ in range(n_samples):
        cause = np.random.choice(causes)
        region = np.random.choice(regions)
        max_p = np.random.choice([20, 24, 32])
        hour = np.random.randint(0, 24)
        minute = np.random.randint(0, 60)
        time_str = f"2026-08-29 {hour:02d}:{minute:02d}:00"

        if cause == "SERVER_CRASH":
            p_count, ping, p_delta, ping_delta, affected, score = 0, np.random.uniform(0, 15), -int(np.random.randint(8, max_p)), 0.0, 1, np.random.uniform(0.85, 1.0)
        elif cause == "HIGH_LATENCY":
            p_count, ping, p_delta, ping_delta, affected, score = int(np.random.randint(5, max_p)), np.random.uniform(170, 350), -int(np.random.randint(0, 3)), np.random.uniform(80, 200), 1, np.random.uniform(0.75, 0.90)
        elif cause == "DDOS_ATTACK":
            p_count, ping, p_delta, ping_delta, affected, score = int(np.random.randint(0, 5)), np.random.uniform(250, 600), -int(np.random.randint(10, max_p)), np.random.uniform(180, 450), 1, np.random.uniform(0.90, 1.0)
        elif cause == "REGIONAL_OUTAGE":
            p_count, ping, p_delta, ping_delta, affected, score = 0, 0.0, -int(np.random.randint(5, max_p)), 0.0, int(np.random.randint(2, 6)), np.random.uniform(0.90, 1.0)
        elif cause == "PLAYER_DROP":
            p_count, ping, p_delta, ping_delta, affected, score = int(np.random.randint(1, 6)), np.random.uniform(25, 60), -int(np.random.randint(6, 15)), np.random.uniform(-5, 10), 1, np.random.uniform(0.75, 0.85)
        else: # MAINTENANCE
            p_count, ping, p_delta, ping_delta, affected, score = 0, 0.0, -int(np.random.randint(0, 5)), 0.0, 1, np.random.uniform(0.75, 0.95)

        records.append({
            "time": time_str,
            "server_id": f"185.25.180.{np.random.randint(1, 10)}:27015",
            "region": region,
            "player_count": p_count,
            "max_players": max_p,
            "ping_ms": ping,
            "anomaly_score": score,
            "ping_delta": ping_delta,
            "player_delta": p_delta,
            "servers_affected_same_region": affected,
            "root_cause": cause,
        })

    return pd.DataFrame(records)


async def load_training_data() -> pd.DataFrame:
    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch("""
            SELECT se.time, se.server_id, ms.region,
                   se.player_count, se.max_players, se.ping_ms,
                   se.anomaly_score, se.ping_delta, se.player_delta,
                   se.servers_affected_same_region, se.root_cause
            FROM server_events se
            JOIN monitored_servers ms ON ms.server_id = se.server_id
            WHERE se.root_cause IS NOT NULL
              AND se.root_cause NOT IN ('UNKNOWN', 'NORMAL')
              AND se.player_count IS NOT NULL
              AND se.anomaly_score IS NOT NULL;
        """)
        await conn.close()
        if len(rows) >= 20:
            df = pd.DataFrame([dict(r) for r in rows])
            print(f"Loaded {len(df)} labeled events from PostgreSQL.")
            return df
    except Exception as e:
        print(f"Database query warning: {e}")

    print("Using bootstrap dataset for model training...")
    return generate_synthetic_bootstrap_data()


def build_feature_matrix(df: pd.DataFrame, scaler=None, encoder=None, fit=False):
    numeric = df[NUMERIC_FEATURES + ["player_ratio", "is_empty", "is_high_ping"]].values
    time_feats = df[TIME_FEATURES].values

    if fit:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
        region_encoded = encoder.fit_transform(df[["region"]])
        scaler = StandardScaler()
        numeric_scaled = scaler.fit_transform(numeric)
    else:
        region_encoded = encoder.transform(df[["region"]])
        numeric_scaled = scaler.transform(numeric)

    X = hstack([numeric_scaled, time_feats, region_encoded]).tocsr()
    return X, scaler, encoder


async def train() -> dict:
    df = await load_training_data()
    df = add_time_features(df)

    X_df = df.drop(columns=["root_cause"])
    y = df["root_cause"]

    # Faqat har bir toifada kamida 2 ta namuna bo'lsa stratify qilinsin
    stratify_target = y if y.value_counts().min() >= 2 else None

    X_train_df, X_test_df, y_train, y_test = train_test_split(
        X_df, y, test_size=0.2, random_state=42, stratify=stratify_target
    )

    X_train, scaler, encoder = build_feature_matrix(X_train_df, fit=True)
    X_test, _, _ = build_feature_matrix(X_test_df, scaler=scaler, encoder=encoder)

    classifiers = {
        "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, class_weight="balanced"),
        "GradientBoosting": GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42),
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced"),
    }

    best_model, best_name, best_acc = None, "", 0.0
    for name, clf in classifiers.items():
        clf.fit(X_train, y_train)
        acc = accuracy_score(y_test, clf.predict(X_test))
        if acc > best_acc:
            best_acc = acc
            best_model = clf
            best_name = name

    MODELS_DIR.mkdir(exist_ok=True)
    artifact = {
        "model": best_model,
        "model_name": best_name,
        "scaler": scaler,
        "encoder": encoder,
        "classes": list(best_model.classes_),
        "accuracy": best_acc,
    }
    joblib.dump(artifact, MODELS_DIR / "root_cause_model.pkl")
    print(f"Model saved: {best_name} (accuracy: {best_acc * 100:.2f}%)")
    return {"status": "trained", "model": best_name, "accuracy": round(best_acc, 4)}


if __name__ == "__main__":
    asyncio.run(train())