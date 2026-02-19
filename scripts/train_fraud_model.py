"""
Train Fraud Isolation Forest Model
===================================
Trains and saves an IsolationForest model using:
  1. Your existing database records (real claim data)
  2. Synthetic data generated from the configured claim-type distributions

Usage
-----
    python scripts/train_fraud_model.py

Options
-------
    --samples N        Number of synthetic samples to generate (default: 5000)
    --contamination F  Fraction of expected anomalies (default: 0.10)
    --from-db          Also include real claims from the database in training

Why Isolation Forest without a Kaggle dataset?
----------------------------------------------
Isolation Forest is UNSUPERVISED – it does not need fraud labels.
It learns the *normal* region of the feature space from the bulk of data,
then anomalies are the points isolated in few splits.

Bootstrap behaviour:
  - First run: all synthetic data. The model learns the shape of your config
    distributions and will flag numerical outliers.
  - After 100+ real claims: run with --from-db to incorporate real patterns.
  - Scheduled retraining (weekly via Celery beat) refines the model over time.
"""
import argparse
import os
import sys
import random

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ai_agents.fraud import config as cfg
from app.ai_agents.fraud.ml_model import build_feature_vector, get_feature_names, CLAIM_TYPE_MAP


def generate_synthetic_samples(n_samples: int, rng: np.random.Generator) -> np.ndarray:
    """
    Generate a synthetic training corpus mirroring the configured distributions.

    ~88% normal claims, ~12% anomalous (seeded fraud-like patterns).
    """
    rows = []
    claim_types = list(cfg.STATISTICAL_BASELINES.keys())
    n_anomalous = int(n_samples * cfg.ML_CONTAMINATION)
    n_normal = n_samples - n_anomalous

    # ── Normal claims ─────────────────────────────────────────────────
    for _ in range(n_normal):
        ct = rng.choice(claim_types)
        baseline = cfg.STATISTICAL_BASELINES[ct]
        amount = max(1.0, rng.normal(baseline["mean"], baseline["std"]))
        context = {
            "claim_amount":            amount,
            "claim_type":              ct,
            "recent_claim_count":      int(rng.integers(0, 3)),
            "prior_fraud_flags":       0,
            "days_to_policy_expiry":   int(rng.integers(60, 730)),
            "total_claim_amount_90d":  amount * rng.uniform(0.5, 2.0),
        }
        rows.append(build_feature_vector(context))

    # ── Anomalous claims (fraud-like patterns) ────────────────────────
    for _ in range(n_anomalous):
        ct = rng.choice(claim_types)
        baseline = cfg.STATISTICAL_BASELINES[ct]
        # Anomalies: extreme amounts, high frequency, near-expiry, prior flags
        fraud_type = rng.choice(["extreme_amount", "high_frequency", "near_expiry", "prior_fraud"])
        if fraud_type == "extreme_amount":
            amount = baseline["mean"] + baseline["std"] * rng.uniform(3.5, 8.0)
        elif fraud_type == "high_frequency":
            amount = baseline["mean"] * rng.uniform(0.8, 1.2)
        elif fraud_type == "near_expiry":
            amount = baseline["mean"] * rng.uniform(1.5, 3.0)
        else:
            amount = baseline["mean"] * rng.uniform(2.0, 4.0)

        context = {
            "claim_amount":            max(1.0, amount),
            "claim_type":              ct,
            "recent_claim_count":      int(rng.integers(3, 10)) if fraud_type == "high_frequency" else 1,
            "prior_fraud_flags":       int(rng.integers(1, 5)) if fraud_type == "prior_fraud" else 0,
            "days_to_policy_expiry":   int(rng.integers(1, 30)) if fraud_type == "near_expiry" else int(rng.integers(30, 365)),
            "total_claim_amount_90d":  amount * rng.uniform(3.0, 6.0),
        }
        rows.append(build_feature_vector(context))

    X = np.array(rows, dtype=np.float64)
    # Shuffle so normal and anomalous examples are interleaved
    rng.shuffle(X)
    return X


def load_db_samples() -> np.ndarray:
    """Load feature vectors from real claims currently in the database."""
    from app.db.session import SessionLocal
    from app.models.claim import Claim
    from app.models.user_fraud_profile import UserFraudProfile
    from datetime import date

    db = SessionLocal()
    rows = []
    try:
        claims = db.query(Claim).all()
        for claim in claims:
            profile = (
                db.query(UserFraudProfile)
                .filter(UserFraudProfile.user_id == claim.user_id)
                .first()
            )
            days_expiry = 365
            if claim.policy_expiry_date:
                days_expiry = (claim.policy_expiry_date - date.today()).days

            context = {
                "claim_amount":            claim.claim_amount or 0.0,
                "claim_type":              claim.claim_type or "HEALTH",
                "recent_claim_count":      getattr(profile, "recent_claim_count", 0) or 0,
                "prior_fraud_flags":       getattr(profile, "prior_fraud_flags", 0) or 0,
                "days_to_policy_expiry":   days_expiry,
                "total_claim_amount_90d":  getattr(profile, "total_claim_amount_90d", 0.0) or 0.0,
            }
            rows.append(build_feature_vector(context))
    finally:
        db.close()

    if not rows:
        print("  (no DB claims found – using synthetic data only)")
        return np.empty((0, 7))

    return np.array(rows, dtype=np.float64)


def train(n_samples: int, contamination: float, include_db: bool) -> None:
    """Full training pipeline: data → scaler → IsolationForest → save."""
    os.makedirs(os.path.dirname(cfg.ML_MODEL_PATH), exist_ok=True)

    rng = np.random.default_rng(cfg.ML_RANDOM_STATE)

    print(f"Generating {n_samples} synthetic training samples...")
    X = generate_synthetic_samples(n_samples, rng)

    if include_db:
        print("Loading real claims from database...")
        X_db = load_db_samples()
        if len(X_db) > 0:
            X = np.vstack([X, X_db])
            print(f"  + {len(X_db)} real claim rows. Total dataset: {len(X)} rows.")

    print(f"Fitting StandardScaler on {len(X)} samples...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print(
        f"Training IsolationForest (n_estimators={cfg.ML_N_ESTIMATORS}, "
        f"contamination={contamination})..."
    )
    model = IsolationForest(
        n_estimators=cfg.ML_N_ESTIMATORS,
        contamination=contamination,
        random_state=cfg.ML_RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    joblib.dump(scaler, cfg.ML_SCALER_PATH)
    joblib.dump(model, cfg.ML_MODEL_PATH)

    # Quick sanity check
    predictions = model.predict(X_scaled)
    n_anomalies = (predictions == -1).sum()
    print(
        f"\n✓ Model trained and saved.\n"
        f"  Model   : {cfg.ML_MODEL_PATH}\n"
        f"  Scaler  : {cfg.ML_SCALER_PATH}\n"
        f"  Features: {get_feature_names()}\n"
        f"  Samples : {len(X)}\n"
        f"  Flagged as anomaly on training set: {n_anomalies} "
        f"({100 * n_anomalies / len(X):.1f}%)\n"
    )
    print(
        "Run 'python scripts/train_fraud_model.py --from-db' after accumulating "
        "real claims to incorporate real-world patterns.\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the fraud IsolationForest model")
    parser.add_argument("--samples", type=int, default=5000,
                        help="Number of synthetic training samples (default: 5000)")
    parser.add_argument("--contamination", type=float, default=cfg.ML_CONTAMINATION,
                        help="Expected anomaly fraction (default: cfg.ML_CONTAMINATION)")
    parser.add_argument("--from-db", action="store_true",
                        help="Also include real claims from the database")
    args = parser.parse_args()
    train(args.samples, args.contamination, args.from_db)
