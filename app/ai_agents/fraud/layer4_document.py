"""
Layer 4 – Document Fraud Detector
Connects the OCR pipeline output to the fraud engine.

Checks
------
1. DUPLICATE_INVOICE_NUMBER   – same invoice number seen on a prior claim
2. LOW_OCR_CONFIDENCE         – confidence below cfg.OCR_CONFIDENCE_THRESHOLD
3. DOCUMENT_DATE_INCONSISTENCY – OCR-extracted date drifts > cfg.DOCUMENT_DATE_DRIFT_DAYS
                                  from claim submission date
4. MISSING_REQUIRED_DOCUMENT  – required doc type absent for this claim category

No external calls – reads from the pre-fetched ``documents`` list in claim_context.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.ai_agents.fraud import config as cfg
from app.schemas.fraud import DocumentResult

logger = logging.getLogger(__name__)


def evaluate(claim_context: Dict[str, Any]) -> DocumentResult:
    """
    Analyse document-level fraud signals.

    Args:
        claim_context: Must include:
            - ``claim_type``     (str)
            - ``claim_date``     (ISO string – date claim was submitted)
            - ``documents``      (list of dicts from Document ORM rows)
            - ``all_invoice_numbers`` (list of str from prior DB query –
                                       pre-fetched by ClaimContextBuilder)

    Returns:
        DocumentResult with normalised score in [0.0, 1.0] and flag list.
    """
    flags: List[str] = []
    raw_score: float = 0.0

    claim_type: str = claim_context.get("claim_type", "")
    documents: List[Dict[str, Any]] = claim_context.get("documents", [])
    claim_date_str: str | None = claim_context.get("claim_date")
    prior_invoice_numbers: List[str] = claim_context.get("all_invoice_numbers", [])

    claim_date: datetime | None = None
    if claim_date_str:
        try:
            claim_date = datetime.fromisoformat(claim_date_str)
        except ValueError:
            claim_date = None

    # Track what doc types are present
    present_types: set[str] = set()
    seen_invoice_numbers: set[str] = set()

    for doc in documents:
        doc_type: str = doc.get("document_type", "")
        present_types.add(doc_type)
        ocr_data: Dict[str, Any] = doc.get("ocr_extracted_json") or {}

        # ── CHECK 1: Duplicate invoice number ──────────────────────────────
        invoice_number = str(ocr_data.get("invoice_number", "")).strip()
        if invoice_number:
            if invoice_number in seen_invoice_numbers or invoice_number in prior_invoice_numbers:
                if "DUPLICATE_INVOICE_NUMBER" not in flags:
                    flags.append("DUPLICATE_INVOICE_NUMBER")
                    raw_score += cfg.DUPLICATE_INVOICE_SCORE
                    logger.debug("Layer4: duplicate invoice '%s'", invoice_number)
            seen_invoice_numbers.add(invoice_number)

        # ── CHECK 2: Low OCR confidence ────────────────────────────────────
        ocr_confidence = doc.get("ocr_confidence") or ocr_data.get("confidence")
        if ocr_confidence is not None:
            try:
                confidence_val = float(ocr_confidence)
                if confidence_val < cfg.OCR_CONFIDENCE_THRESHOLD:
                    if "LOW_OCR_CONFIDENCE" not in flags:
                        flags.append("LOW_OCR_CONFIDENCE")
                        raw_score += cfg.LOW_OCR_CONFIDENCE_SCORE
                        logger.debug(
                            "Layer4: low OCR confidence %.2f (threshold %.2f)",
                            confidence_val, cfg.OCR_CONFIDENCE_THRESHOLD,
                        )
            except (TypeError, ValueError):
                pass

        # ── CHECK 3: Document date inconsistency ────────────────────────────
        if claim_date is not None:
            doc_date_str = str(ocr_data.get("date", "") or "").strip()
            if doc_date_str:
                try:
                    doc_date = datetime.fromisoformat(doc_date_str)
                    drift_days = abs((claim_date - doc_date).days)
                    if drift_days > cfg.DOCUMENT_DATE_DRIFT_DAYS:
                        if "DOCUMENT_DATE_INCONSISTENCY" not in flags:
                            flags.append("DOCUMENT_DATE_INCONSISTENCY")
                            raw_score += cfg.DOCUMENT_DATE_INCONSISTENCY_SCORE
                            logger.debug(
                                "Layer4: date drift %d days (threshold %d)",
                                drift_days, cfg.DOCUMENT_DATE_DRIFT_DAYS,
                            )
                except ValueError:
                    pass

    # ── CHECK 4: Missing required document types ────────────────────────────
    required = cfg.REQUIRED_DOCUMENTS_BY_TYPE.get(claim_type, [])
    for req_type in required:
        if req_type not in present_types:
            if "MISSING_REQUIRED_DOCUMENT" not in flags:
                flags.append("MISSING_REQUIRED_DOCUMENT")
                raw_score += cfg.MISSING_REQUIRED_DOCUMENT_SCORE
                logger.debug("Layer4: missing required doc type '%s'", req_type)

    score = min(1.0, max(0.0, raw_score))
    logger.debug("Layer4 document: flags=%s score=%.3f", flags, score)

    return DocumentResult(score=score, flags=flags)
