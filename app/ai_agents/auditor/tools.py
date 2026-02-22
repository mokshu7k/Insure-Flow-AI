"""
Auditor agent tools — system-wide read-only DB queries surfacing suspicious patterns.

Each function returns a plain dict that becomes part of AuditorState.raw_signals.
All tools accept db: AsyncSession injected via closure at graph instantiation time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── 1. Adjuster–Provider Collusion ───────────────────────────────────────────

async def check_adjuster_provider_collusion(*, db) -> dict[str, Any]:
    """
    Flag adjusters whose approval rate for a specific provider is >2x their
    overall approval rate, with a minimum of 10 claims with that provider.
    """
    from sqlalchemy import text
    try:
        sql = text("""
            WITH adjuster_totals AS (
                SELECT
                    csh.changed_by                  AS adjuster_id,
                    COUNT(*)::float                 AS total_reviewed,
                    SUM(CASE WHEN csh.to_status = 'APPROVED' THEN 1 ELSE 0 END)::float
                                                    AS total_approved
                FROM claim_status_history csh
                WHERE csh.to_status IN ('APPROVED', 'REJECTED')
                GROUP BY csh.changed_by
            ),
            adjuster_provider AS (
                SELECT
                    csh.changed_by                  AS adjuster_id,
                    c.provider_id                   AS provider_id,
                    COUNT(*)::float                 AS pair_reviewed,
                    SUM(CASE WHEN csh.to_status = 'APPROVED' THEN 1 ELSE 0 END)::float
                                                    AS pair_approved
                FROM claim_status_history csh
                JOIN claims c ON c.id = csh.claim_id
                WHERE csh.to_status IN ('APPROVED', 'REJECTED')
                  AND c.provider_id IS NOT NULL
                GROUP BY csh.changed_by, c.provider_id
                HAVING COUNT(*) >= 10
            )
            SELECT
                ap.adjuster_id::text,
                ap.provider_id::text,
                ap.pair_reviewed,
                ap.pair_approved,
                ROUND(
                    (ap.pair_approved / NULLIF(ap.pair_reviewed, 0))::numeric, 3
                ) AS pair_approval_rate,
                ROUND(
                    (at2.total_approved / NULLIF(at2.total_reviewed, 0))::numeric, 3
                ) AS overall_approval_rate
            FROM adjuster_provider ap
            JOIN adjuster_totals at2 ON at2.adjuster_id = ap.adjuster_id
            WHERE (ap.pair_approved / NULLIF(ap.pair_reviewed, 0))
                  > 2.0 * (at2.total_approved / NULLIF(at2.total_reviewed, 0))
            ORDER BY pair_approval_rate DESC
            LIMIT 20
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"collusion_pairs": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_adjuster_provider_collusion: %s", exc)
        return {"error": str(exc)}


# ── 2. Provider Overbilling ───────────────────────────────────────────────────

async def check_provider_overbilling(*, db) -> dict[str, Any]:
    """
    Providers whose average claim_amount in the last 30 days is >2.5x their
    all-time average (requires at least 5 historical claims).
    """
    from sqlalchemy import text
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    try:
        sql = text("""
            WITH baseline AS (
                SELECT
                    provider_id,
                    COUNT(*)          AS total_claims,
                    AVG(claim_amount) AS avg_amount_alltime
                FROM claims
                WHERE provider_id IS NOT NULL
                GROUP BY provider_id
                HAVING COUNT(*) >= 5
            ),
            recent AS (
                SELECT
                    provider_id,
                    COUNT(*)          AS recent_claims,
                    AVG(claim_amount) AS avg_amount_recent
                FROM claims
                WHERE provider_id IS NOT NULL
                  AND created_at >= :cutoff
                GROUP BY provider_id
                HAVING COUNT(*) >= 2
            )
            SELECT
                b.provider_id::text,
                b.total_claims,
                ROUND(b.avg_amount_alltime::numeric, 2) AS avg_alltime,
                r.recent_claims,
                ROUND(r.avg_amount_recent::numeric, 2)  AS avg_recent_30d,
                ROUND(
                    (r.avg_amount_recent / NULLIF(b.avg_amount_alltime, 0))::numeric, 2
                ) AS spike_ratio
            FROM baseline b
            JOIN recent r ON r.provider_id = b.provider_id
            WHERE r.avg_amount_recent > 2.5 * b.avg_amount_alltime
            ORDER BY spike_ratio DESC
            LIMIT 20
        """).bindparams(cutoff=cutoff)
        rows = (await db.execute(sql)).mappings().all()
        return {"overbilling_providers": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_provider_overbilling: %s", exc)
        return {"error": str(exc)}


# ── 3. Underpayment Pattern ───────────────────────────────────────────────────

async def check_underpayment_pattern(*, db) -> dict[str, Any]:
    """
    Adjusters who systematically approve <65% of requested amount on average
    AND have silent large cuts (no adjuster_notes) — at least 10 approved claims.
    """
    from sqlalchemy import text
    try:
        sql = text("""
            WITH adjuster_cuts AS (
                SELECT
                    csh.changed_by       AS adjuster_id,
                    COUNT(*)             AS approved_claims,
                    AVG(
                        CASE WHEN c.claim_amount > 0
                             THEN c.approved_amount / c.claim_amount
                             ELSE NULL END
                    )                    AS avg_payout_ratio,
                    SUM(
                        CASE WHEN (c.adjuster_notes IS NULL
                                   OR LENGTH(c.adjuster_notes) < 30)
                              AND c.approved_amount < c.claim_amount * 0.6
                             THEN 1 ELSE 0 END
                    )                    AS silent_cut_count
                FROM claim_status_history csh
                JOIN claims c ON c.id = csh.claim_id
                WHERE csh.to_status = 'APPROVED'
                  AND c.approved_amount IS NOT NULL
                  AND c.claim_amount > 0
                GROUP BY csh.changed_by
                HAVING COUNT(*) >= 10
            )
            SELECT
                adjuster_id::text,
                approved_claims,
                ROUND(avg_payout_ratio::numeric, 3) AS avg_payout_ratio,
                silent_cut_count
            FROM adjuster_cuts
            WHERE avg_payout_ratio < 0.65
               OR silent_cut_count >= 5
            ORDER BY avg_payout_ratio ASC
            LIMIT 20
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"underpayment_adjusters": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_underpayment_pattern: %s", exc)
        return {"error": str(exc)}


# ── 4. High Fraud Score Approved ─────────────────────────────────────────────

async def check_high_fraud_score_approved(*, db) -> dict[str, Any]:
    """Claims with fraud_score >0.70 that are in APPROVED or SETTLED state."""
    from sqlalchemy import text
    try:
        sql = text("""
            SELECT
                c.id::text           AS claim_id,
                c.claim_number,
                c.status,
                c.claim_amount,
                c.approved_amount,
                c.provider_id::text,
                c.user_id::text,
                fa.fraud_score,
                fa.risk_level,
                fa.explanation_text,
                c.updated_at         AS last_status_change
            FROM claims c
            JOIN fraud_assessments fa ON fa.claim_id = c.id
            WHERE fa.fraud_score > 0.70
              AND c.status IN ('APPROVED', 'SETTLED')
            ORDER BY fa.fraud_score DESC
            LIMIT 50
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"high_fraud_approved": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_high_fraud_score_approved: %s", exc)
        return {"error": str(exc)}


# ── 5. Abnormal Settlement Speed ─────────────────────────────────────────────

async def check_abnormal_settlement_speed(*, db) -> dict[str, Any]:
    """Claims that went from SUBMITTED to SETTLED in under 24 hours."""
    from sqlalchemy import text
    try:
        sql = text("""
            WITH submission AS (
                SELECT claim_id, MIN(created_at) AS submitted_at
                FROM claim_status_history
                WHERE to_status = 'SUBMITTED'
                GROUP BY claim_id
            ),
            settlement AS (
                SELECT claim_id, MIN(created_at) AS settled_at
                FROM claim_status_history
                WHERE to_status = 'SETTLED'
                GROUP BY claim_id
            )
            SELECT
                s.claim_id::text,
                c.claim_number,
                c.claim_amount,
                c.approved_amount,
                c.provider_id::text,
                c.user_id::text,
                sub.submitted_at,
                s.settled_at,
                ROUND(
                    EXTRACT(EPOCH FROM (s.settled_at - sub.submitted_at)) / 3600.0, 2
                ) AS hours_to_settle
            FROM settlement s
            JOIN submission sub ON sub.claim_id = s.claim_id
            JOIN claims c ON c.id = s.claim_id
            WHERE s.settled_at - sub.submitted_at < INTERVAL '24 hours'
            ORDER BY hours_to_settle ASC
            LIMIT 30
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"fast_settlements": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_abnormal_settlement_speed: %s", exc)
        return {"error": str(exc)}


# ── 6. Settlement Amount Discrepancy ─────────────────────────────────────────

async def check_settlement_discrepancy(*, db) -> dict[str, Any]:
    """Settlements where paid amount differs from approved_amount by >5%."""
    from sqlalchemy import text
    try:
        sql = text("""
            SELECT
                s.id::text            AS settlement_id,
                s.claim_id::text,
                c.claim_number,
                c.approved_amount     AS claim_approved,
                s.amount              AS settled_amount,
                ROUND(
                    ABS(s.amount - c.approved_amount)::numeric, 2
                )                     AS absolute_diff,
                ROUND(
                    ABS(s.amount - c.approved_amount)
                    / NULLIF(c.approved_amount, 0) * 100, 2
                )                     AS pct_diff,
                s.initiated_by::text,
                s.status              AS settlement_status
            FROM settlements s
            JOIN claims c ON c.id = s.claim_id
            WHERE c.approved_amount IS NOT NULL
              AND c.approved_amount > 0
              AND ABS(s.amount - c.approved_amount)
                  / NULLIF(c.approved_amount, 0) > 0.05
            ORDER BY pct_diff DESC
            LIMIT 30
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"settlement_discrepancies": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_settlement_discrepancy: %s", exc)
        return {"error": str(exc)}


# ── 7. Claim Amount Gap (silent large cuts) ───────────────────────────────────

async def check_claim_amount_gap(*, db) -> dict[str, Any]:
    """
    APPROVED/SETTLED claims where approved < 60% of claimed AND
    adjuster_notes is NULL or very short — no documented reason for the cut.
    """
    from sqlalchemy import text
    try:
        sql = text("""
            SELECT
                c.id::text,
                c.claim_number,
                c.claim_type,
                c.claim_amount,
                c.approved_amount,
                ROUND(
                    (1.0 - c.approved_amount / NULLIF(c.claim_amount, 0)) * 100, 1
                )                     AS cut_pct,
                c.adjuster_notes,
                c.provider_id::text,
                c.user_id::text,
                csh.changed_by::text  AS deciding_adjuster
            FROM claims c
            LEFT JOIN LATERAL (
                SELECT changed_by FROM claim_status_history
                WHERE claim_id = c.id AND to_status = 'APPROVED'
                ORDER BY created_at DESC
                LIMIT 1
            ) csh ON true
            WHERE c.status IN ('APPROVED', 'SETTLED')
              AND c.approved_amount IS NOT NULL
              AND c.claim_amount > 0
              AND c.approved_amount < c.claim_amount * 0.60
              AND (c.adjuster_notes IS NULL OR LENGTH(c.adjuster_notes) < 50)
            ORDER BY cut_pct DESC
            LIMIT 30
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"undocumented_large_cuts": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_claim_amount_gap: %s", exc)
        return {"error": str(exc)}


# ── 8. Provider Cluster Activity ─────────────────────────────────────────────

async def check_provider_cluster_activity(*, db) -> dict[str, Any]:
    """
    3+ different providers filing claims on the same claim_type in the same
    7-day window with nearly identical amount bucket (rounded to nearest 1000).
    Proxy for a coordinated billing ring.
    """
    from sqlalchemy import text
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    try:
        sql = text("""
            WITH weekly_buckets AS (
                SELECT
                    provider_id,
                    claim_type,
                    ROUND(claim_amount / 1000.0) * 1000   AS amount_bucket,
                    DATE_TRUNC('week', created_at)         AS week_start,
                    id                                     AS claim_id
                FROM claims
                WHERE provider_id IS NOT NULL
                  AND created_at >= :cutoff
            )
            SELECT
                claim_type,
                amount_bucket,
                week_start,
                COUNT(DISTINCT provider_id)                AS distinct_providers,
                COUNT(*)                                   AS total_claims,
                ARRAY_AGG(DISTINCT provider_id::text)      AS provider_ids,
                ARRAY_AGG(claim_id::text)                  AS claim_ids
            FROM weekly_buckets
            GROUP BY claim_type, amount_bucket, week_start
            HAVING COUNT(DISTINCT provider_id) >= 3
            ORDER BY distinct_providers DESC, total_claims DESC
            LIMIT 20
        """).bindparams(cutoff=cutoff)
        rows = (await db.execute(sql)).mappings().all()
        return {"provider_clusters": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_provider_cluster_activity: %s", exc)
        return {"error": str(exc)}


# ── 9. User Claim Surge (slipped through fraud engine) ───────────────────────

async def check_user_claim_surge(*, db) -> dict[str, Any]:
    """
    Users with recent_claims_30d >4 or total_claim_amount_90d >800000
    whose fraud_flag_count is still 0 — slipped through without being flagged.
    """
    from sqlalchemy import text
    try:
        sql = text("""
            SELECT
                ufp.user_id::text,
                ufp.recent_claims_30d,
                ufp.total_claim_amount_90d,
                ufp.fraud_flag_count,
                ufp.total_claims,
                ufp.last_claim_date
            FROM user_fraud_profiles ufp
            WHERE ufp.fraud_flag_count = 0
              AND (
                  ufp.recent_claims_30d > 4
               OR ufp.total_claim_amount_90d > 800000
              )
            ORDER BY ufp.recent_claims_30d DESC, ufp.total_claim_amount_90d DESC
            LIMIT 30
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"unflagged_surges": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_user_claim_surge: %s", exc)
        return {"error": str(exc)}


# ── 10. Document Integrity Flags ─────────────────────────────────────────────

async def check_document_integrity(*, db) -> dict[str, Any]:
    """
    Claims where:
      - same document_type_code submitted 3+ times (repeated resubmissions), OR
      - average extraction_confidence <0.50 across all docs, OR
      - 2+ DocumentValidationResult rows with result=FAIL
    """
    from sqlalchemy import text
    try:
        sql = text("""
            WITH doc_stats AS (
                SELECT
                    cd.claim_id,
                    COUNT(*)                             AS total_docs,
                    AVG(cd.extraction_confidence)        AS avg_confidence,
                    MAX(sub_count.cnt)                   AS max_type_submissions
                FROM claim_documents cd
                JOIN (
                    SELECT claim_id, document_type_code, COUNT(*) AS cnt
                    FROM claim_documents
                    GROUP BY claim_id, document_type_code
                ) sub_count ON sub_count.claim_id = cd.claim_id
                             AND sub_count.document_type_code = cd.document_type_code
                GROUP BY cd.claim_id
            ),
            fail_counts AS (
                SELECT cd.claim_id, COUNT(*) AS fail_count
                FROM document_validation_results dvr
                JOIN claim_documents cd ON cd.id = dvr.claim_document_id
                WHERE dvr.result = 'FAIL'
                GROUP BY cd.claim_id
            )
            SELECT
                ds.claim_id::text,
                ds.total_docs,
                ROUND(ds.avg_confidence::numeric, 3)  AS avg_confidence,
                ds.max_type_submissions,
                COALESCE(fc.fail_count, 0)             AS validation_fail_count
            FROM doc_stats ds
            LEFT JOIN fail_counts fc ON fc.claim_id = ds.claim_id
            WHERE ds.max_type_submissions >= 3
               OR ds.avg_confidence < 0.50
               OR COALESCE(fc.fail_count, 0) >= 2
            ORDER BY validation_fail_count DESC, avg_confidence ASC
            LIMIT 30
        """)
        rows = (await db.execute(sql)).mappings().all()
        return {"doc_integrity_issues": [dict(r) for r in rows]}
    except Exception as exc:
        logger.error("check_document_integrity: %s", exc)
        return {"error": str(exc)}
