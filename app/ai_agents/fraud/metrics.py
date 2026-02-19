"""
Fraud Engine – Prometheus Metrics
All instrumentation is defined here and imported by the orchestrator.

Metrics exported:
    fraud_score_distribution        – Histogram of final fraud scores by claim type.
    fraud_layer_latency_seconds     – Per-layer execution time histogram.
    fraud_ai_degraded_total         – Counter of analyses run in AI-degraded mode.
    fraud_high_risk_total           – Counter of high-risk detections by claim type.
    fraud_ml_unavailable_total      – Counter of times ML layer was unavailable.
    fraud_engine_analysis_total     – Total analyses performed (labels: claim_type).
    fraud_circuit_breaker_open_total– Circuit-breaker open-event counter.
"""
from __future__ import annotations

from prometheus_client import Counter, Histogram

# ---------------------------------------------------------------------------
# Final score distribution (bucket boundaries chosen for insurance domain)
# ---------------------------------------------------------------------------
FRAUD_SCORE_HISTOGRAM = Histogram(
    name="fraud_score_distribution",
    documentation="Distribution of final fraud scores produced by the engine",
    labelnames=["claim_type"],
    buckets=[0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00],
)

# ---------------------------------------------------------------------------
# Per-layer latency (seconds)
# Labels: layer = "deterministic" | "statistical" | "narrative" |
#                 "document" | "network" | "ml" | "aggregation"
# ---------------------------------------------------------------------------
FRAUD_LAYER_LATENCY = Histogram(
    name="fraud_layer_latency_seconds",
    documentation="Wall-clock execution time of each fraud-engine layer",
    labelnames=["layer"],
    buckets=[0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.000, 5.000],
)

# ---------------------------------------------------------------------------
# AI degraded-mode counter
# ---------------------------------------------------------------------------
FRAUD_AI_DEGRADED_TOTAL = Counter(
    name="fraud_ai_degraded_total",
    documentation=(
        "Number of fraud analyses run in AI-degraded mode "
        "(narrative layer timed out or circuit breaker open)"
    ),
)

# ---------------------------------------------------------------------------
# High-risk detection counter
# ---------------------------------------------------------------------------
FRAUD_HIGH_RISK_TOTAL = Counter(
    name="fraud_high_risk_total",
    documentation="Number of fraud assessments with risk_level HIGH or VERY_HIGH",
    labelnames=["claim_type"],
)

# ---------------------------------------------------------------------------
# ML unavailability counter
# ---------------------------------------------------------------------------
FRAUD_ML_UNAVAILABLE_TOTAL = Counter(
    name="fraud_ml_unavailable_total",
    documentation="Number of analyses where the ML (Isolation Forest) model was not available",
)

# ---------------------------------------------------------------------------
# Total analyses
# ---------------------------------------------------------------------------
FRAUD_ENGINE_ANALYSIS_TOTAL = Counter(
    name="fraud_engine_analysis_total",
    documentation="Total number of fraud-engine analyses performed",
    labelnames=["claim_type"],
)

# ---------------------------------------------------------------------------
# Circuit-breaker open events
# ---------------------------------------------------------------------------
FRAUD_CIRCUIT_BREAKER_OPEN_TOTAL = Counter(
    name="fraud_circuit_breaker_open_total",
    documentation="Number of times the Ollama circuit breaker was opened",
)
