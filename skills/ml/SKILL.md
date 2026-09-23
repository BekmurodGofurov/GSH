---
name: gsh-root-cause-ml
description: >
  Use this skill whenever modifying root-cause-ml — adding or renaming a feature,
  changing thresholds, retraining the model, changing the HTTP contract, or adding
  a new root-cause label. Also activate when wiring root-cause-ml output into a new
  consumer (e.g., the agent harness or a new alerting path).
---

# GSH Root-Cause ML Rules

These rules exist because `root-cause-ml` has two parts that must always stay in
sync — the training code (`train.py`) and the inference code (`predict.py`) — and
because it sits in the middle of a live pipeline where contract breaks are silent
until something explodes downstream.

## The two files that must always match

`train.py` and `predict.py` independently build the feature vector. If you add,
remove, or rename a feature in one, you must update the other in the same commit:

| What changes | Files to update |
|---|---|
| Add a numeric feature | `train.py: NUMERIC_FEATURES` list **and** `predict.py: create_feature_vector()` raw_numeric array |
| Add a derived feature | `train.py: add_time_features()` **and** `predict.py: create_feature_vector()` |
| Change region encoding | Both `build_feature_matrix()` in `train.py` and `create_feature_vector()` in `predict.py` |

A mismatch means inference will silently use a different feature vector than the
model was trained on — the model will still produce output, just wrong output.

## Retraining safely

**Do not retrain while the service is under heavy load.** Training is CPU-bound
and runs in the same process. In production, trigger retraining via
`POST /train` only during a low-traffic window.

**The model file is replaced atomically by `joblib.dump`.** However, `load_model()`
caches the artifact in a global variable (`_artifact`). After retraining, the
in-memory cache is stale until the process restarts or `_artifact` is invalidated.
If you need hot-reload after training, add `_artifact = None` at the end of `train()`
to force `load_model()` to re-read the file on the next prediction request.

**Never manually overwrite `root_cause_model.pkl`** while the service is running —
`joblib.load` is not atomic and a partial write will crash the service.

## Do not change the HTTP input/output contract without updating bridge.py

`anomaly-bridge` (`anomaly-detection-ml/bridge.py`) calls `POST /predict/root-cause`
and expects exactly these fields in the request body:

```
server_id, region, player_count, max_players, ping_ms, anomaly_score,
ping_delta, player_delta, servers_affected_same_region, timestamp
```

And exactly these fields in the response:

```
primary_cause, confidence, explanation, recommendation, predictions[]
```

If you rename or remove a field, `bridge.py` will break silently (it will send the
old field name, which Pydantic will accept as the default value rather than raising
an error). Always update `bridge.py` in the same PR.

## Adding a new root-cause label

1. Add the label string to `generate_synthetic_bootstrap_data()` in `train.py`
   (the `causes` list) and add representative synthetic rows for it.
2. Add a case to `rule_based_labeler()` in `predict.py` with explicit threshold
   conditions — do not leave the new label reachable only via ML until you have
   enough real labeled data.
3. Add a case to `generate_real_world_narrative()` in `predict.py` — the agent
   and the Telegram bot both display this text; "Unclassified telemetry deviation"
   for a known label is confusing.
4. Retrain the model. Check that the new label appears in `artifact["classes"]`.
5. Update `docs/ml.md` — the label table and the rule-based table.

## Confidence thresholds — do not change silently

The thresholds in `predict.py` (`0.65` = HIGH, `0.35` = MEDIUM, `0.40` = ML
fallback to rule-based) directly affect what the dashboard and Telegram alerts
display. If you tune them, document the reasoning in the PR and update `docs/ml.md`.

## The rule-based fallback is not a bug

When ML top-class probability < 0.40, the code intentionally falls back to
`rule_based_labeler()`. This is the designed cold-start and low-confidence path —
do not remove it to "simplify" the code. Without it, a fresh deployment with no
trained model would crash on every anomaly.

## root-cause-ml does not talk to the database

Only `train.py` opens a DB connection (to load training data). The running
service (`main.py`, `predict.py`) is stateless and must stay that way — it
receives all inputs over HTTP. Do not add a `DB_URL` read to `predict.py` or
`main.py`'s startup. If you need a feature from the DB at inference time, compute
it in `bridge.py` and add it to the request payload.

## Quick checklist before opening a PR

- [ ] Feature change updated in **both** `train.py` and `predict.py`
- [ ] HTTP contract change propagated to `bridge.py`
- [ ] New root-cause label has: synthetic data, rule-based case, narrative, docs update
- [ ] Retrained model artifact committed (or CI retrains on deploy)
- [ ] `POST /health` on the running service returns `model_loaded: true`
