"""
Unit Tests: Fraud Detection Agents
All tests are deterministic — no randomness in agents.
"""
import pytest
from app.ai_agents.orchestrator import FraudOrchestrator
from app.ai_agents.rule_agent import RuleAgent
from app.ai_agents.anomaly_agent import AnomalyAgent
from app.ai_agents.behavior_agent import BehaviorAgent
from app.ai_agents.explanation_agent import ExplanationAgent


@pytest.fixture
def low_risk_claim():
    return {
        "claim_id": "test-001",
        "policy_number": "POL-2024-12345",
        "claim_type": "HEALTH",
        "claim_amount": 30_000.0,
        "user_id": "user-001",
        "recent_claim_count": 0,
        "prior_fraud_flags": 0,
    }


@pytest.fixture
def high_risk_claim():
    return {
        "claim_id": "test-002",
        "policy_number": "POL",          # too short
        "claim_type": "HEALTH",
        "claim_amount": 900_000.0,       # extreme amount
        "user_id": "user-002",
        "recent_claim_count": 5,
        "prior_fraud_flags": 2,
    }


class TestRuleAgent:
    def test_no_flags_for_low_risk(self, low_risk_claim):
        flags = RuleAgent().validate(low_risk_claim)
        assert "AMOUNT_EXCEEDS_THRESHOLD" not in flags

    def test_flags_high_health_amount(self, high_risk_claim):
        flags = RuleAgent().validate(high_risk_claim)
        assert "AMOUNT_EXCEEDS_THRESHOLD" in flags

    def test_flags_short_policy(self, high_risk_claim):
        flags = RuleAgent().validate(high_risk_claim)
        assert "INVALID_POLICY_FORMAT" in flags

    def test_motor_threshold(self):
        flags = RuleAgent().validate({
            "policy_number": "POL-MOTOR-123",
            "claim_type": "MOTOR",
            "claim_amount": 250_000.0,
        })
        assert "AMOUNT_EXCEEDS_THRESHOLD" in flags

    def test_round_amount_flag(self):
        flags = RuleAgent().validate({
            "policy_number": "POL-12345678",
            "claim_type": "HEALTH",
            "claim_amount": 100_000.0,
        })
        assert "SUSPICIOUSLY_ROUND_AMOUNT" in flags


class TestAnomalyAgent:
    def test_returns_correct_types(self, low_risk_claim):
        flags, score = AnomalyAgent().detect_anomalies(low_risk_claim)
        assert isinstance(flags, list)
        assert 0.0 <= score <= 1.0

    def test_extreme_amount_is_outlier(self):
        # 900k is (900000-50000)/25000 = 34 z-score for HEALTH baseline → must flag
        flags, score = AnomalyAgent().detect_anomalies({
            "claim_type": "HEALTH",
            "claim_amount": 900_000.0,
            "policy_number": "POL-VALID-12345",
        })
        assert "AMOUNT_STATISTICAL_OUTLIER" in flags
        assert score > 0.0

    def test_normal_amount_no_outlier(self, low_risk_claim):
        # 30k is below the 50k mean — z = (50000-30000)/25000 = 0.8 → no flag
        flags, _ = AnomalyAgent().detect_anomalies(low_risk_claim)
        assert "AMOUNT_STATISTICAL_OUTLIER" not in flags

    def test_score_deterministic(self, high_risk_claim):
        # Same input → same output every time (no randomness)
        r1 = AnomalyAgent().detect_anomalies(high_risk_claim)
        r2 = AnomalyAgent().detect_anomalies(high_risk_claim)
        assert r1 == r2


class TestBehaviorAgent:
    def test_no_flags_for_clean_profile(self, low_risk_claim):
        flags, score = BehaviorAgent().analyze_behavior(low_risk_claim)
        assert flags == []
        assert score == 0.0

    def test_high_frequency_flagged(self):
        flags, score = BehaviorAgent().analyze_behavior({
            "claim_type": "HEALTH",
            "claim_amount": 10_000,
            "recent_claim_count": 5,
            "prior_fraud_flags": 0,
        })
        assert "UNUSUALLY_HIGH_CLAIM_FREQUENCY" in flags
        assert score > 0.0

    def test_prior_fraud_flagged(self):
        flags, _ = BehaviorAgent().analyze_behavior({
            "claim_type": "HEALTH",
            "claim_amount": 10_000,
            "recent_claim_count": 0,
            "prior_fraud_flags": 1,
        })
        assert "PREVIOUS_FRAUD_FLAGS_ON_RECORD" in flags

    def test_near_expiry_flagged(self):
        flags, _ = BehaviorAgent().analyze_behavior({
            "claim_type": "HEALTH",
            "claim_amount": 10_000,
            "recent_claim_count": 0,
            "prior_fraud_flags": 0,
            "days_to_policy_expiry": 15,
        })
        assert "CLAIM_NEAR_POLICY_EXPIRY" in flags

    def test_score_deterministic(self, high_risk_claim):
        r1 = BehaviorAgent().analyze_behavior(high_risk_claim)
        r2 = BehaviorAgent().analyze_behavior(high_risk_claim)
        assert r1 == r2


class TestExplanationAgent:
    def test_high_risk_explanation(self):
        exp = ExplanationAgent().generate_explanation(
            fraud_score=0.75,
            rule_flags=["AMOUNT_EXCEEDS_THRESHOLD"],
            anomaly_flags=["AMOUNT_STATISTICAL_OUTLIER"],
            behavior_flags=[],
            claim_context={"claim_amount": 600_000, "claim_type": "HEALTH", "policy_number": "POL-123"},
        )
        assert "HIGH" in exp
        assert "manual" in exp.lower()
        assert len(exp) > 100

    def test_minimal_risk_explanation(self):
        exp = ExplanationAgent().generate_explanation(
            fraud_score=0.05,
            rule_flags=[], anomaly_flags=[], behavior_flags=[],
            claim_context={"claim_amount": 5000, "claim_type": "HEALTH", "policy_number": "POL-99999"},
        )
        assert "MINIMAL" in exp

    def test_all_known_flags_humanize(self):
        agent = ExplanationAgent()
        for flag in [
            "AMOUNT_EXCEEDS_THRESHOLD", "SUSPICIOUSLY_ROUND_AMOUNT",
            "INVALID_POLICY_FORMAT", "AMOUNT_STATISTICAL_OUTLIER",
            "UNUSUALLY_HIGH_CLAIM_FREQUENCY", "PREVIOUS_FRAUD_FLAGS_ON_RECORD",
        ]:
            result = agent._humanize_flag(flag)
            assert isinstance(result, str) and len(result) > 0


class TestFraudOrchestrator:
    def test_returns_valid_result(self, low_risk_claim):
        result = FraudOrchestrator().analyze(low_risk_claim)
        assert 0.0 <= result.fraud_score <= 1.0
        assert isinstance(result.deterministic_flags, list)
        assert isinstance(result.statistical_flags, list)
        assert isinstance(result.behavioral_flags, list)
        assert len(result.explanation) > 0
        assert "agent_scores" in result.model_dump()

    def test_high_risk_scores_higher(self, low_risk_claim, high_risk_claim):
        orch = FraudOrchestrator()
        assert orch.analyze(high_risk_claim).fraud_score > orch.analyze(low_risk_claim).fraud_score

    def test_score_bounded(self, high_risk_claim):
        result = FraudOrchestrator().analyze(high_risk_claim)
        assert result.fraud_score <= 1.0
        assert result.fraud_score >= 0.0

    def test_deterministic(self, high_risk_claim):
        orch = FraudOrchestrator()
        r1 = orch.analyze(high_risk_claim)
        r2 = orch.analyze(high_risk_claim)
        assert r1.fraud_score == r2.fraud_score
        assert r1.deterministic_flags == r2.deterministic_flags