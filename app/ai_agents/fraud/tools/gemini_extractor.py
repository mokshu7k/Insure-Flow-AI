"""
Dual Gemini extraction — blind-split cognitive load.

Two separate LLM calls to prevent the model from "making the math work":
1. **Primary Call**: Extract all line items + full JSON structure.
2. **Shadow Call**: Extract ONLY the grand total / amount payable (focused prompt).

Optional:
3. **Coordinate Call**: Get bounding box of the total amount for visual verification.
"""
from __future__ import annotations

import json
import logging
import re
import time
import base64
from typing import Any

logger = logging.getLogger(__name__)


def _get_llm(temperature: float = 0.1):
    """Create a Gemini LLM instance."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.config import settings

    if not settings.GCP_API_KEY:
        raise ValueError("No GCP_API_KEY configured")

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GCP_API_KEY,
        temperature=temperature,
        max_output_tokens=8000,
    )


def _parse_json_response(content: str) -> dict | None:
    """Robustly parse JSON from an LLM response (handles fences, trailing commas, etc.)."""
    content = content.strip()

    # Strip markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL)
    if fence_match:
        content = fence_match.group(1).strip()
    else:
        brace_start = content.find("{")
        brace_end = content.rfind("}")
        bracket_start = content.find("[")
        bracket_end = content.rfind("]")

        # Pick whichever outer container comes first
        if brace_start != -1 and brace_end != -1:
            if bracket_start != -1 and bracket_start < brace_start:
                content = content[bracket_start:bracket_end + 1]
            else:
                content = content[brace_start:brace_end + 1]

    # Strategy A: direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Strategy B: collapse whitespace
    try:
        return json.loads(re.sub(r"\s+", " ", content))
    except json.JSONDecodeError:
        pass

    # Strategy C: fix trailing commas + single quotes
    try:
        fixed = re.sub(r"\s+", " ", content)
        fixed = re.sub(r",\s*}", "}", fixed)
        fixed = re.sub(r",\s*]", "]", fixed)
        fixed = fixed.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return None


def primary_extraction(page_images: list[bytes], document_type: str) -> dict[str, Any]:
    """Primary Gemini call — extract all line items into structured JSON.

    Args:
        page_images: List of PNG byte arrays (one per page).
        document_type: e.g. "HOSPITAL_BILL"

    Returns:
        Dict with keys like line_items, total_amount, patient_name, etc.
    """
    llm = _get_llm(temperature=0.1)

    prompt = f"""You are an expert document parser for insurance fraud detection.

DOCUMENT TYPE: {document_type}

TASK: Extract ALL financial data from this document image with extreme precision.
Return a JSON object with these keys:
- "line_items": array of {{"item": "description", "quantity": 1, "rate": 0.00, "amount": 0.00}}
- "total_amount": the grand total / amount payable (number)
- "subtotal": subtotal before taxes if visible (number or null)
- "tax_amount": tax/GST amount if visible (number or null)
- "discount": discount amount if visible (number or null)
- "patient_name": patient name if visible (string or null)
- "hospital_name": hospital/provider name if visible (string or null)
- "bill_date": date on the document (string or null)
- "bill_number": invoice/bill number if visible (string or null)
- "admission_date": admission date if visible (string or null)
- "discharge_date": discharge date if visible (string or null)

CRITICAL RULES:
1. Extract ALL line items — do not summarize or merge rows.
2. Return amounts as raw numbers WITHOUT commas or currency symbols.
3. If a field is not visible, set it to null.
4. Return ONLY valid JSON, no markdown, no explanation.

Extract from the uploaded document now."""

    # Build multimodal message content
    content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img_bytes in page_images[:3]:  # limit to 3 pages
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    from langchain_core.messages import HumanMessage
    t0 = time.perf_counter()
    response = llm.invoke([HumanMessage(content=content_parts)])
    elapsed = time.perf_counter() - t0
    logger.info("Primary extraction completed in %.2fs", elapsed)

    text = response.content
    if isinstance(text, list):
        text = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in text
        ).strip()

    parsed = _parse_json_response(text)
    if parsed is None:
        logger.error("Primary extraction: failed to parse JSON. Raw: %s", text[:500])
        return {"line_items": [], "total_amount": None, "_parse_error": True}

    return parsed


def shadow_total_extraction(page_images: list[bytes]) -> float | None:
    """Shadow Gemini call — extract ONLY the grand total / amount payable.

    Uses a tightly focused prompt with low temperature to get just the number.

    Args:
        page_images: List of PNG byte arrays.

    Returns:
        The extracted total as a float, or None if extraction fails.
    """
    llm = _get_llm(temperature=0.0)

    prompt = """Look at this document image carefully.

Find the "Grand Total", "Total Amount", "Amount Payable", "Net Amount", 
or similar final total amount on this document.

Return ONLY the number. No currency symbols, no commas, no text.
Just the raw number. Example: 145000

If you cannot find any total, return: null"""

    content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img_bytes in page_images[:2]:  # Only first 2 pages needed
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    from langchain_core.messages import HumanMessage
    t0 = time.perf_counter()
    response = llm.invoke([HumanMessage(content=content_parts)])
    elapsed = time.perf_counter() - t0
    logger.info("Shadow total extraction completed in %.2fs", elapsed)

    text = response.content
    if isinstance(text, list):
        text = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in text
        ).strip()

    text = text.strip()
    if text.lower() == "null" or not text:
        return None

    # Clean the response — it should be just a number
    cleaned = re.sub(r"[^\d.]", "", text)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        logger.warning("Shadow extraction: could not parse '%s' as float", text)
        return None


def coordinate_extraction(page_images: list[bytes]) -> dict[str, Any] | None:
    """Ask Gemini for the bounding box coordinates of the total amount.

    Returns:
        Dict with keys: ymin, xmin, ymax, xmax (normalized 0-1000),
        and "value" (the text Gemini sees at that location).
        None if extraction fails.
    """
    llm = _get_llm(temperature=0.0)

    prompt = """Look at this document image.

Find the "Grand Total", "Total Amount", or "Amount Payable" VALUE (the number, not the label).

Return a JSON object with:
- "value": the total amount as a string (exactly as it appears in the image)
- "bounding_box": [ymin, xmin, ymax, xmax] coordinates normalized to 0-1000 range

Example: {"value": "1,45,000", "bounding_box": [850, 400, 880, 600]}

Return ONLY the JSON object, no explanation."""

    content_parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for img_bytes in page_images[:1]:  # Just first page
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    from langchain_core.messages import HumanMessage
    t0 = time.perf_counter()
    response = llm.invoke([HumanMessage(content=content_parts)])
    elapsed = time.perf_counter() - t0
    logger.info("Coordinate extraction completed in %.2fs", elapsed)

    text = response.content
    if isinstance(text, list):
        text = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in text
        ).strip()

    parsed = _parse_json_response(text)
    if parsed is None:
        logger.warning("Coordinate extraction: failed to parse. Raw: %s", text[:300])
        return None

    return parsed
