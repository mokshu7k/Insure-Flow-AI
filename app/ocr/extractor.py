"""
OCR Extractor
Multi-engine OCR with automatic routing:
  - PaddleOCR  : primary engine — printed docs, tables, Hindi/regional text, skewed images
  - TrOCR      : handwriting fallback — prescriptions, FIRs, handwritten discharge notes
  - Tesseract  : fast fallback for clean printed English when PaddleOCR unavailable

Engine selection logic:
  1. Handwritten doc types  → TrOCR
  2. All other types        → PaddleOCR (with PPStructure for table docs)
  3. PaddleOCR unavailable  → Tesseract
  4. Any engine conf < 0.5  → retry with next engine
"""
import numpy as np
from PIL import Image
import logging
from typing import Optional
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)

# Document types that are typically handwritten → use TrOCR
HANDWRITTEN_TYPES = {"PRESCRIPTION", "POLICE_REPORT", "FIR"}

# Document types with tables/complex layout → use PPStructure
TABLE_LAYOUT_TYPES = {"INVOICE", "ESTIMATE", "DISCHARGE_SUMMARY", "MEDICAL_REPORT"}

# Tesseract configuration profiles (used only as last fallback)
TESSERACT_CONFIGS = {
    "standard": r"--oem 3 --psm 3",
    "single_block": r"--oem 3 --psm 6",
    "invoice": r"--oem 3 --psm 4",
    "table": r"--oem 3 --psm 6 -c preserve_interword_spaces=1",
}


@dataclass
class ExtractionResult:
    """Result of OCR extraction"""
    raw_text: str
    confidence: float                  # 0.0 to 1.0
    word_count: int
    strategy_used: str
    language: str = "eng"
    table_data: list = field(default_factory=list)   # Structured table rows from PPStructure


class OCRExtractor:
    """
    Multi-engine OCR extractor.

    Priority:
      PaddleOCR (primary, self-hosted, no data egress)
          └── PPStructure for tables/invoices
      TrOCR (handwriting, self-hosted, no data egress)
      Tesseract (fast fallback for simple printed text)
    """

    def __init__(self):
        self._paddle_ocr = None          # lazy-loaded
        self._paddle_structure = None    # lazy-loaded
        self._trocr_processor = None     # lazy-loaded
        self._trocr_model = None         # lazy-loaded

        # Tesseract path (fallback)
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
            self._tesseract_available = True
            logger.info(f"Tesseract available at: {settings.TESSERACT_PATH}")
        except Exception:
            self._tesseract_available = False
            logger.warning("Tesseract not available — will rely on PaddleOCR/TrOCR only")

    # ── Public entry point ───────────────────────────────────────────────────

    def extract_text(
        self,
        image: np.ndarray,
        document_type: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract text from a preprocessed image.

        Args:
            image:         Preprocessed numpy array (from OCRPreprocessor).
            document_type: Extraction hint — drives engine and strategy selection.

        Returns:
            ExtractionResult with text, confidence, and optional table_data.
        """
        doc_type = (document_type or "OTHER").upper()

        # Route to correct primary engine
        if doc_type in HANDWRITTEN_TYPES:
            result = self._extract_trocr(image)
            # If TrOCR confidence is poor, fall back to PaddleOCR
            if result.confidence < 0.5:
                logger.info("TrOCR low confidence — retrying with PaddleOCR")
                paddle_result = self._extract_paddle(image, doc_type)
                if paddle_result.confidence > result.confidence:
                    result = paddle_result
        else:
            result = self._extract_paddle(image, doc_type)
            # If PaddleOCR confidence is poor, try Tesseract as last resort
            if result.confidence < 0.5 and self._tesseract_available:
                logger.info("PaddleOCR low confidence — retrying with Tesseract")
                tesseract_result = self._extract_tesseract(image, doc_type)
                if tesseract_result.confidence > result.confidence:
                    result = tesseract_result

        logger.info(
            f"OCR extraction complete: engine={result.strategy_used}, "
            f"confidence={result.confidence:.2f}, words={result.word_count}, "
            f"tables={len(result.table_data)}"
        )
        return result

    def extract_with_confidence_data(self, image: np.ndarray) -> dict:
        """
        Extract text with per-word confidence scores and bounding boxes.
        Uses PaddleOCR word-level data.
        """
        ocr = self._get_paddle_ocr()
        try:
            raw_results = ocr.ocr(image, cls=True)
            words = []
            for line in (raw_results[0] or []):
                bbox, (text, conf) = line
                if text.strip():
                    x_coords = [pt[0] for pt in bbox]
                    y_coords = [pt[1] for pt in bbox]
                    words.append({
                        "text": text,
                        "confidence": round(float(conf), 3),
                        "x": int(min(x_coords)),
                        "y": int(min(y_coords)),
                        "width": int(max(x_coords) - min(x_coords)),
                        "height": int(max(y_coords) - min(y_coords)),
                    })

            avg_confidence = (
                sum(w["confidence"] for w in words) / len(words) if words else 0.0
            )
            return {
                "words": words,
                "average_confidence": round(avg_confidence, 3),
                "total_words": len(words),
            }
        except Exception as e:
            logger.error(f"PaddleOCR word-level extraction failed: {e}")
            return {"words": [], "average_confidence": 0.0, "total_words": 0}

    # ── PaddleOCR engine ─────────────────────────────────────────────────────

    def _get_paddle_ocr(self):
        """Lazy-load PaddleOCR instance (avoids heavy import at startup)."""
        if self._paddle_ocr is None:
            from paddleocr import PaddleOCR
            # use_angle_cls=True handles rotated/skewed documents automatically
            self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        return self._paddle_ocr

    def _get_paddle_structure(self):
        """Lazy-load PPStructure for table/layout-heavy documents."""
        if self._paddle_structure is None:
            from paddleocr import PPStructure
            self._paddle_structure = PPStructure(table=True, ocr=True, lang="en", show_log=False)
        return self._paddle_structure

    def _extract_paddle(self, image: np.ndarray, doc_type: str) -> ExtractionResult:
        """
        Run PaddleOCR. Uses PPStructure for table-heavy documents,
        standard PaddleOCR for everything else.
        """
        try:
            if doc_type in TABLE_LAYOUT_TYPES:
                return self._extract_paddle_structure(image, doc_type)
            return self._extract_paddle_standard(image)
        except ImportError:
            logger.warning("PaddleOCR not installed — falling back to Tesseract")
            return self._extract_tesseract(image, doc_type)
        except Exception as e:
            logger.error(f"PaddleOCR extraction failed: {e}")
            return ExtractionResult(raw_text="", confidence=0.0, word_count=0,
                                    strategy_used="paddle_error")

    def _extract_paddle_standard(self, image: np.ndarray) -> ExtractionResult:
        """Standard PaddleOCR — line-by-line text extraction."""
        ocr = self._get_paddle_ocr()
        raw_results = ocr.ocr(image, cls=True)

        lines = []
        confidences = []
        for line in (raw_results[0] or []):
            _, (text, conf) = line
            if text.strip():
                lines.append(text)
                confidences.append(float(conf))

        raw_text = "\n".join(lines)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return ExtractionResult(
            raw_text=raw_text.strip(),
            confidence=round(avg_conf, 3),
            word_count=len(raw_text.split()),
            strategy_used="paddleocr_standard",
        )

    def _extract_paddle_structure(self, image: np.ndarray, doc_type: str) -> ExtractionResult:
        """
        PPStructure — parses tables and text regions separately.
        table_data contains structured rows: [[cell, cell, ...], ...]
        """
        structure = self._get_paddle_structure()
        result = structure(image)

        all_text: list[str] = []
        all_conf: list[float] = []
        table_data: list = []

        for region in result:
            region_type = region.get("type", "")
            if region_type == "table":
                # Extract table cells as structured rows
                html = region.get("res", {}).get("html", "")
                rows = self._parse_html_table(html)
                table_data.extend(rows)
                # Also add flat text so parser regex still works
                for row in rows:
                    all_text.append("  |  ".join(str(c) for c in row))
                all_conf.append(0.90)  # Table extraction is reliable
            else:
                # Text region
                for line in region.get("res", []):
                    text = line.get("text", "").strip()
                    conf = float(line.get("confidence", 0.0))
                    if text:
                        all_text.append(text)
                        all_conf.append(conf)

        raw_text = "\n".join(all_text)
        avg_conf = sum(all_conf) / len(all_conf) if all_conf else 0.0
        return ExtractionResult(
            raw_text=raw_text.strip(),
            confidence=round(avg_conf, 3),
            word_count=len(raw_text.split()),
            strategy_used="paddleocr_structure",
            table_data=table_data,
        )

    def _parse_html_table(self, html: str) -> list:
        """Parse HTML table string from PPStructure into list of row lists."""
        if not html:
            return []
        try:
            from html.parser import HTMLParser

            class _TableParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.rows, self._row, self._cell, self._in_cell = [], [], [], False

                def handle_starttag(self, tag, attrs):
                    if tag in ("tr",): self._row = []
                    if tag in ("td", "th"): self._cell = []; self._in_cell = True

                def handle_endtag(self, tag):
                    if tag in ("td", "th"):
                        self._row.append("".join(self._cell).strip()); self._in_cell = False
                    if tag == "tr" and self._row:
                        self.rows.append(self._row)

                def handle_data(self, data):
                    if self._in_cell: self._cell.append(data)

            p = _TableParser()
            p.feed(html)
            return p.rows
        except Exception:
            return []

    # ── TrOCR engine ─────────────────────────────────────────────────────────

    def _get_trocr(self):
        """Lazy-load TrOCR processor and model (large-handwritten variant)."""
        if self._trocr_processor is None:
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            model_name = "microsoft/trocr-large-handwritten"
            logger.info(f"Loading TrOCR model: {model_name}")
            self._trocr_processor = TrOCRProcessor.from_pretrained(model_name)
            self._trocr_model = VisionEncoderDecoderModel.from_pretrained(model_name)
        return self._trocr_processor, self._trocr_model

    def _extract_trocr(self, image: np.ndarray) -> ExtractionResult:
        """
        TrOCR handwriting recognition.
        Splits image into horizontal strips (TrOCR is line-oriented)
        and concatenates results.
        """
        try:
            processor, model = self._get_trocr()
            pil_image = Image.fromarray(image).convert("RGB")

            # Split into strips of ~48px height for line-level recognition
            strips = self._split_into_lines(pil_image, strip_height=48)
            if not strips:
                strips = [pil_image]

            texts = []
            for strip in strips:
                pixel_values = processor(images=strip, return_tensors="pt").pixel_values
                generated_ids = model.generate(pixel_values)
                text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
                if text.strip():
                    texts.append(text.strip())

            raw_text = "\n".join(texts)
            # TrOCR doesn't expose per-token confidence; use word count heuristic
            confidence = min(0.85, 0.5 + 0.01 * len(texts)) if texts else 0.0

            return ExtractionResult(
                raw_text=raw_text,
                confidence=round(confidence, 3),
                word_count=len(raw_text.split()),
                strategy_used="trocr_handwritten",
            )
        except ImportError:
            logger.warning("TrOCR (transformers/torch) not installed — falling back to PaddleOCR")
            return self._extract_paddle_standard(image)
        except Exception as e:
            logger.error(f"TrOCR extraction failed: {e}")
            return ExtractionResult(raw_text="", confidence=0.0, word_count=0,
                                    strategy_used="trocr_error")

    def _split_into_lines(self, pil_image: Image.Image, strip_height: int = 48) -> list:
        """Divide image into horizontal strips for TrOCR line-level processing."""
        w, h = pil_image.size
        strips = []
        y = 0
        while y < h:
            strip = pil_image.crop((0, y, w, min(y + strip_height, h)))
            strips.append(strip)
            y += strip_height
        return strips

    # ── Tesseract engine (fallback) ──────────────────────────────────────────

    def _extract_tesseract(self, image: np.ndarray, doc_type: str) -> ExtractionResult:
        """Tesseract — fast fallback for clean printed English text."""
        try:
            import pytesseract

            pil_image = Image.fromarray(image)

            if doc_type in ("INVOICE", "ESTIMATE"):
                config = TESSERACT_CONFIGS["invoice"]
                strategy = "tesseract_invoice"
            elif doc_type in ("PRESCRIPTION", "MEDICAL_REPORT", "DISCHARGE_SUMMARY"):
                config = TESSERACT_CONFIGS["single_block"]
                strategy = "tesseract_single_block"
            else:
                config = TESSERACT_CONFIGS["standard"]
                strategy = "tesseract_standard"

            raw_text = pytesseract.image_to_string(pil_image, config=config, lang="eng")
            data = pytesseract.image_to_data(
                pil_image, config=config,
                output_type=pytesseract.Output.DICT, lang="eng"
            )
            confidences = [
                int(c) for c, t in zip(data["conf"], data["text"])
                if t.strip() and int(c) > 0
            ]
            avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

            return ExtractionResult(
                raw_text=raw_text.strip(),
                confidence=round(avg_conf, 3),
                word_count=len(raw_text.split()),
                strategy_used=strategy,
            )
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {e}")
            return ExtractionResult(raw_text="", confidence=0.0, word_count=0,
                                    strategy_used="tesseract_error")