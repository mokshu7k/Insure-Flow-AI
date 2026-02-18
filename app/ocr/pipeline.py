"""
OCR Pipeline
Orchestrates: preprocess → extract → parse → validate.

Engine routing (all self-hosted, zero data egress):
  Handwritten doc types  (PRESCRIPTION, POLICE_REPORT, FIR)
      → TrOCR (microsoft/trocr-large-handwritten)
  Table/layout doc types (INVOICE, ESTIMATE, DISCHARGE_SUMMARY, MEDICAL_REPORT)
      → PaddleOCR PPStructure (returns structured table_data alongside raw_text)
  All other printed docs
      → PaddleOCR standard
  Any engine confidence < 0.5
      → falls back to next engine automatically (see extractor.py)

PDF routing: PyMuPDF rasterises pages → image pipeline.
Graceful degradation: any stage failure returns manual_review=True, never crashes caller.
"""
import io
import logging
from pathlib import Path
from typing import Dict, Any, Union

from app.ocr.preprocess import OCRPreprocessor
from app.ocr.extractor import OCRExtractor, ExtractionResult
from app.ocr.parser import OCRParser

logger = logging.getLogger(__name__)

IMAGE_MIME = {"image/jpeg", "image/jpg", "image/png", "image/tiff", "image/bmp"}
PDF_MIME = {"application/pdf"}

MINIMUM_CONFIDENCE = 0.45


class OCRPipeline:
    """
    Single entry point for all document OCR.

    Usage:
        pipeline = OCRPipeline()
        result = pipeline.process(file_bytes, content_type="image/jpeg", document_type="INVOICE")
        result = pipeline.process(file_bytes, content_type="application/pdf", document_type="INVOICE")
    """

    def __init__(self):
        self.preprocessor = OCRPreprocessor()
        self.extractor = OCRExtractor()
        self.parser = OCRParser()

    # ── Public entry point ───────────────────────────────────────────────────

    def process(
        self,
        file_bytes: bytes,
        content_type: str,
        document_type: str = "OTHER",
    ) -> Dict[str, Any]:
        """
        Route by MIME type then run OCR.

        Args:
            file_bytes:    Raw bytes from upload.
            content_type:  MIME type (image/* or application/pdf).
            document_type: Extraction hint (INVOICE, PRESCRIPTION, etc.).

        Returns:
            {
                extracted_fields: dict,
                raw_text: str,
                confidence: float,
                requires_manual_review: bool,
                ocr_metadata: dict,
            }
        """
        try:
            if content_type in PDF_MIME:
                return self._process_pdf(file_bytes, document_type)
            elif content_type in IMAGE_MIME:
                return self._process_image(file_bytes, document_type)
            else:
                # Unsupported type — flag for manual review, do not crash
                logger.warning(f"Unsupported MIME for OCR: {content_type}")
                return self._manual_review_result(
                    reason=f"Unsupported file type for OCR: {content_type}"
                )
        except Exception as exc:
            logger.error(f"OCR pipeline error: {exc}", exc_info=True)
            return self._manual_review_result(reason=str(exc))

    # ── Image path ───────────────────────────────────────────────────────────

    def _process_image(self, file_bytes: bytes, document_type: str) -> Dict[str, Any]:
        # PaddleOCR handles its own angle/skew correction internally.
        # Run full preprocessing only for Tesseract fallback cases (clean printed docs).
        preprocessed = self.preprocessor.preprocess(file_bytes)
        extraction: ExtractionResult = self.extractor.extract_text(
            preprocessed, document_type=document_type
        )
        return self._build_result(extraction, document_type)

    # ── PDF path ─────────────────────────────────────────────────────────────

    def _process_pdf(self, file_bytes: bytes, document_type: str) -> Dict[str, Any]:
        """
        Rasterise each PDF page with PyMuPDF (fitz) then run image OCR.
        Falls back to text extraction if fitz unavailable.
        """
        try:
            import fitz  # PyMuPDF
            return self._pdf_via_fitz(file_bytes, document_type, fitz)
        except ImportError:
            logger.warning("PyMuPDF not installed — falling back to pdfminer text extraction")
            return self._pdf_via_text_fallback(file_bytes, document_type)

    def _pdf_via_fitz(self, file_bytes: bytes, document_type: str, fitz) -> Dict[str, Any]:
        import numpy as np
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text: list[str] = []
        all_conf: list[float] = []

        for page in doc:
            # Rasterise at 200 DPI → numpy array
            mat = fitz.Matrix(200 / 72, 200 / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width
            )
            preprocessed = self.preprocessor.preprocess_for_pdf(img_array)
            extraction = self.extractor.extract_text(preprocessed, document_type=document_type)
            all_text.append(extraction.raw_text)
            all_conf.append(extraction.confidence)

        combined_text = "\n\n".join(all_text)
        avg_conf = sum(all_conf) / len(all_conf) if all_conf else 0.0

        fake_extraction = ExtractionResult(
            raw_text=combined_text,
            confidence=round(avg_conf, 3),
            word_count=len(combined_text.split()),
            strategy_used="pdf_fitz",
        )
        return self._build_result(fake_extraction, document_type, pages=len(all_conf))

    def _pdf_via_text_fallback(self, file_bytes: bytes, document_type: str) -> Dict[str, Any]:
        """Extract embedded text directly (no rasterisation)."""
        try:
            from pdfminer.high_level import extract_text
            raw_text = extract_text(io.BytesIO(file_bytes)) or ""
        except Exception as e:
            logger.error(f"pdfminer fallback failed: {e}")
            return self._manual_review_result(reason="PDF text extraction failed")

        structured = self.parser.parse(raw_text, document_type)
        word_count = len(raw_text.split())
        confidence = 0.70 if word_count > 20 else 0.30  # heuristic

        return {
            "extracted_fields": structured,
            "raw_text": raw_text,
            "confidence": confidence,
            "requires_manual_review": confidence < MINIMUM_CONFIDENCE,
            "ocr_metadata": {
                "strategy_used": "pdf_text_fallback",
                "word_count": word_count,
                "document_type": document_type,
            },
        }

    # ── Result builders ──────────────────────────────────────────────────────

    def _build_result(
        self,
        extraction: ExtractionResult,
        document_type: str,
        pages: int = 1,
    ) -> Dict[str, Any]:
        structured = self.parser.parse(
            extraction.raw_text,
            document_type,
            table_data=extraction.table_data,
        )
        requires_review = (
            extraction.confidence < MINIMUM_CONFIDENCE or extraction.word_count < 5
        )
        return {
            "extracted_fields": structured,
            "raw_text": extraction.raw_text,
            "confidence": extraction.confidence,
            "requires_manual_review": requires_review,
            "ocr_metadata": {
                "word_count": extraction.word_count,
                "strategy_used": extraction.strategy_used,
                "confidence_threshold": MINIMUM_CONFIDENCE,
                "document_type": document_type,
                "pages_processed": pages,
                "tables_extracted": len(extraction.table_data),
            },
        }

    def _manual_review_result(self, reason: str = "") -> Dict[str, Any]:
        return {
            "extracted_fields": {},
            "raw_text": "",
            "confidence": 0.0,
            "requires_manual_review": True,
            "ocr_metadata": {"error": reason},
        }