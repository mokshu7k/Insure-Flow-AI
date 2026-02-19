"""
Fraud Engine Configuration
All thresholds, weights, and tuning constants live here.
No magic numbers allowed in engine logic.
"""
from typing import Dict


# ---------------------------------------------------------------------------
# Versioning – embedded in every FraudAssessmentResponse for traceability
# ---------------------------------------------------------------------------
CONFIG_VERSION: str = "2.0.0"
BASELINE_VERSION: str = "1.0.0"   # tracks statistical baseline data version

# ---------------------------------------------------------------------------
# Layer Weights (must sum to 1.0)
# ---------------------------------------------------------------------------
WEIGHT_DETERMINISTIC: float = 0.30
WEIGHT_STATISTICAL: float = 0.25
WEIGHT_NARRATIVE: float = 0.15
WEIGHT_DOCUMENT: float = 0.15
WEIGHT_NETWORK: float = 0.10
WEIGHT_ML: float = 0.05

# Degraded-mode weights (used when AI / ML times out; only L1+L2+L4 remain)
DEGRADED_WEIGHT_DETERMINISTIC: float = 0.45
DEGRADED_WEIGHT_STATISTICAL: float = 0.35
DEGRADED_WEIGHT_DOCUMENT: float = 0.20

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
DORMANCY_DAYS_THRESHOLD: int = 365   # >1 year of inactivity triggers CLAIM_AFTER_LONG_DORMANCY

FREQUENCY_RISK_SCORE: float = 0.35
PRIOR_FRAUD_RISK_SCORE: float = 0.40
NEAR_EXPIRY_RISK_SCORE: float = 0.20
DORMANCY_RISK_SCORE: float = 0.15

STATISTICAL_SEED: int = 42   # deterministic seeding for reproducibility

# ---------------------------------------------------------------------------
# Layer 3 – Narrative / AI
# ---------------------------------------------------------------------------
ENABLE_EXTERNAL_AI: bool = False
AI_TIMEOUT_SECONDS: float = 10.0
NARRATIVE_DEFAULT_SCORE: float = 0.0   # fallback score when AI fails

# Ollama (self-hosted LLM, zero data egress)
EXTERNAL_AI_BASE_URL: str = "http://localhost:11434"
EXTERNAL_AI_MODEL: str = "mistral"
EXTERNAL_AI_MAX_TOKENS: int = 512

# Circuit breaker: open after N consecutive failures, reset after RESET_TIMEOUT seconds
CIRCUIT_BREAKER_FAIL_MAX: int = 3
CIRCUIT_BREAKER_RESET_TIMEOUT: int = 60   # seconds

# ---------------------------------------------------------------------------
# Layer 4 – Document Fraud
# ---------------------------------------------------------------------------
OCR_CONFIDENCE_THRESHOLD: float = 0.60        # below this → low-confidence signal
DOCUMENT_DATE_DRIFT_DAYS: int = 30            # incident date vs doc creation date tolerance
DUPLICATE_INVOICE_SCORE: float = 0.50
LOW_OCR_CONFIDENCE_SCORE: float = 0.25
DOCUMENT_DATE_INCONSISTENCY_SCORE: float = 0.30
MISSING_REQUIRED_DOCUMENT_SCORE: float = 0.20

REQUIRED_DOCUMENTS_BY_TYPE: Dict[str, list] = {
    "HEALTH": ["INVOICE", "DISCHARGE_SUMMARY"],
    "MOTOR":  ["ESTIMATE", "POLICE_REPORT"],
    "REIMBURSEMENT": ["INVOICE"],
}

# ---------------------------------------------------------------------------
# Layer 5 – Network / Graph Analysis
# ---------------------------------------------------------------------------
PROVIDER_HIGH_CLAIM_COUNT_THRESHOLD: int = 5    # N claims in window
PROVIDER_HIGH_CLAIM_WINDOW_DAYS: int = 30
PROVIDER_FRAUD_RATE_THRESHOLD: float = 0.40     # >40 % of provider's claims are high-risk
HIGH_RISK_PROVIDER_SCORE: float = 0.40
SHARED_PROVIDER_CLUSTER_SCORE: float = 0.25

# ---------------------------------------------------------------------------
# Layer 6 – ML (Isolation Forest)
# ---------------------------------------------------------------------------
ML_MODEL_PATH: str = "models/fraud_isolation_forest.pkl"
ML_SCALER_PATH: str = "models/fraud_scaler.pkl"
ML_CONTAMINATION: float = 0.10        # expected ~10 % anomalies in training data
ML_N_ESTIMATORS: int = 200
ML_RANDOM_STATE: int = 42
ML_ANOMALY_SCORE_SCALE: float = 0.50  # max contribution from ML layer to fraud score

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