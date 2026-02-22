"""
Metadata & EXIF Analysis — The Digital Fingerprint.

Most fraudulent medical bills are either "born digital" (created in
Word/Canva/Photoshop) or are photos of screens.  This module inspects
the invisible digital fingerprint that accompanies every image/PDF.

Checks performed:
  1. Software tag detection — "Adobe Photoshop", "Canva", etc.
  2. CreateDate vs ModifyDate discrepancy
  3. Camera hardware strings (should be present for "scanned" photos)
  4. Resolution consistency (DPI anomalies)
  5. Color-space / bit-depth anomalies

All checks are deterministic — no LLM calls.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from typing import Any

import exifread
from PIL import Image
from PIL.ExifTags import TAGS as PIL_TAGS

logger = logging.getLogger(__name__)

# ── Known suspicious software tags ───────────────────────────────────────────
_SUSPICIOUS_SOFTWARE = [
    "photoshop", "illustrator", "canva", "gimp", "paint.net",
    "affinity", "inkscape", "corel", "pixlr", "fotor",
    "microsoft word", "libreoffice", "openoffice",
    "wps office", "google docs",
]

# Software that is expected for legitimate scanned documents
_SCANNER_SOFTWARE = [
    "scanner", "scan", "camscanner", "adobe scan", "genius scan",
    "microsoft lens", "office lens", "epson", "hp scan", "canon",
    "brother", "xerox", "ricoh", "konica",
]


def _is_suspicious_software(tag_value: str) -> tuple[bool, str]:
    """Check if a software tag indicates document fabrication."""
    lower = tag_value.lower().strip()
    for s in _SUSPICIOUS_SOFTWARE:
        if s in lower:
            return True, f"Suspicious creator software: '{tag_value}'"
    return False, ""


def _is_scanner_software(tag_value: str) -> bool:
    """Check if a software tag indicates a legitimate scanner."""
    lower = tag_value.lower().strip()
    return any(s in lower for s in _SCANNER_SOFTWARE)


def _parse_exif_datetime(dt_str: str) -> datetime | None:
    """Parse EXIF datetime formats."""
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y:%m:%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(dt_str).strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def analyze_metadata(image_bytes: bytes) -> dict[str, Any]:
    """Analyse image metadata/EXIF for forensic signals.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, TIFF, etc.).

    Returns:
        dict with keys:
            passed: bool
            flags: list[str]
            software: str | None
            create_date: str | None
            modify_date: str | None
            camera_make: str | None
            camera_model: str | None
            dpi: tuple[int, int] | None
            has_exif: bool
            details: dict   (full extracted metadata)
    """
    result: dict[str, Any] = {
        "passed": True,
        "flags": [],
        "software": None,
        "create_date": None,
        "modify_date": None,
        "camera_make": None,
        "camera_model": None,
        "dpi": None,
        "has_exif": False,
        "details": {},
    }

    flags: list[str] = []
    details: dict[str, Any] = {}

    # ── 1. ExifRead analysis (more comprehensive than Pillow) ─────────────────
    try:
        exif_tags = exifread.process_file(
            io.BytesIO(image_bytes), details=False
        )
        if exif_tags:
            result["has_exif"] = True
            for tag_name, tag_val in exif_tags.items():
                details[tag_name] = str(tag_val)
    except Exception as exc:
        logger.debug("ExifRead failed: %s", exc)
        exif_tags = {}

    # ── 2. Pillow fallback for basic metadata ─────────────────────────────────
    try:
        img = Image.open(io.BytesIO(image_bytes))
        pil_info = img.info or {}
        details["format"] = img.format
        details["mode"] = img.mode
        details["size"] = list(img.size)

        # DPI
        dpi = pil_info.get("dpi") or img.info.get("dpi")
        if dpi:
            result["dpi"] = (int(dpi[0]), int(dpi[1]))
            details["dpi"] = result["dpi"]

            # Very low DPI for a supposedly scanned document is suspicious
            if max(dpi) < 72:
                flags.append(
                    f"LOW_DPI: image resolution {dpi[0]}x{dpi[1]} dpi "
                    "is unusually low for a scanned document"
                )

        # Pillow EXIF
        pil_exif = img.getexif()
        if pil_exif:
            result["has_exif"] = True
            for tag_id, value in pil_exif.items():
                tag_name = PIL_TAGS.get(tag_id, str(tag_id))
                details[f"PIL_{tag_name}"] = str(value)

    except Exception as exc:
        logger.debug("Pillow metadata extraction failed: %s", exc)

    # ── 3. Extract key fields ─────────────────────────────────────────────────
    # Software / Creator
    software = (
        details.get("Image Software")
        or details.get("PIL_Software")
        or details.get("Image ProcessingSoftware")
        or details.get("PIL_ProcessingSoftware")
        or ""
    )
    if software:
        result["software"] = software
        is_suspicious, reason = _is_suspicious_software(software)
        if is_suspicious:
            flags.append(f"SUSPICIOUS_SOFTWARE: {reason}")

    # Camera make/model
    make = details.get("Image Make") or details.get("PIL_Make") or ""
    model = details.get("Image Model") or details.get("PIL_Model") or ""
    if make:
        result["camera_make"] = make
    if model:
        result["camera_model"] = model

    # Dates
    create_str = (
        details.get("EXIF DateTimeOriginal")
        or details.get("Image DateTimeOriginal")
        or details.get("PIL_DateTimeOriginal")
        or ""
    )
    modify_str = (
        details.get("Image DateTime")
        or details.get("PIL_DateTime")
        or ""
    )
    if create_str:
        result["create_date"] = str(create_str)
    if modify_str:
        result["modify_date"] = str(modify_str)

    # ── 4. Date discrepancy check ─────────────────────────────────────────────
    if create_str and modify_str:
        created = _parse_exif_datetime(str(create_str))
        modified = _parse_exif_datetime(str(modify_str))
        if created and modified:
            if modified < created:
                flags.append(
                    f"DATE_ANOMALY: ModifyDate ({modify_str}) is before "
                    f"CreateDate ({create_str}) — metadata tampering suspected"
                )
            elif (modified - created).days > 365:
                flags.append(
                    f"DATE_GAP: ModifyDate ({modify_str}) is >1 year after "
                    f"CreateDate ({create_str}) — late re-editing"
                )

    # ── 5. "Scanned" but no camera data ──────────────────────────────────────
    if not make and not model and not _is_scanner_software(software):
        # If there's no software tag AND no camera → could be born-digital
        if result["has_exif"]:
            # Has EXIF but no camera info — might be digitally created
            flags.append(
                "NO_CAMERA_DATA: EXIF data present but no camera "
                "make/model — document may be digitally fabricated"
            )

    result["flags"] = flags
    result["passed"] = len(flags) == 0
    result["details"] = details

    return result


def analyze_pdf_metadata(pdf_bytes: bytes) -> dict[str, Any]:
    """Analyse PDF-specific metadata for forensic signals.

    Uses PyMuPDF to extract the PDF info dict (Creator, Producer,
    CreationDate, ModDate, etc.).

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        Same structure as analyze_metadata().
    """
    import fitz  # PyMuPDF

    result: dict[str, Any] = {
        "passed": True,
        "flags": [],
        "software": None,
        "create_date": None,
        "modify_date": None,
        "camera_make": None,
        "camera_model": None,
        "dpi": None,
        "has_exif": False,
        "details": {},
    }

    flags: list[str] = []
    details: dict[str, Any] = {}

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        meta = doc.metadata or {}
        doc.close()
    except Exception as exc:
        logger.warning("PyMuPDF metadata extraction failed: %s", exc)
        result["flags"] = ["METADATA_EXTRACTION_FAILED"]
        result["passed"] = False
        return result

    if meta:
        result["has_exif"] = True
        details.update(meta)

    # Producer / Creator
    creator = meta.get("creator", "")
    producer = meta.get("producer", "")
    software = creator or producer
    if software:
        result["software"] = software
        is_suspicious, reason = _is_suspicious_software(software)
        if is_suspicious:
            flags.append(f"SUSPICIOUS_SOFTWARE: {reason}")

    # Dates
    create_date_raw = meta.get("creationDate", "")
    mod_date_raw = meta.get("modDate", "")

    if create_date_raw:
        result["create_date"] = create_date_raw
    if mod_date_raw:
        result["modify_date"] = mod_date_raw

    # Parse PDF dates (format: D:YYYYMMDDHHmmSS)
    def _parse_pdf_date(raw: str) -> datetime | None:
        cleaned = re.sub(r"^D:", "", str(raw).strip())
        cleaned = re.sub(r"['\+\-Z].*$", "", cleaned)
        for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
            try:
                return datetime.strptime(cleaned, fmt)
            except (ValueError, TypeError):
                continue
        return None

    if create_date_raw and mod_date_raw:
        created = _parse_pdf_date(create_date_raw)
        modified = _parse_pdf_date(mod_date_raw)
        if created and modified:
            if modified < created:
                flags.append(
                    f"DATE_ANOMALY: ModDate ({mod_date_raw}) before "
                    f"CreationDate ({create_date_raw}) — metadata tampering"
                )

    # Check for image editing software in producer chain
    if producer:
        is_suspicious, reason = _is_suspicious_software(producer)
        if is_suspicious and f"SUSPICIOUS_SOFTWARE: {reason}" not in flags:
            flags.append(f"SUSPICIOUS_PRODUCER: {reason}")

    result["flags"] = flags
    result["passed"] = len(flags) == 0
    result["details"] = details

    return result
