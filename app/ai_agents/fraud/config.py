"""
Fraud Engine Configuration
All thresholds, weights, and tuning constants live here.
No magic numbers allowed in engine logic.
"""
from typing import Dict


# ---------------------------------------------------------------------------
# Versioning – embedded in every FraudAssessmentResponse for traceability
# ---------------------------------------------------------------------------
CONFIG_VERSION: str = "1.0.0"
BASELINE_VERSION: str = "1.0.0"   # tracks statistical baseline data version

# ---------------------------------------------------------------------------
# Layer Weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHT_DETERMINISTIC: float = 0.40
WEIGHT_STATISTICAL: float = 0.35
WEIGHT_NARRATIVE: float = 0.25

# Degraded-mode weights (used when AI times out; narrative weight → 0)
DEGRADED_WEIGHT_DETERMINISTIC: float = 0.55
DEGRADED_WEIGHT_STATISTICAL: float = 0.45

# ---------------------------------------------------------------------------
# Layer 1 – Deterministic thresholds
# ---------------------------------------------------------------------------
SCORE_PER_DETERMINISTIC_SIGNAL: float = 0.15

CLAIM_AMOUNT_THRESHOLDS: Dict[str, float] = {
    "HEALTH": 500_000.0,
    "MOTOR": 200_000.0,
    "REIMBURSEMENT": 300_000.0,
}

ROUND_AMOUNT_MODULUS: float = 10_000.0
ROUND_AMOUNT_FLOOR: float = 50_000.0

MIN_POLICY_NUMBER_LENGTH: int = 8

# ---------------------------------------------------------------------------
# Layer 2 – Statistical baselines
# ---------------------------------------------------------------------------
STATISTICAL_BASELINES: Dict[str, Dict[str, float]] = {
    "HEALTH": {"mean": 50_000.0, "std": 25_000.0},
    "MOTOR":  {"mean": 30_000.0, "std": 15_000.0},
    "REIMBURSEMENT": {"mean": 40_000.0, "std": 20_000.0},
}

Z_SCORE_THRESHOLD: float = 2.5
Z_SCORE_ANOMALY_CONTRIBUTION: float = 0.30

# Behavioral thresholds
HIGH_CLAIM_FREQUENCY_THRESHOLD: int = 3
PRIOR_FRAUD_FLAGS_THRESHOLD: int = 1
DAYS_TO_EXPIRY_THRESHOLD: int = 30

FREQUENCY_RISK_SCORE: float = 0.35
PRIOR_FRAUD_RISK_SCORE: float = 0.40
NEAR_EXPIRY_RISK_SCORE: float = 0.20
DORMANCY_RISK_SCORE: float = 0.15

STATISTICAL_SEED: int = 42   # deterministic seeding for reproducibility

# ---------------------------------------------------------------------------
# Layer 3 – Narrative / AI
# ---------------------------------------------------------------------------
ENABLE_EXTERNAL_AI: bool = False
AI_TIMEOUT_SECONDS: float = 5.0
NARRATIVE_DEFAULT_SCORE: float = 0.0   # fallback score when AI fails

# ---------------------------------------------------------------------------
# Privacy
# ---------------------------------------------------------------------------
DEFAULT_PRIVACY_MODE: str = "balanced"   # strict | balanced | raw

# ---------------------------------------------------------------------------
# Risk level boundaries (used in narrative layer)
# ---------------------------------------------------------------------------
RISK_LEVEL_BOUNDARIES: Dict[str, float] = {
    "VERY_HIGH": 0.85,
    "HIGH": 0.70,
    "MODERATE": 0.50,
    "LOW": 0.30,
    # anything below 0.30 → MINIMAL
}
