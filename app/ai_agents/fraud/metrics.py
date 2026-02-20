"""Prometheus metrics for fraud engine."""
from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram

    FRAUD_ANALYSES_TOTAL = Counter(
        "fraud_analyses_total", "Total fraud analyses run", ["risk_level"]
    )
    FRAUD_SCORE_HISTOGRAM = Histogram(
        "fraud_score", "Distribution of fraud scores", buckets=[.1,.2,.3,.4,.5,.6,.7,.8,.9,1.0]
    )
    LAYER_LATENCY = Histogram(
        "fraud_layer_latency_seconds", "Per-layer latency", ["layer"]
    )
    HIGH_RISK_GAUGE = Gauge("fraud_high_risk_current", "Claims currently at HIGH/VERY_HIGH risk")

    def record_analysis(score: float, risk_level: str) -> None:
        FRAUD_ANALYSES_TOTAL.labels(risk_level=risk_level).inc()
        FRAUD_SCORE_HISTOGRAM.observe(score)
        if risk_level in ("HIGH", "VERY_HIGH"):
            HIGH_RISK_GAUGE.inc()

except ImportError:
    def record_analysis(score: float, risk_level: str) -> None:
        pass
