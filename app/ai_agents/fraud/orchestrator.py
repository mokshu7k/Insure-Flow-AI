"""
Fraud Engine Orchestrator — LLM-powered layer scoring with rule-based fallback.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai_agents.fraud.config import cfg
from app.ai_agents.fraud.privacy import sanitize

logger = logging.getLogger(__name__)

# Layer display names for the prompt
LAYER_NAMES = ["deterministic", "statistical", "narrative", "document", "network", "ml"]


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
    """LLM-powered fraud analysis — Gemini decides per-layer scores + explanation."""

    def analyze(self, claim_context: dict[str, Any], privacy_mode: str = "strict") -> FraudEngineResponse:
        logger.info("Starting fraud analysis for claim=%s", claim_context.get("claim_id"))

        try:
            return self._llm_analyze(claim_context, privacy_mode)
        except Exception as exc:
            logger.warning("LLM fraud analysis failed (%s), using rule-based fallback", exc)
            return self._fallback_analyze(claim_context, privacy_mode)

    # ── LLM-based analysis ────────────────────────────────────────────────────
    def _llm_analyze(self, claim_context: dict[str, Any], privacy_mode: str) -> FraudEngineResponse:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from app.config import settings

        if not settings.GCP_API_KEY:
            raise ValueError("No GCP_API_KEY configured")

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GCP_API_KEY,
            temperature=0.3,
            max_output_tokens=5000,
        )

        # Build a clean summary of the claim for the LLM
        doc_validation = claim_context.get("document_validation", {})
        extracted = claim_context.get("extracted_data", {})

        prompt = f"""You are an expert insurance fraud scoring AI. Your ONLY job is to assign numerical fraud risk scores to each detection layer. You are NOT writing a report.

CLAIM DATA:
- Claim ID: {claim_context.get('claim_id')}
- Type: {claim_context.get('claim_type', 'unknown')}
- Amount: {claim_context.get('claim_amount', 0)}
- Policy: {claim_context.get('policy_number', 'unknown')}
- Description: {claim_context.get('description', 'none')[:500]}
- Filed: {claim_context.get('claim_created_at', 'unknown')}

CLAIMANT HISTORY:
- Claims in last 30 days: {claim_context.get('recent_claims_30d', 0)}
- Total claimed in 90 days: {claim_context.get('total_claim_amount_90d', 0)}
- Previous fraud flags: {claim_context.get('fraud_flag_count', 0)}

DOCUMENT DATA:
- Extracted fields: {json.dumps(extracted, default=str)[:800] if extracted else 'none'}
- Validation status: {doc_validation.get('validation_status', 'not_validated')}
- Validation reason: {doc_validation.get('validation_reason', 'none')}
- Document fraud weight: {doc_validation.get('fraud_signal_weight', 0)}

TASK: Score fraud risk from 0.0 (clean) to 1.0 (fraudulent) for each layer. Keep flag strings SHORT (under 60 chars each, no special characters, no curly braces).

Layers:
1. deterministic - Rule violations (amount limits, frequency, duplicates)
2. statistical - Statistical anomalies (unusual amounts, patterns)
3. narrative - Description consistency and red flags
4. document - Document quality, missing fields, tampering signs
5. network - Connections to known fraud patterns
6. ml - Overall behavioral pattern signals

Respond with ONLY this JSON object, nothing else. No markdown, no backticks, no extra text. All strings must be on a single line:
{{"layers":{{"deterministic":{{"score":0.0,"flags":[]}},"statistical":{{"score":0.0,"flags":[]}},"narrative":{{"score":0.0,"flags":[]}},"document":{{"score":0.0,"flags":[]}},"network":{{"score":0.0,"flags":[]}},"ml":{{"score":0.0,"flags":[]}}}},"explanation":"One short sentence summarizing the risk. See the full Claim Report for detailed analysis."}}"""

        t0 = time.perf_counter()
        response = llm.invoke(prompt)
        elapsed = time.perf_counter() - t0
        logger.info("LLM fraud analysis completed in %.2fs", elapsed)

        content = response.content
        if isinstance(content, list):
            content = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            ).strip()

        # Robust JSON extraction — handle code fences, extra text, etc.
        import re
        content = content.strip()
        logger.info("LLM fraud raw response (first 1000 chars): %s", content[:1000])

        # Step 1: Strip markdown code fences if present
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL)
        if fence_match:
            content = fence_match.group(1).strip()
        else:
            # Find outermost JSON object
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start != -1 and brace_end != -1:
                content = content[brace_start:brace_end + 1]

        # Step 2: Attempt multiple parsing strategies
        parsed = None

        # Strategy A: direct parse
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            pass

        # Strategy B: collapse all whitespace (newlines, tabs) to single spaces
        if parsed is None:
            try:
                cleaned = re.sub(r'\s+', ' ', content)
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        # Strategy C: fix common LLM issues — trailing commas, single quotes
        if parsed is None:
            try:
                fixed = re.sub(r'\s+', ' ', content)
                fixed = re.sub(r',\s*}', '}', fixed)   # trailing comma before }
                fixed = re.sub(r',\s*]', ']', fixed)   # trailing comma before ]
                fixed = fixed.replace("'", '"')          # single quotes to double
                parsed = json.loads(fixed)
            except json.JSONDecodeError:
                pass

        # Strategy D: use ast.literal_eval as last resort for Python dict syntax
        if parsed is None:
            try:
                import ast
                parsed = ast.literal_eval(content)
            except (ValueError, SyntaxError):
                pass

        if parsed is None:
            raise ValueError(f"Could not parse LLM response as JSON. Raw (first 300): {content[:300]}")
        layers = parsed["layers"]
        explanation = parsed.get("explanation", "")

        # Ensure explanation references the deep report
        if "claim report" not in explanation.lower():
            explanation = explanation.rstrip(". ") + ". See the full Claim Report for detailed analysis."

        # Build layer_scores and layer_details in the format the frontend expects
        layer_scores: dict[str, Any] = {}
        layer_details: dict[str, dict] = {}
        all_flags: list[str] = []
        weighted_total = 0.0
        weights = cfg.LAYER_WEIGHTS

        for name in LAYER_NAMES:
            layer_data = layers.get(name, {"score": 0.0, "flags": []})
            score = max(0.0, min(1.0, float(layer_data.get("score", 0.0))))
            flags = layer_data.get("flags", [])

            layer_scores[name] = {
                "score": score,
                "flags": flags,
                "layer": name,
                "method": "llm",
                "ai_degraded": False,
            }
            layer_details[name] = {
                "score": score,
                "flags": flags,
                "layer": name,
                "method": "llm",
                "ai_degraded": False,
            }
            all_flags.extend(flags)
            weighted_total += score * weights.get(name, 0.0)

        final_score = round(min(weighted_total, 1.0), 4)

        # CRITICAL OVERRIDE: document validation flagged as critical
        doc_validation = claim_context.get("document_validation", {})
        if doc_validation.get("validation_status") == "flagged_critical":
            logger.warning("Document flagged as CRITICAL — overriding fraud score to 0.95")
            final_score = 0.95
            all_flags = ["DOCUMENT_CRITICAL_OVERRIDE"] + all_flags

        risk_level = self._risk_level(final_score)

        try:
            from app.ai_agents.fraud.metrics import record_analysis
            record_analysis(final_score, risk_level)
        except Exception:
            pass

        return FraudEngineResponse(
            fraud_score=final_score,
            risk_level=risk_level,
            layer_scores=layer_scores,
            layer_details=layer_details,
            deterministic_signals=layers.get("deterministic", {}).get("flags", []),
            statistical_signals=layers.get("statistical", {}).get("flags", []),
            behavioral_flags=layers.get("narrative", {}).get("flags", []),
            document_flags=layers.get("document", {}).get("flags", []),
            network_flags=layers.get("network", {}).get("flags", []),
            explanation_text=explanation,
            feature_snapshot=sanitize(claim_context, mode=privacy_mode),
            ai_degraded_mode=False,
            ml_model_used=False,
        )

    # ── Rule-based fallback ───────────────────────────────────────────────────
    def _fallback_analyze(self, claim_context: dict[str, Any], privacy_mode: str) -> FraudEngineResponse:
        """Original rule-based pipeline — used when LLM is unavailable."""
        from app.ai_agents.fraud import (
            aggregator,
            layer1_deterministic,
            layer2_statistical,
            layer3_narrative,
            layer4_document,
            layer5_network,
            layer6_ml,
        )
        from app.ai_agents.fraud.metrics import LAYER_LATENCY

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

        # Layer 3 — narrative
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

        agg = aggregator.aggregate(layer_results)

        # CRITICAL OVERRIDE
        doc_validation = claim_context.get("document_validation", {})
        if doc_validation.get("validation_status") == "flagged_critical":
            agg["final_score"] = 0.95
            agg["risk_level"] = "VERY_HIGH"
            all_flags = ["DOCUMENT_CRITICAL_OVERRIDE"] + agg["all_flags"]
        else:
            all_flags = agg["all_flags"]

        explanation = self._fallback_explanation(all_flags, agg["final_score"], agg["risk_level"])

        try:
            from app.ai_agents.fraud.metrics import record_analysis
            record_analysis(agg["final_score"], agg["risk_level"])
        except Exception:
            pass

        return FraudEngineResponse(
            fraud_score=agg["final_score"],
            risk_level=agg["risk_level"],
            layer_scores=agg["layer_scores"],
            layer_details=layer_results,
            deterministic_signals=layer_results.get("deterministic", {}).get("flags", []),
            statistical_signals=layer_results.get("statistical", {}).get("signals", []),
            behavioral_flags=layer_results.get("narrative", {}).get("flags", []),
            document_flags=layer_results.get("document", {}).get("flags", []),
            network_flags=layer_results.get("network", {}).get("flags", []),
            explanation_text=explanation,
            feature_snapshot=sanitize(claim_context, mode=privacy_mode),
            ai_degraded_mode=layer_results.get("narrative", {}).get("ai_degraded", True),
            ml_model_used=layer_results.get("ml", {}).get("model_used", False),
        )

    # ── Helpers ────────────────────────────────────────────────────────────────
    @staticmethod
    def _risk_level(score: float) -> str:
        for label, threshold in sorted(
            cfg.RISK_LEVEL_BOUNDARIES.items(), key=lambda kv: kv[1], reverse=True
        ):
            if score >= threshold:
                return label
        return "MINIMAL"

    @staticmethod
    def _fallback_explanation(flags: list[str], score: float, risk_level: str) -> str:
        if not flags:
            return (
                f"No significant fraud indicators detected. Risk: {risk_level} (score={score:.2f}). "
                f"See the full Claim Report for detailed analysis."
            )
        flag_summary = "; ".join(flags[:5])
        return (
            f"Fraud score: {score:.2f} ({risk_level}). "
            f"Primary signals: {flag_summary}."
            + (" [+more]" if len(flags) > 5 else "")
            + " See the full Claim Report for detailed analysis."
        )
