"""
Layer 6 – ML Anomaly Detector (Isolation Forest)
Unsupervised multivariate anomaly detection using sklearn's IsolationForest.

Why Isolation Forest without a Kaggle dataset?
-----------------------------------------------
Isolation Forest is unsupervised – it does NOT need labelled fraud data.
It learns what "normal" looks like from the bulk of your claim distribution,
then scores deviations from that normality.

Bootstrap strategy
------------------
1. Run ``python scripts/train_fraud_model.py`` once – it generates a synthetic
   training corpus drawn from your realistic claim distributions, seeds it with
   the claim patterns from your existing seed data, and fits the IsolationForest.
2. As your real claim volume grows, re-run the training script (or expose the
   /fraud/retrain endpoint – admin-only) so the model learns real-world patterns.
3. The model files (pkl) are stored locally; no cloud egress.

Graceful degradation
--------------------
If no model file is found (first run before training), this layer returns
score=0.0 and ml_available=False so the other layers carry the full weight.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np

from app.ai_agents.fraud import config as cfg
from app.ai_agents.fraud.ml_model import build_feature_vector, get_model_and_scaler
from app.schemas.fraud import MLResult

logger = logging.getLogger(__name__)


def evaluate(claim_context: Dict[str, Any]) -> MLResult:
    """
    Run IsolationForest anomaly detection on the feature vector.

    Isolation Forest returns a decision function value:
        - Positive values → inlier (normal)
        - Negative values → outlier (anomaly)

    We map that raw score to [0, 1] and scale by cfg.ML_ANOMALY_SCORE_SCALE
    so the ML layer's max contribution never dominates the aggregation.

    Args:
        claim_context: Fully enriched claim context dict.

    Returns:
        MLResult with score in [0.0, 1.0] and ml_available flag.
    """
    model, scaler = get_model_and_scaler()

    if model is None or scaler is None:
        logger.debug("Layer6 ML: model not available – returning 0.0")
        return MLResult(score=0.0, ml_available=False, raw_decision=None)

    try:
        features = build_feature_vector(claim_context).reshape(1, -1)
        features_scaled = scaler.transform(features)

        # decision_function: negative → more anomalous
        raw_decision: float = float(model.decision_function(features_scaled)[0])

        # Sigmoid mapping: decision ≈ 0 → normal centre;
        # large negative values → high fraud probability
        # We flip the sign so anomalous = high value
        anomaly_value = -raw_decision  # more anomalous → larger positive

        # Normalise to [0, 1] using a soft sigmoid centred at 0.0
        import math
        sigmoid = 1.0 / (1.0 + math.exp(-3.0 * anomaly_value))

        # Scale down so ML is a supporting signal, not over-riding L1/L2
        final_score = min(1.0, max(0.0, sigmoid * cfg.ML_ANOMALY_SCORE_SCALE))

        logger.debug(
            "Layer6 ML: raw_decision=%.4f anomaly_value=%.4f final_score=%.4f",
            raw_decision, anomaly_value, final_score,
        )

        return MLResult(score=final_score, ml_available=True, raw_decision=raw_decision)

    except Exception as exc:
        logger.error("Layer6 ML evaluation failed: %s", exc, exc_info=True)
        return MLResult(score=0.0, ml_available=False, raw_decision=None)
