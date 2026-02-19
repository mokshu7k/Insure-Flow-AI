"""
ML Model Utilities
Handles loading, caching, and feature extraction for the Isolation Forest model.

Design
------
- Models are serialised with joblib to ``cfg.ML_MODEL_PATH`` / ``cfg.ML_SCALER_PATH``.
- If no model file exists the layer gracefully degrades (returns 0.0 score).
- Thread-safe lazy loading via module-level cache.
- Feature vector is deterministic: no randomness, no external calls.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np

from app.ai_agents.fraud import config as cfg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level lazy cache so we only load once per process startup
# ---------------------------------------------------------------------------
_model = None       # IsolationForest
_scaler = None      # StandardScaler


def _load_artifacts() -> Tuple[Any, Any]:
    """Load (model, scaler) from disk, or return (None, None) if absent."""
    global _model, _scaler
    if _model is not None:
        return _model, _scaler

    model_path = cfg.ML_MODEL_PATH
    scaler_path = cfg.ML_SCALER_PATH

    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        logger.info(
            "ML model files not found at '%s' / '%s'. "
            "Layer 6 will be inactive until you run: python scripts/train_fraud_model.py",
            model_path, scaler_path,
        )
        return None, None

    try:
        _model = joblib.load(model_path)
        _scaler = joblib.load(scaler_path)
        logger.info("ML fraud model loaded from '%s'", model_path)
        return _model, _scaler
    except Exception as exc:
        logger.error("Failed to load ML model: %s", exc)
        return None, None


def get_model_and_scaler() -> Tuple[Optional[Any], Optional[Any]]:
    """Public accessor – returns cached (model, scaler) or (None, None)."""
    return _load_artifacts()


def reload_model() -> bool:
    """
    Force-reload model from disk (called after retraining).
    Returns True on success, False on failure.
    """
    global _model, _scaler
    _model = None
    _scaler = None
    m, s = _load_artifacts()
    return m is not None


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
CLAIM_TYPE_MAP = {"HEALTH": 0, "MOTOR": 1, "REIMBURSEMENT": 2}


def build_feature_vector(claim_context: Dict[str, Any]) -> np.ndarray:
    """
    Extract a fixed-length numerical feature vector for the IsolationForest.

    Features (in order):
        0  claim_amount_log      – log1p(claim_amount) – compresses skew
        1  claim_type_encoded    – 0/1/2 ordinal
        2  recent_claim_count    – from UserFraudProfile
        3  prior_fraud_flags     – from UserFraudProfile
        4  days_to_policy_expiry – integer days (clipped at 0 and 730)
        5  amount_z_score        – z-score relative to claim-type baseline
        6  total_claim_amount_90d_log – log1p of 90-day rolling total

    Returns:
        1-D numpy array of shape (7,).
    """
    claim_amount: float = float(claim_context.get("claim_amount", 0.0))
    claim_type: str = claim_context.get("claim_type", "HEALTH")
    baseline = cfg.STATISTICAL_BASELINES.get(claim_type, {"mean": 50_000.0, "std": 25_000.0})

    amount_log = float(np.log1p(claim_amount))
    type_encoded = float(CLAIM_TYPE_MAP.get(claim_type, 0))
    recent_count = float(min(claim_context.get("recent_claim_count", 0), 20))
    fraud_flags = float(min(claim_context.get("prior_fraud_flags", 0), 10))
    days_expiry = float(
        max(0.0, min(730.0, claim_context.get("days_to_policy_expiry", 365) or 365))
    )
    z_score = (
        abs(claim_amount - baseline["mean"]) / baseline["std"]
        if baseline["std"] > 0 else 0.0
    )
    amount_90d_log = float(
        np.log1p(claim_context.get("total_claim_amount_90d", 0.0) or 0.0)
    )

    return np.array([
        amount_log,
        type_encoded,
        recent_count,
        fraud_flags,
        days_expiry,
        z_score,
        amount_90d_log,
    ], dtype=np.float64)


def get_feature_names() -> List[str]:
    return [
        "claim_amount_log",
        "claim_type_encoded",
        "recent_claim_count",
        "prior_fraud_flags",
        "days_to_policy_expiry",
        "amount_z_score",
        "total_claim_amount_90d_log",
    ]
