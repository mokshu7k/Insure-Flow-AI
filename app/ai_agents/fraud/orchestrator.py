"""
Fraud Engine Orchestrator — coordinates all 6 layers and produces final assessment.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai_agents.fraud import (
    aggregator,
    layer1_deterministic,
    layer2_statistical,
    layer3_narrative,
    layer4_document,
    layer5_network,
    layer6_ml,
)
from app.ai_agents.fraud.config import cfg
from app.ai_agents.fraud.metrics import LAYER_LATENCY, record_analysis
from app.ai_agents.fraud.privacy import sanitize

logger = logging.getLogger(__name__)


@dataclass
class FraudEngineResponse:
    fraud_score: float
    risk_level: str
    layer_scores: dict[str, float]
    layer_details: dict[str, Any]          # Full per-layer output (flags, method, ai_degraded)
    deterministic_signals: list[str] = field(default_factory=list)
    statistical_signals: list[str] = field(default_factory=list)
    behavioral_flags: list[str] = field(default_factory=list)
    document_flags: list[str] = field(default_factory=list)
    network_flags: list[str] = field(default_factory=list)
    explanation_text: str = ""
    feature_snapshot: dict[str, Any] = field(default_factory=dict)
    config_version: str = cfg.VERSION
    ai_degraded_mode: bool = False
    ml_model_used: bool = False


class FraudEngineOrchestrator:
    """Coordinates the 6-layer fraud analysis pipeline."""

    def analyze(self, claim_context: dict[str, Any], privacy_mode: str = "strict") -> FraudEngineResponse:
        logger.info("Starting fraud analysis for claim=%s", claim_context.get("claim_id"))
        layer_results: dict[str, dict] = {}

        for layer_name, layer_fn in [
            ("deterministic", layer1_deterministic.run),
            ("statistical",   layer2_statistical.run),
            ("document",      layer4_document.run),
            ("network",       layer5_network.run),
            ("ml",            layer6_ml.run),
        ]:
            t0 = time.perf_counter()
            try:
                layer_results[layer_name] = layer_fn(claim_context)
            except Exception as exc:
                logger.warning("Layer %s failed: %s", layer_name, exc)
                layer_results[layer_name] = {"score": 0.0, "flags": [], "error": str(exc)}
            finally:
                try:
                    LAYER_LATENCY.labels(layer=layer_name).observe(time.perf_counter() - t0)
                except Exception:
                    pass

        # Layer 3 — narrative (Gemini)
        from app.config import settings
        t0 = time.perf_counter()
        try:
            layer_results["narrative"] = layer3_narrative.run(
                claim_context, llm_enabled=settings.ENABLE_EXTERNAL_AI
            )
        except Exception as exc:
            logger.warning("Narrative layer failed: %s", exc)
            layer_results["narrative"] = {"score": 0.0, "flags": [], "ai_degraded": True}
        finally:
            try:
                LAYER_LATENCY.labels(layer="narrative").observe(time.perf_counter() - t0)
            except Exception:
                pass

        # Aggregate scores
        agg = aggregator.aggregate(layer_results)
        
        # CRITICAL OVERRIDE: If document validation flagged as critical, override final score
        doc_validation = claim_context.get("document_validation", {})
        if doc_validation.get("validation_status") == "flagged_critical":
            logger.warning("Document flagged as CRITICAL - overriding fraud score to 0.95")
            agg["final_score"] = 0.95
            agg["risk_level"] = "VERY_HIGH"
            all_flags = ["DOCUMENT_CRITICAL_OVERRIDE"] + agg["all_flags"]
        else:
            all_flags = agg["all_flags"]

        # Build human-readable explanation via Gemini (or fallback to string concat)
        explanation = self._build_explanation(
            layer_results=layer_results,
            agg=agg,
            claim_context=claim_context,
        )

        try:
            record_analysis(agg["final_score"], agg["risk_level"])
        except Exception:
            pass

        return FraudEngineResponse(
            fraud_score=agg["final_score"],
            risk_level=agg["risk_level"],
            layer_scores=agg["layer_scores"],
            layer_details=layer_results,            # Full per-layer raw output
            deterministic_signals=layer_results.get("deterministic", {}).get("flags", []),
            statistical_signals=layer_results.get("statistical",   {}).get("signals", []),
            behavioral_flags=layer_results.get("narrative",     {}).get("flags", []),
            document_flags=layer_results.get("document",      {}).get("flags", []),
            network_flags=layer_results.get("network",       {}).get("flags", []),
            explanation_text=explanation,
            feature_snapshot=sanitize(claim_context, mode=privacy_mode),
            ai_degraded_mode=layer_results.get("narrative", {}).get("ai_degraded", True),
            ml_model_used=layer_results.get("ml", {}).get("model_used", False),
        )

    # ── Explanation ────────────────────────────────────────────────────────────
    def _build_explanation(
        self,
        layer_results: dict[str, dict],
        agg: dict[str, Any],
        claim_context: dict[str, Any],
    ) -> str:
        """Try Gemini first for a narrative explanation; fallback to rule-based string."""
        try:
            return self._gemini_explanation(layer_results, agg, claim_context)
        except Exception as exc:
            logger.warning("Gemini explanation failed, using fallback: %s", exc)
            return self._fallback_explanation(agg["all_flags"], agg["final_score"], agg["risk_level"])

    def _gemini_explanation(
        self,
        layer_results: dict[str, dict],
        agg: dict[str, Any],
        claim_context: dict[str, Any],
    ) -> str:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from app.config import settings

        if not settings.GCP_API_KEY:
            raise ValueError("No GCP_API_KEY")

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GCP_API_KEY,
            temperature=0.2,
        )

        # Summarise signals for the prompt (keep it concise)
        all_flags = agg["all_flags"]
        layer_scores_str = ", ".join(
            f"{k}={v:.2f}" for k, v in agg["layer_scores"].items()
        )

        prompt = (
            f"You are an insurance fraud analyst. Write a concise 2-3 sentence explanation "
            f"for why this claim received a fraud score of {agg['final_score']:.2f} "
            f"({agg['risk_level']} risk). "
            f"Layer scores: {layer_scores_str}. "
            f"Signals detected: {'; '.join(all_flags[:10]) if all_flags else 'none'}. "
            f"Claim type: {claim_context.get('claim_type', 'unknown')}. "
            f"Do NOT use JSON. Plain English only."
        )

        response = llm.invoke(prompt)
        return response.content.strip()

    def _fallback_explanation(self, flags: list[str], score: float, risk_level: str) -> str:
        if not flags:
            return f"No significant fraud indicators detected. Risk: {risk_level} (score={score:.2f})."
        flag_summary = "; ".join(flags[:5])
        return (
            f"Fraud score: {score:.2f} ({risk_level}). "
            f"Primary signals: {flag_summary}."
            + (" [+more]" if len(flags) > 5 else "")
        )
