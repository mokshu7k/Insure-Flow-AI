"""Fraud engine configuration — boundaries, weights, and constants."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FraudEngineConfig:
    VERSION: str = "2.0.0"

    # Layer weights (must sum to 1.0)
    LAYER_WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "deterministic": 0.25,
        "statistical": 0.20,
        "narrative": 0.15,
        "document": 0.15,
        "network": 0.10,
        "ml": 0.15,
    })

    # Risk level score boundaries
    RISK_LEVEL_BOUNDARIES: dict[str, float] = field(default_factory=lambda: {
        "VERY_HIGH": 0.85,
        "HIGH": 0.70,
        "MEDIUM": 0.50,
        "LOW": 0.30,
        "MINIMAL": 0.0,
    })

    # Deterministic rule thresholds
    MAX_CLAIM_AMOUNT: float = 500_000.0
    MAX_CLAIMS_30D: int = 5
    DUPLICATE_WINDOW_DAYS: int = 7

    # Statistical thresholds
    AMOUNT_ZSCORE_THRESHOLD: float = 2.5
    FREQUENCY_ZSCORE_THRESHOLD: float = 2.0


cfg = FraudEngineConfig()
