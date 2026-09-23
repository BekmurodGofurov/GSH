# ML Pipeline Documentation

GSH's ML pipeline has two stages that work in sequence:

1. **Anomaly Detection** — detects *whether* a server metric is abnormal
   (owned by the anomaly-detection-ml engineer; see `anomaly-detection-ml/main.py`).
2. **Root-Cause Classification** — determines *why* the anomaly happened
   (owned by MuhammadAyub; see `root-cause-ml/`).

This document covers the root-cause classifier in detail. For the anomaly
detection algorithm, refer to the anomaly-detection-ml engineer.

---

## How Data Reaches root-cause-ml

`anomaly-bridge` (`anomaly-detection-ml/bridge.py`) is the glue between the
two stages. It:

1. Polls `server_metrics` in TimescaleDB every 5 seconds.
2. Sends each new metric row to `anomaly-detection-ml` → `POST /predict/anomaly`.
3. If `is_anomaly: true`, builds a richer payload (including delta features and
   regional context) and calls `root-cause-ml` → `POST /predict/root-cause`.
4. Writes the labeled incident into `server_events` with `label_source='model'`.

The root-cause service **never polls the database itself** — it is stateless and
only responds to HTTP requests from `anomaly-bridge`.

---

## Root-Cause Classifier (`root-cause-ml`)

### What it classifies

Six possible root causes:

| Label | Meaning |
|---|---|
| `SERVER_CRASH` | Process crashed; all players dropped while network was fine |
| `HIGH_LATENCY` | Upstream congestion; ping elevated but players still connected |
| `DDOS_ATTACK` | Extreme ping spike combined with rapid player disconnects |
| `REGIONAL_OUTAGE` | ≥ 2 servers in the same region degraded simultaneously |
| `PLAYER_DROP` | Natural end-of-match player departure; stable network |
| `MAINTENANCE` | Graceful admin-controlled shutdown |

### Service entrypoint

`POST /predict/root-cause` — accepts an `IncidentRequest` Pydantic model,
returns an `IncidentResponse`.

```
IncidentRequest fields:
  server_id                    str       required
  region                       str       default "EU-East"
  player_count                 int ≥ 0   required
  max_players                  int ≥ 0   default 32
  ping_ms                      float ≥ 0 default 50.0
  anomaly_score                float 0–1 default 0.8
  ping_delta                   float     default 0.0   (ms change vs. previous sample)
  player_delta                 int       default 0     (player change vs. previous sample)
  servers_affected_same_region int ≥ 1   default 1
  timestamp                    datetime  default now()
  top_k                        int 1–6   default 3     (how many ranked predictions to return)
```

```
IncidentResponse fields:
  server_id      str
  timestamp      str (ISO 8601)
  primary_cause  str  (top-ranked label)
  confidence     str  HIGH | MEDIUM | LOW
  explanation    str  (human-readable narrative)
  recommendation str  (operator action hint)
  predictions    list[{ rank, root_cause, probability, confidence }]
```

---

## Feature Engineering

Features are computed in two places that must stay in sync:
- **Training**: `train.py` → `add_time_features()` + `build_feature_matrix()`
- **Inference**: `predict.py` → `create_feature_vector()`

### Numeric features (7 raw → scaled with `StandardScaler`)

| Feature | Source |
|---|---|
| `player_count` | from `server_metrics` |
| `max_players` | from `server_metrics` |
| `ping_ms` | from `server_metrics` |
| `anomaly_score` | output of anomaly-detection-ml |
| `ping_delta` | `current_ping − previous_ping` (computed in bridge.py) |
| `player_delta` | `current_players − previous_players` (computed in bridge.py) |
| `servers_affected_same_region` | count of servers in same region with active anomaly in last 1 minute |

### Derived binary/ratio features (3, included in the scaled block)

| Feature | Formula |
|---|---|
| `player_ratio` | `player_count / max(max_players, 1)` |
| `is_empty` | `1` if `player_count == 0` |
| `is_high_ping` | `1` if `ping_ms > 200` |

### Cyclical time features (6, not scaled — appended after scaling)

Timestamp is encoded as sine/cosine pairs to avoid the midnight/Sunday wrap-around
discontinuity that would confuse a linear model:

| Feature | Formula |
|---|---|
| `hour_sin` / `hour_cos` | `sin/cos(2π × hour / 24)` |
| `minute_sin` / `minute_cos` | `sin/cos(2π × minute / 60)` |
| `day_sin` / `day_cos` | `sin/cos(2π × weekday / 7)` |

### Categorical feature

| Feature | Encoding |
|---|---|
| `region` | `OneHotEncoder(handle_unknown="ignore")` — handles unseen regions at inference gracefully |

**Total feature vector**: `10 scaled numerics + 6 time + N region columns (sparse)`,
combined with `scipy.sparse.hstack` into a single CSR matrix.

---

## Prediction Logic (`predict.py`)

```
predict_root_cause(...)
    ↓
    load_model() → try to load models/root_cause_model.pkl
    ↓
    if artifact missing or no scaler:
        → rule_based_labeler()   ← cold-start fallback
    else:
        build feature vector from inputs
        model.predict_proba(X)
        rank results by probability
        if top probability < 0.40:
            → rule_based_labeler()  ← low-confidence fallback
        else:
            use ML results
    ↓
    generate_real_world_narrative()  → explanation + recommendation
    ↓
    return { primary_cause, confidence, explanation, recommendation, predictions[] }
```

Confidence thresholds applied to `probability`:

| Probability | Confidence label |
|---|---|
| ≥ 0.65 | `HIGH` |
| 0.35 – 0.64 | `MEDIUM` |
| < 0.35 | `LOW` |

---

## Rule-Based Fallback (`predict.py → rule_based_labeler`)

Used when: (a) no trained model exists, or (b) ML top-class probability < 0.40.

| Priority | Condition | Label |
|---|---|---|
| 1 | `servers_affected_same_region ≥ 2` | `REGIONAL_OUTAGE` (0.94) |
| 2 | `player_count == 0 AND player_delta ≤ -3` | `SERVER_CRASH` (0.95) |
| 3 | `ping_delta > 140 AND player_delta < -2` | `DDOS_ATTACK` (0.89) |
| 4 | `ping_ms > 160 OR ping_delta > 75` | `HIGH_LATENCY` (0.88) |
| 5 | `player_delta < -4 AND ping_ms < 80` | `PLAYER_DROP` (0.84) |
| default | — | `UNKNOWN_ANOMALY` (0.50) |

---

## Model Training (`train.py`)

### Trigger

```bash
# Via HTTP (while service is running):
POST /train

# Via CLI:
python main.py train

# Or directly:
python train.py
```

### Training data source

```
load_training_data()
    ↓
    Try: SELECT from server_events WHERE root_cause IS NOT NULL
                                    AND root_cause NOT IN ('UNKNOWN','NORMAL')
                                    AND player_count IS NOT NULL
                                    AND anomaly_score IS NOT NULL
    ↓
    if rows < 20:
        use generate_synthetic_bootstrap_data(n_samples=300)
        (300 rows, random_seed=42, balanced across 6 classes and 4 regions)
```

Real data is preferred. The bootstrap dataset exists so the service can train
immediately on a fresh deployment with no historical data yet.

### Model selection

Three classifiers compete; the one with the highest accuracy on a 20% held-out
test set is saved:

| Classifier | Config |
|---|---|
| `RandomForestClassifier` | 100 trees, max_depth=10, class_weight="balanced" |
| `GradientBoostingClassifier` | 100 estimators, max_depth=5 |
| `LogisticRegression` | max_iter=1000, class_weight="balanced" |

Train/test split is 80/20, stratified by class when each class has ≥ 2 samples.

### Artifact

Saved to `root-cause-ml/models/root_cause_model.pkl` as a `joblib` dict:

```python
{
    "model":      <best sklearn classifier>,
    "model_name": "RandomForest" | "GradientBoosting" | "LogisticRegression",
    "scaler":     <StandardScaler fitted on training numerics>,
    "encoder":    <OneHotEncoder fitted on training regions>,
    "classes":    [list of class label strings],
    "accuracy":   float  # validation accuracy (0–1)
}
```

The model artifact is checked on every `/health` request — `model_loaded: true`
and `validation_accuracy` are returned so operators can confirm the service is
ready.

---

## Two Label Namespaces — Do Not Confuse Them

`bridge.py` classifies anomalies with **two separate, independent labels**:

| Label | Field | Values | Who sets it |
|---|---|---|---|
| `event_type` | `server_events.event_type` | `OFFLINE`, `HIGH_PING`, `CRASH` | `bridge.py → classify_event_type()` from anomaly reasons |
| `root_cause` | `server_events.root_cause` | `SERVER_CRASH`, `HIGH_LATENCY`, etc. | `root-cause-ml → primary_cause` |

`event_type` is a coarse operational category derived from the anomaly-detection
output. `root_cause` is the ML-classified business reason. Both are written to the
same `server_events` row and both appear in the dashboard event log.

---

## Adding Active-Learning Labels

Admins can manually correct a root cause label via the gateway API:

```
POST /api/v1/events/{event_id}/label
{ "root_cause": "MAINTENANCE" }
```

This sets `label_source = 'manual'` in `server_events`. The training query
(`load_training_data`) does **not** filter by `label_source` — it uses both
`'model'` and `'manual'` rows. Manually corrected labels therefore automatically
improve the next training run, which is the active-learning loop.
