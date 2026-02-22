"""
Extraction Prompt Builder + Field Promoter.

This module is the bridge between the DB templates and the Gemini LLM:

1. ``build_extraction_prompt(template, document_type)``
   Takes an ``extraction_template`` JSONB from ``document_requirements``
   and returns a structured prompt string for Gemini.

2. ``PROMOTED_FIELD_MAP``
   Maps document_type_code → which extracted_data keys go to which
   promoted columns on ``claim_documents``.

3. ``promote_fields(document_type_code, extracted_data)``
   Returns a dict of promoted column values to set on the ClaimDocument row.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  1. PROMPT BUILDER — turns extraction_template → Gemini prompt
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_extraction_prompt(
    extraction_template: dict,
    document_type_code: str,
    display_name: str = "",
) -> str:
    """Build a structured prompt for Gemini given an extraction template.

    The prompt tells the LLM:
    - What type of document this is
    - Exactly which fields to extract (key, type, required/optional)
    - Special instructions
    - The output format (JSON matching the keys)

    Returns a string ready to be sent as the text part of a multimodal
    Gemini request alongside the document image.
    """
    fields = extraction_template.get("fields", [])
    instructions = extraction_template.get("instructions", "")

    # Build the field spec table for the LLM
    field_lines = []
    required_keys = []
    optional_keys = []

    for f in fields:
        key = f["key"]
        ftype = f.get("type", "string")
        required = f.get("required", False)
        label = f.get("label", key)
        req_marker = "REQUIRED" if required else "optional"

        line = f'  - "{key}" ({ftype}, {req_marker}): {label}'

        # For array fields with sub-fields, show the structure
        if ftype == "array" and "item_fields" in f:
            sub_keys = [sf["key"] for sf in f["item_fields"]]
            line += f'\n      Each item is an object with keys: {sub_keys}'

        field_lines.append(line)

        if required:
            required_keys.append(key)
        else:
            optional_keys.append(key)

    field_spec = "\n".join(field_lines)

    # Build the expected output JSON skeleton
    skeleton = {}
    for f in fields:
        key = f["key"]
        ftype = f.get("type", "string")
        if ftype == "string":
            skeleton[key] = "<extracted value>"
        elif ftype == "date":
            skeleton[key] = "DD/MM/YYYY"
        elif ftype == "number":
            skeleton[key] = 0
        elif ftype == "boolean":
            skeleton[key] = True
        elif ftype == "array":
            if "item_fields" in f:
                item = {sf["key"]: "..." for sf in f["item_fields"]}
                skeleton[key] = [item]
            else:
                skeleton[key] = ["..."]
        elif ftype == "array_of_strings":
            skeleton[key] = ["..."]
        else:
            skeleton[key] = "<value>"

    skeleton_json = json.dumps(skeleton, indent=2)

    prompt = f"""You are an expert document parser for insurance claims.

DOCUMENT TYPE: {document_type_code} — {display_name}

TASK: Extract the following fields from the uploaded document image/PDF.
Return ONLY a valid JSON object with the extracted values. No markdown, no explanation.

FIELDS TO EXTRACT:
{field_spec}

SPECIAL INSTRUCTIONS:
{instructions}

IMPORTANT RULES:
1. For REQUIRED fields: you MUST extract a value. If truly not visible, set to null and I'll flag it.
2. For optional fields: extract if visible, otherwise omit the key or set to null.
3. Dates: always return in DD/MM/YYYY format.
4. Numbers/amounts: return as raw numbers WITHOUT commas or currency symbols (e.g. 145000 not "₹1,45,000").
5. Booleans: return true or false (lowercase).
6. Arrays: return as JSON arrays even if only one item.
7. Arrays (like medications, line_items): extract EVERY row visible in the table — NEVER skip a row because one cell is blank or illegible. Use null for any missing/illegible cell value. Never return an empty array if rows are visible.
8. Medication/drug tables: capture every row regardless of whether dosage, frequency, or duration is filled. Frequency in formats like "1+0+1" (morning+afternoon+night) must be kept EXACTLY as written. Copy drug names exactly as printed including abbreviations like Tab., Cap., brand name, and strength (e.g. "Tab. Ultrafen-plus", "Cap. Progon200mg").
9. If the document appears to be a DIFFERENT type than {document_type_code}, set a top-level key "_wrong_document_type": true and "_detected_type": "<what you think it is>".
10. Add a top-level "_extraction_notes" key with any observations (unclear text, potential issues, etc.)

EXPECTED OUTPUT FORMAT:
```json
{skeleton_json}
```

Now extract from the uploaded document."""

    return prompt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  2. PROMOTED FIELD MAP — which extracted_data keys map to which columns
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Format: document_type_code → { promoted_column: extracted_data_key }
# If an extracted_data key differs per doc type, we map it explicitly here.

PROMOTED_FIELD_MAP: dict[str, dict[str, str]] = {
    "AADHAAR": {
        "patient_name": "full_name",        # Aadhaar uses "full_name" not "patient_name"
        "document_number": "aadhaar_number",
        # no hospital_name, doctor_name, diagnosis, dates, amount
    },
    "PAN": {
        "patient_name": "full_name",
        "document_number": "pan_number",
    },
    "HOSPITAL_BILL": {
        "patient_name": "patient_name",
        "hospital_name": "hospital_name",
        "admission_date": "admission_date",
        "discharge_date": "discharge_date",
        "total_amount": "total_amount",
        "document_date": "bill_date",
        "document_number": "bill_number",
        "entity_gstin": "hospital_gstin",
        "entity_registration_no": "hospital_registration_no",
    },
    "DISCHARGE_SUMMARY": {
        "patient_name": "patient_name",
        "hospital_name": "hospital_name",
        "doctor_name": "treating_doctor_name",
        "diagnosis": "primary_diagnosis",
        "admission_date": "admission_date",
        "discharge_date": "discharge_date",
        "entity_registration_no": "hospital_registration_no",
    },
    "PRESCRIPTION": {
        "patient_name": "patient_name",
        "doctor_name": "doctor_name",
        "diagnosis": "diagnosis",
        "document_date": "prescription_date",
        # no hospital_name (clinic possible but not guaranteed)
    },
    "CLAIM_FORM": {
        "patient_name": "patient_name",
        "hospital_name": "hospital_name",
        "diagnosis": "diagnosis",
        "admission_date": "admission_date",
        "discharge_date": "discharge_date",
        "total_amount": "estimated_cost",
        "document_number": "policy_number",
        "entity_registration_no": "hospital_registration_no",
    },
    "LAB_REPORT": {
        "patient_name": "patient_name",
        "hospital_name": "lab_name",           # lab_name maps to hospital_name column
        "document_date": "report_date",
    },
    "PHARMACY_BILL": {
        "patient_name": "patient_name",
        "hospital_name": "pharmacy_name",
        "total_amount": "total_amount",
        "document_date": "bill_date",
        "document_number": "bill_number",
        "entity_gstin": "pharmacy_gstin",
        "entity_registration_no": "pharmacy_license",
    },
    "PREAUTH_LETTER": {
        "patient_name": "patient_name",
        "hospital_name": "hospital_name",
        "diagnosis": "diagnosis",
        "total_amount": "approved_amount",
        "document_date": "approval_date",
        "document_number": "preauth_number",
    },
    "FIR_REPORT": {
        "patient_name": "patient_name",
        "document_number": "fir_number",
        "document_date": "incident_date",
    },
    "DEATH_CERTIFICATE": {
        "patient_name": "deceased_name",
        "document_date": "date_of_death",
        "document_number": "registration_number",
    },
    "AMBULANCE_RECEIPT": {
        "patient_name": "patient_name",
        "hospital_name": "drop_location",      # drop hospital
        "total_amount": "amount",
        "document_date": "date",
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  3. FIELD PROMOTER — copies values from extracted_data → promoted columns
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _parse_date(value: Any) -> date | None:
    """Try to parse DD/MM/YYYY, YYYY-MM-DD, or other common formats."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None  # unparseable — service layer will flag this


def _parse_amount(value: Any) -> Decimal | None:
    """Parse a number, stripping commas and currency symbols."""
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    s = str(value).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def promote_fields(
    document_type_code: str,
    extracted_data: dict | None,
) -> dict[str, Any]:
    """Given OCR output, return a dict of promoted column values.

    Usage in service layer:
        promoted = promote_fields("HOSPITAL_BILL", extracted)
        for col, val in promoted.items():
            setattr(claim_document, col, val)

    Returns only non-None values, so partial extraction is fine.
    """
    if not extracted_data:
        return {}

    field_map = PROMOTED_FIELD_MAP.get(document_type_code, {})
    if not field_map:
        return {}

    result: dict[str, Any] = {}

    # Date columns that need parsing
    date_columns = {"admission_date", "discharge_date", "document_date"}
    # Amount columns that need parsing
    amount_columns = {"total_amount"}

    for promoted_col, source_key in field_map.items():
        raw_value = extracted_data.get(source_key)
        if raw_value is None:
            continue

        if promoted_col in date_columns:
            parsed = _parse_date(raw_value)
            if parsed:
                result[promoted_col] = parsed
        elif promoted_col in amount_columns:
            parsed = _parse_amount(raw_value)
            if parsed:
                result[promoted_col] = parsed
        else:
            # String columns — truncate to column max length
            val = str(raw_value).strip()
            if val:
                result[promoted_col] = val[:256]  # safe for String(256) cols

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  4. CROSS-DOCUMENT CONSISTENCY CHECKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Define which promoted columns must be consistent across which doc types
CONSISTENCY_RULES = {
    "patient_name": {
        "must_match_across": [
            "AADHAAR", "PAN", "HOSPITAL_BILL", "DISCHARGE_SUMMARY",
            "PRESCRIPTION", "CLAIM_FORM",
        ],
        "tolerance": "fuzzy",  # fuzzy name matching (handles Sr/Shri/Mr. etc.)
    },
    "hospital_name": {
        "must_match_across": [
            "HOSPITAL_BILL", "DISCHARGE_SUMMARY", "CLAIM_FORM",
        ],
        "tolerance": "fuzzy",
    },
    "doctor_name": {
        "must_match_across": [
            "DISCHARGE_SUMMARY", "PRESCRIPTION",
        ],
        "tolerance": "fuzzy",
    },
    "diagnosis": {
        "must_match_across": [
            "DISCHARGE_SUMMARY", "PRESCRIPTION", "CLAIM_FORM",
        ],
        "tolerance": "semantic",  # LLM checks if diagnoses are semantically same
    },
    "admission_date": {
        "must_match_across": [
            "HOSPITAL_BILL", "DISCHARGE_SUMMARY", "CLAIM_FORM",
        ],
        "tolerance": "exact",
    },
    "discharge_date": {
        "must_match_across": [
            "HOSPITAL_BILL", "DISCHARGE_SUMMARY",
        ],
        "tolerance": "exact",
    },
    "entity_gstin": {
        "must_match_across": [
            "HOSPITAL_BILL",  # pharmacy GST is different entity, so only hospital
        ],
        "tolerance": "exact",
    },
    "entity_registration_no": {
        "must_match_across": [
            "HOSPITAL_BILL", "DISCHARGE_SUMMARY", "CLAIM_FORM",
        ],
        "tolerance": "exact",
    },
}
