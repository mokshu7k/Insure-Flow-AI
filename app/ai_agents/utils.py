"""
AI Agents Utilities
Shared helpers for the multi-agent fraud detection system
"""
from typing import Dict, Any, List
import math


def normalize_score(raw_score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Normalize a score to [0, 1] range.

    Args:
        raw_score: Raw score value
        min_val: Minimum possible value
        max_val: Maximum possible value

    Returns:
        Normalized score in [0.0, 1.0]
    """
    if max_val == min_val:
        return 0.0
    normalized = (raw_score - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, normalized))


def compute_z_score(value: float, mean: float, std: float) -> float:
    """
    Compute standard z-score for anomaly detection.

    Args:
        value: Observed value
        mean: Population mean
        std: Population standard deviation

    Returns:
        Z-score (unsigned)
    """
    if std == 0:
        return 0.0
    return abs((value - mean) / std)


def weighted_aggregate(scores: List[tuple]) -> float:
    """
    Compute weighted aggregate score.

    Args:
        scores: List of (score, weight) tuples

    Returns:
        Weighted aggregate in [0.0, 1.0]
    """
    total_weight = sum(w for _, w in scores)
    if total_weight == 0:
        return 0.0

    weighted_sum = sum(s * w for s, w in scores)
    return min(1.0, weighted_sum / total_weight)


def sigmoid_scale(value: float, steepness: float = 10.0, midpoint: float = 0.5) -> float:
    """
    Apply sigmoid scaling to convert a linear score to probability-like output.
    Makes the fraud score more sensitive around the threshold.

    Args:
        value: Input value [0, 1]
        steepness: Controls curve steepness
        midpoint: Inflection point

    Returns:
        Scaled value [0, 1]
    """
    return 1.0 / (1.0 + math.exp(-steepness * (value - midpoint)))


def extract_claim_features(claim_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract normalized numerical features from claim context.
    Used for statistical analysis by agents.

    Args:
        claim_context: Raw claim context dict

    Returns:
        Feature dictionary
    """
    features = {}

    # Amount features
    amount = claim_context.get("claim_amount", 0)
    features["claim_amount"] = amount
    features["amount_log"] = math.log1p(amount)  # Log scale for large amounts
    features["amount_thousands"] = amount / 1000.0

    # Claim type encoding
    claim_type = claim_context.get("claim_type", "OTHER")
    features["is_health"] = 1 if claim_type == "HEALTH" else 0
    features["is_motor"] = 1 if claim_type == "MOTOR" else 0
    features["is_reimbursement"] = 1 if claim_type == "REIMBURSEMENT" else 0

    # Policy number length (short = potentially fake)
    policy = claim_context.get("policy_number", "")
    features["policy_length"] = len(policy)

    return features