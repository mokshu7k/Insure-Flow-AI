"""
Layer 6 — ML Model (Isolation Forest)
Anomaly detection using a trained Isolation Forest.
Degrades gracefully if model file is missing or scikit-learn unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "fraud_model.pkl")
_model = None
_model_loaded = False


def _load_model():
    global _model, _model_loaded
    if _model_loaded:
        return _model
    try:
        import joblib
        path = os.path.abspath(_MODEL_PATH)
        if os.path.exists(path):
            _model = joblib.load(path)
            logger.info("Fraud ML model loaded from %s", path)
        else:
            logger.warning("Fraud ML model not found at %s. Layer 6 disabled.", path)
    except Exception as exc:
        logger.warning("Failed to load fraud ML model: %s", exc)
    finally:
        _model_loaded = True
    return _model


def _build_feature_vector(context: dict[str, Any]) -> list[float]:
    return [
        float(context.get("claim_amount", 0)),
        float(context.get("recent_claims_30d", 0)),
        float(context.get("total_claim_amount_90d", 0)),
        float(context.get("fraud_flag_count", 0)),
        float(context.get("days_since_policy_start", 365)),
        float(context.get("provider_claim_count_30d", 0)),
        float(context.get("provider_fraud_flag_pct", 0.0)),
    ]


def run(context: dict[str, Any]) -> dict[str, Any]:
    model = _load_model()
    if model is None:
        return {"score": 0.0, "flags": [], "layer": "ml", "model_used": False}

    try:
        import numpy as np
        features = np.array([_build_feature_vector(context)])
        raw_score = model.decision_function(features)[0]
        # Isolation Forest: negative score = more anomalous
        # Map to [0,1] where 1 = most anomalous
        normalized = float(1.0 - (raw_score + 0.5))
        normalized = max(0.0, min(1.0, normalized))
        flags = ["ML_ANOMALY_DETECTED"] if normalized > 0.6 else []
        return {"score": normalized, "flags": flags, "layer": "ml", "model_used": True}
    except Exception as exc:
        logger.warning("ML inference failed: %s", exc)
        return {"score": 0.0, "flags": [], "layer": "ml", "model_used": False}


def reload_model() -> None:
    global _model, _model_loaded
    _model = None
    _model_loaded = False
    _load_model()
