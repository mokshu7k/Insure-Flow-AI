"""
seed_audit_findings.py
──────────────────────
Inserts one realistic AuditRun + 8 AuditFinding rows so the audit UI
has something to display without needing to run a full Gemini sweep.

Run from the repo root:
    python scripts/seed_audit_findings.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone, timedelta

# ── Make sure app package is importable ──────────────────────────────────────
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import AsyncSessionLocal                         # noqa: E402
from app.models.audit_finding import AuditRun, AuditFinding          # noqa: E402


# ── Fake entity IDs (stable so re-runs are idempotent on run_id) ─────────────
ADJ_ID   = "5f3b2e11-0000-0000-0000-000000000001"   # adjuster
PROV_A   = "a1b2c3d4-0000-0000-0000-000000000002"   # provider Alpha
PROV_B   = "b2c3d4e5-0000-0000-0000-000000000003"   # provider Beta
PROV_C   = "c3d4e5f6-0000-0000-0000-000000000004"   # provider Gamma
USER_1   = "d4e5f6a7-0000-0000-0000-000000000005"   # customer1
USER_2   = "e5f6a7b8-0000-0000-0000-000000000006"   # customer2
CLM_1    = "f6a7b8c9-0000-0000-0000-000000000007"   # claim A
CLM_2    = "a7b8c9d0-0000-0000-0000-000000000008"   # claim B
CLM_3    = "b8c9d0e1-0000-0000-0000-000000000009"   # claim C
SETT_1   = "c9d0e1f2-0000-0000-0000-000000000010"   # settlement


FINDINGS: list[dict] = [
    # 1 ── CRITICAL: adjuster-provider collusion
    {
        "finding_type": "ADJUSTER_PROVIDER_COLLUSION",
        "severity": "CRITICAL",
        "entity_type": "ADJUSTER",
        "entity_id": ADJ_ID,
        "supporting_entity_ids": [PROV_A, CLM_1, CLM_2],
        "description": (
            "Adjuster approved 94 % of claims routed through Provider Alpha — "
            "far above the 61 % platform average — across 18 separate claims."
        ),
        "gemini_narrative": (
            "The adjuster approval rate for Provider Alpha is 94 %, compared to a "
            "platform-wide baseline of 61 % for all adjusters over the same 90-day window. "
            "The pattern appears in 18 consecutive claims, all processed within 48 hours, "
            "significantly faster than the median approval time of 5.2 days. "
            "Three of those claims had fraud scores above 0.65 yet were approved without "
            "annotation. This combination of routing concentration, speed, and fraud-score "
            "override strongly suggests an undisclosed financial relationship."
        ),
        "recommended_action": (
            "Freeze the adjuster's approval authority and request HR to audit their "
            "financial disclosure forms. Escalate claims CLM_1 and CLM_2 for independent "
            "re-review. Notify compliance within 24 hours."
        ),
        "evidence": {
            "adjuster_id": ADJ_ID,
            "provider_id": PROV_A,
            "approval_rate_pct": 94.4,
            "platform_avg_pct": 61.2,
            "flagged_claims": [CLM_1, CLM_2],
            "avg_approval_days": 1.9,
            "platform_avg_days": 5.2,
        },
    },

    # 2 ── HIGH: provider overbilling
    {
        "finding_type": "PROVIDER_OVERBILLING",
        "severity": "HIGH",
        "entity_type": "PROVIDER",
        "entity_id": PROV_B,
        "supporting_entity_ids": [CLM_3],
        "description": (
            "Provider Beta's average claim amount spiked 3.1× in the last 30 days "
            "versus their 12-month baseline — a statistically improbable jump."
        ),
        "gemini_narrative": (
            "Provider Beta submitted claims averaging ₹1,18,400 in the past 30 days, "
            "compared to a 12-month rolling average of ₹38,200 per claim. "
            "The jump of 3.1× cannot be explained by seasonal diagnosis trends or "
            "inflation alone. Cross-referencing with procedure codes shows the provider "
            "started billing premium cardiac procedure codes (ICD P9211) without any "
            "corresponding increase in inpatient admissions. "
            "Five of the eight recent claims share identical line-item descriptions, "
            "suggesting template-based billing inflation."
        ),
        "recommended_action": (
            "Request itemised bills and supporting diagnostic reports for all 8 recent "
            "claims. Engage a medical billing auditor. Consider suspension of direct "
            "settlement until audit is complete."
        ),
        "evidence": {
            "provider_id": PROV_B,
            "avg_claim_last_30d": 118400,
            "avg_claim_12m_baseline": 38200,
            "spike_ratio": 3.1,
            "flagged_procedure_code": "ICD P9211",
            "identical_description_count": 5,
        },
    },

    # 3 ── HIGH: underpayment pattern
    {
        "finding_type": "UNDERPAYMENT_PATTERN",
        "severity": "HIGH",
        "entity_type": "ADJUSTER",
        "entity_id": ADJ_ID,
        "supporting_entity_ids": [CLM_1, CLM_2, CLM_3],
        "description": (
            "The adjuster consistently approves 42–55 % less than the claimed amount "
            "with no documented reason — significantly below the 15 % platform norm."
        ),
        "gemini_narrative": (
            "Across 14 claims handled by this adjuster, the median approved-vs-claimed "
            "ratio is 49 %, whereas the platform median is 85 %. "
            "None of the under-approved claims include an adjuster justification note, "
            "which is required by SOP when the cut exceeds 25 %. "
            "This systematic underpayment exposes the insurer to policyholder grievance "
            "filings and potential IRDAI non-compliance penalties. "
            "The pattern is consistent enough to suggest either deliberate suppression "
            "or a misunderstanding of policy coverage rules."
        ),
        "recommended_action": (
            "Audit all 14 claims and require the adjuster to provide written justification "
            "retroactively. If justifications are absent or inadequate, reprocess claims "
            "at correct amounts and initiate an HR performance review."
        ),
        "evidence": {
            "adjuster_id": ADJ_ID,
            "median_approved_pct": 49,
            "platform_median_pct": 85,
            "claims_without_justification": 14,
            "sop_threshold_pct": 25,
        },
    },

    # 4 ── CRITICAL: high fraud score approved
    {
        "finding_type": "HIGH_FRAUD_SCORE_APPROVED",
        "severity": "CRITICAL",
        "entity_type": "CLAIM",
        "entity_id": CLM_2,
        "supporting_entity_ids": [USER_1, ADJ_ID],
        "description": (
            "Claim CLM_2 carried a fraud score of 0.83 (threshold 0.70) but was "
            "approved and settled within 36 hours without any fraud review flag."
        ),
        "gemini_narrative": (
            "Claim CLM_2 was scored 0.83 by the automated fraud model at submission time, "
            "exceeding the mandatory manual-review threshold of 0.70. "
            "Despite this, the claim moved directly from SUBMITTED to APPROVED in 36 hours "
            "without any SIU (Special Investigations Unit) referral or hold flag. "
            "The approving adjuster is the same individual identified in the "
            "ADJUSTER_PROVIDER_COLLUSION finding. "
            "The claim amount of ₹2,15,000 was paid in full. "
            "This represents a clear process control failure that may also indicate "
            "intentional fraud facilitation."
        ),
        "recommended_action": (
            "Immediately freeze settlement disbursement for CLM_2 if not yet cleared. "
            "Escalate to SIU with full audit trail. Review the fraud scoring pipeline "
            "to ensure high-score claims cannot bypass manual review queues."
        ),
        "evidence": {
            "claim_id": CLM_2,
            "fraud_score": 0.83,
            "review_threshold": 0.70,
            "hours_to_approval": 36,
            "siu_referral": False,
            "settlement_amount": 215000,
        },
    },

    # 5 ── HIGH: abnormal settlement speed
    {
        "finding_type": "ABNORMAL_SETTLEMENT_SPEED",
        "severity": "HIGH",
        "entity_type": "CLAIM",
        "entity_id": CLM_1,
        "supporting_entity_ids": [SETT_1, ADJ_ID],
        "description": (
            "Claim CLM_1 went from SUBMITTED to SETTLED in 11 hours — "
            "well below the 24-hour minimum investigation window."
        ),
        "gemini_narrative": (
            "The insurer's SOP mandates a minimum 24-hour review window for all claims "
            "above ₹50,000. Claim CLM_1 (₹1,82,000) was submitted at 09:14 and settled "
            "at 20:38 the same day — an 11.4-hour turnaround. "
            "The claim involved Provider Alpha (see collusion finding) and was approved "
            "by the flagged adjuster. "
            "No document verification steps appear in the audit trail between submission "
            "and approval, suggesting the normal workflow was bypassed. "
            "Abnormal speed combined with the broader collusion pattern elevates this "
            "to a high-priority concern."
        ),
        "recommended_action": (
            "Pull the full workflow trace for CLM_1 from the audit log. Identify which "
            "system roles bypassed the 24-hour hold. Reinstate mandatory minimum review "
            "windows as a hard constraint in the claims workflow engine."
        ),
        "evidence": {
            "claim_id": CLM_1,
            "submitted_at": "2026-02-18T09:14:00Z",
            "settled_at": "2026-02-18T20:38:00Z",
            "hours_elapsed": 11.4,
            "minimum_window_hours": 24,
            "claim_amount": 182000,
            "provider_id": PROV_A,
        },
    },

    # 6 ── MEDIUM: settlement discrepancy
    {
        "finding_type": "SETTLEMENT_AMOUNT_DISCREPANCY",
        "severity": "MEDIUM",
        "entity_type": "CLAIM",
        "entity_id": CLM_3,
        "supporting_entity_ids": [SETT_1],
        "description": (
            "Settlement amount (₹72,000) differs from approved claim amount (₹88,500) "
            "by 18.6 %, exceeding the 5 % tolerance with no deduction log."
        ),
        "gemini_narrative": (
            "Platform policy allows up to a 5 % variance between the approved claim "
            "amount and the final settlement disbursement for rounding or co-pay "
            "adjustments. For CLM_3, the variance is 18.6 % (₹16,500 gap). "
            "The settlement record contains no deduction codes, co-pay references, or "
            "adjustment notes that would account for the difference. "
            "This may indicate a data entry error, a silent policy application, or "
            "deliberate underpayment to the beneficiary. "
            "The policyholder has not yet raised a grievance, but this is likely once "
            "they receive the settlement breakdown."
        ),
        "recommended_action": (
            "Request the settlement operations team to produce the deduction breakdown "
            "for CLM_3. If no legitimate deduction applies, issue a corrective payment "
            "of ₹16,500 and notify the policyholder. Update the settlement record with "
            "proper deduction codes."
        ),
        "evidence": {
            "claim_id": CLM_3,
            "approved_amount": 88500,
            "settled_amount": 72000,
            "variance_pct": 18.6,
            "allowed_variance_pct": 5.0,
            "deduction_codes_present": False,
        },
    },

    # 7 ── MEDIUM: user claim surge
    {
        "finding_type": "USER_CLAIM_SURGE",
        "severity": "MEDIUM",
        "entity_type": "USER",
        "entity_id": USER_1,
        "supporting_entity_ids": [CLM_1, CLM_2],
        "description": (
            "customer1@test.ai filed 6 claims in the last 30 days — 3× their annual "
            "average — without triggering any fraud flag escalation."
        ),
        "gemini_narrative": (
            "This user's historical claim frequency is 2.1 per year. In the last 30 days "
            "alone they have submitted 6 claims across two policy types. "
            "The automated fraud scoring pipeline did not escalate any of these despite "
            "the anomalous frequency because the individual claim amounts were below the "
            "per-claim fraud flag threshold. "
            "However, the aggregate pattern — rapid multi-claim filing, two different "
            "providers, overlapping treatment dates — warrants a manual review. "
            "Syndicate-style soft fraud (staggered small claims under the detection "
            "threshold) is a known exploitation vector."
        ),
        "recommended_action": (
            "Manually review all 6 claims for overlapping treatment dates, duplicate "
            "procedures, and provider relationships. Flag the user account for enhanced "
            "monitoring for the next 90 days. Consider retrospective fraud scoring "
            "on the aggregate claim bundle."
        ),
        "evidence": {
            "user_id": USER_1,
            "claims_last_30d": 6,
            "annual_avg_claims": 2.1,
            "surge_ratio": 2.9,
            "fraud_flag_raised": False,
            "claim_ids": [CLM_1, CLM_2],
        },
    },

    # 8 ── LOW: document integrity
    {
        "finding_type": "DOCUMENT_INTEGRITY_FLAGS",
        "severity": "LOW",
        "entity_type": "CLAIM",
        "entity_id": CLM_3,
        "supporting_entity_ids": [PROV_C],
        "description": (
            "CLM_3 has 3 document re-submission events and a low OCR confidence score "
            "(0.41) on the hospital discharge summary."
        ),
        "gemini_narrative": (
            "The discharge summary attached to CLM_3 was re-uploaded three times over "
            "two days. The final version has an OCR extraction confidence of 0.41, which "
            "is below the platform's acceptable threshold of 0.60. "
            "Differences between the three versions include changes to the admission date "
            "and the attending physician name. "
            "While these could reflect legitimate corrections, the pattern is consistent "
            "with document tampering, particularly when viewed alongside the settlement "
            "discrepancy already identified for this claim. "
            "Provider Gamma has one prior document integrity flag from six months ago."
        ),
        "recommended_action": (
            "Request the original paper discharge summary directly from the hospital "
            "via the provider verification portal. Compare all three document versions "
            "diff by diff. If tampering is confirmed, escalate to SIU and notify the "
            "IRDAI grievance cell."
        ),
        "evidence": {
            "claim_id": CLM_3,
            "resubmission_count": 3,
            "ocr_confidence": 0.41,
            "confidence_threshold": 0.60,
            "changed_fields": ["admission_date", "attending_physician"],
            "provider_prior_flags": 1,
        },
    },
]


async def seed() -> None:
    run_id = "audit-seed-2026-02-22T00:00:00"
    now = datetime.now(timezone.utc)
    started = now - timedelta(minutes=3)

    async with AsyncSessionLocal() as db:
        # ── Idempotency check ────────────────────────────────────────────────
        from sqlalchemy import select
        existing = await db.execute(
            select(AuditRun).where(AuditRun.run_id == run_id)
        )
        if existing.scalar_one_or_none():
            print(f"[seed_audit] run_id={run_id!r} already exists — skipping.")
            return

        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in FINDINGS:
            sev = f["severity"].upper()
            if sev in counts:
                counts[sev] += 1

        run = AuditRun(
            id=uuid.uuid4(),
            run_id=run_id,
            status="COMPLETED",
            started_at=started,
            completed_at=now,
            total_findings=len(FINDINGS),
            critical_count=counts["CRITICAL"],
            high_count=counts["HIGH"],
            medium_count=counts["MEDIUM"],
            low_count=counts["LOW"],
            summary_narrative=(
                "This sweep identified 8 findings across 4 severity levels. "
                "Most critically, a systemic adjuster–provider collusion pattern was detected: "
                "a single adjuster approved 94 % of claims from Provider Alpha — far above platform norms — "
                "including two claims that exceeded the fraud-score override threshold without SIU referral. "
                "Provider Beta shows a 3.1× billing spike with no supporting admission data, "
                "consistent with overbilling via cloned procedure codes. "
                "Customer1 exhibits a 3× claim-frequency surge that bypassed the per-claim fraud pipeline. "
                "Two supporting findings on document integrity and settlement discrepancy for CLM_3 "
                "compound the risk profile of that claim. "
                "Immediate action is recommended on the two CRITICAL findings before further settlements are disbursed."
            ),
            errors={},
        )
        db.add(run)
        await db.flush()

        for f in FINDINGS:
            finding = AuditFinding(
                id=uuid.uuid4(),
                audit_run_id=run.id,
                finding_type=f["finding_type"],
                severity=f["severity"],
                entity_type=f["entity_type"],
                entity_id=f["entity_id"],
                supporting_entity_ids=f.get("supporting_entity_ids", []),
                description=f["description"],
                gemini_narrative=f.get("gemini_narrative"),
                recommended_action=f.get("recommended_action"),
                evidence=f.get("evidence", {}),
            )
            db.add(finding)

        await db.commit()
        print(
            f"[seed_audit] Inserted AuditRun {run_id!r} "
            f"with {len(FINDINGS)} findings "
            f"(CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} "
            f"MEDIUM={counts['MEDIUM']} LOW={counts['LOW']})."
        )


if __name__ == "__main__":
    asyncio.run(seed())
