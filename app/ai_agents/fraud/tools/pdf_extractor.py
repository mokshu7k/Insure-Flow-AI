"""
PDF raw text extractor — PyMuPDF-based ground-truth stream.

Even if a fraudster places a white box over a number and types a new one,
the underlying PDF char-stream often still contains the original value.
This gives us the "undeniable truth" to cross-reference against LLM output.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def get_raw_text(file_bytes: bytes) -> str:
    """Extract the full raw text layer from a PDF.

    Args:
        file_bytes: Raw bytes of the PDF file.

    Returns:
        Concatenated text from all pages.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = ""
        for page in doc:
            full_text += page.get_text("text")
        doc.close()
        return full_text
    except Exception as exc:
        logger.warning("PyMuPDF text extraction failed: %s", exc)
        return ""


def get_page_images(file_bytes: bytes) -> list[bytes]:
    """Render each PDF page as a PNG image (for Gemini visual calls).

    Returns a list of PNG byte arrays, one per page.
    """
    images: list[bytes] = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            # Render at 2x zoom for better quality
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            images.append(pix.tobytes("png"))
        doc.close()
    except Exception as exc:
        logger.warning("PyMuPDF page rendering failed: %s", exc)
    return images


def extract_text_blocks_with_positions(file_bytes: bytes) -> list[dict[str, Any]]:
    """Extract text blocks with their bounding boxes.

    Returns a list of dicts: {text, x0, y0, x1, y1, page}
    Useful for coordinate-based verification.
    """
    blocks: list[dict[str, Any]] = []
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num, page in enumerate(doc):
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") == 0:  # text block
                    for line in block.get("lines", []):
                        text = " ".join(
                            span["text"] for span in line.get("spans", [])
                        ).strip()
                        if text:
                            bbox = line["bbox"]
                            blocks.append({
                                "text": text,
                                "x0": bbox[0],
                                "y0": bbox[1],
                                "x1": bbox[2],
                                "y1": bbox[3],
                                "page": page_num,
                            })
        doc.close()
    except Exception as exc:
        logger.warning("PyMuPDF block extraction failed: %s", exc)
    return blocks


def normalize_number_string(value: Any) -> str:
    """Normalize a number for fuzzy matching.

    Strips commas, currency symbols, whitespace, and leading zeros
    so that "₹50,000.00", "50000", "50,000" all become "50000".
    """
    s = str(value).strip()
    # Remove currency symbols and common prefixes
    s = re.sub(r"[₹$€£]", "", s)
    s = s.replace("Rs.", "").replace("Rs", "").replace("INR", "")
    # Remove commas and whitespace
    s = s.replace(",", "").replace(" ", "")
    # Remove trailing .00
    if s.endswith(".00"):
        s = s[:-3]
    # Remove leading zeros (but keep single "0")
    s = s.lstrip("0") or "0"
    return s
