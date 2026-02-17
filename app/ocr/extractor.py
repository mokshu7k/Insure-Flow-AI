"""
OCR Extractor
Tesseract integration with confidence scoring and multi-strategy extraction
"""
import pytesseract
import numpy as np
from PIL import Image
import logging
from typing import Optional
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

# Tesseract configuration profiles
TESSERACT_CONFIGS = {
    "standard": r"--oem 3 --psm 3",           # Fully automatic page segmentation
    "single_block": r"--oem 3 --psm 6",       # Uniform block of text
    "invoice": r"--oem 3 --psm 4",            # Single column of text
    "table": r"--oem 3 --psm 6 -c preserve_interword_spaces=1",
    "number": r"--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.,/-",
}


@dataclass
class ExtractionResult:
    """Result of OCR extraction"""
    raw_text: str
    confidence: float        # 0.0 to 1.0
    word_count: int
    strategy_used: str
    language: str = "eng"


class OCRExtractor:
    """
    Tesseract OCR extractor.

    Strategies:
    1. Try multiple Tesseract configs
    2. Pick result with highest confidence
    3. Return structured result with metadata
    """

    def __init__(self):
        # Set Tesseract binary path
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
        logger.info(f"Tesseract path set to: {settings.TESSERACT_PATH}")

    def extract_text(
        self,
        image: np.ndarray,
        document_type: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract text from preprocessed image.

        Args:
            image: Preprocessed numpy array (from OCRPreprocessor)
            document_type: Hint for config selection (INVOICE, PRESCRIPTION, etc.)

        Returns:
            ExtractionResult with text and confidence
        """
        pil_image = Image.fromarray(image)

        # Select strategy based on document type
        if document_type in ("INVOICE", "ESTIMATE"):
            primary_strategy = "invoice"
        elif document_type in ("PRESCRIPTION", "MEDICAL_REPORT", "DISCHARGE_SUMMARY"):
            primary_strategy = "single_block"
        else:
            primary_strategy = "standard"

        # Try primary strategy
        best_result = self._extract_with_config(pil_image, primary_strategy)

        # If confidence is low, try fallback strategies
        if best_result.confidence < 0.6:
            for strategy in TESSERACT_CONFIGS:
                if strategy == primary_strategy:
                    continue
                result = self._extract_with_config(pil_image, strategy)
                if result.confidence > best_result.confidence:
                    best_result = result
                    if best_result.confidence >= 0.75:
                        break  # Good enough

        logger.info(
            f"OCR extraction complete: strategy={best_result.strategy_used}, "
            f"confidence={best_result.confidence:.2f}, words={best_result.word_count}"
        )

        return best_result

    def extract_with_confidence_data(self, image: np.ndarray) -> dict:
        """
        Extract text with per-word confidence scores.
        Used for validation and uncertain word flagging.

        Args:
            image: Preprocessed numpy array

        Returns:
            Dict with words, confidence per word, and bounding boxes
        """
        pil_image = Image.fromarray(image)

        data = pytesseract.image_to_data(
            pil_image,
            config=TESSERACT_CONFIGS["standard"],
            output_type=pytesseract.Output.DICT
        )

        words = []
        for i, word in enumerate(data["text"]):
            if word.strip() and int(data["conf"][i]) > 0:
                words.append({
                    "text": word,
                    "confidence": int(data["conf"][i]) / 100.0,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                })

        avg_confidence = (
            sum(w["confidence"] for w in words) / len(words)
            if words else 0.0
        )

        return {
            "words": words,
            "average_confidence": round(avg_confidence, 3),
            "total_words": len(words),
        }

    # ─────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────

    def _extract_with_config(self, pil_image: Image.Image, strategy: str) -> ExtractionResult:
        """Run Tesseract with a specific config and compute confidence"""
        config = TESSERACT_CONFIGS[strategy]

        try:
            # Get text
            raw_text = pytesseract.image_to_string(pil_image, config=config, lang="eng")

            # Get confidence data
            data = pytesseract.image_to_data(
                pil_image,
                config=config,
                output_type=pytesseract.Output.DICT,
                lang="eng"
            )

            # Calculate average confidence (only non-empty words)
            confidences = [
                int(conf) for conf, text in zip(data["conf"], data["text"])
                if text.strip() and int(conf) > 0
            ]
            avg_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
            word_count = len([w for w in raw_text.split() if w.strip()])

            return ExtractionResult(
                raw_text=raw_text.strip(),
                confidence=round(avg_confidence, 3),
                word_count=word_count,
                strategy_used=strategy
            )

        except Exception as e:
            logger.error(f"Tesseract extraction failed with strategy {strategy}: {e}")
            return ExtractionResult(
                raw_text="",
                confidence=0.0,
                word_count=0,
                strategy_used=strategy
            )