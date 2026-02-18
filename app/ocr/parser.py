"""
OCR Parser
Extracts structured fields from raw OCR text using regex + NLP.
When table_data is provided (from PPStructure), structured rows are used
directly for amount/line-item extraction, reducing regex fragility.
"""
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class OCRParser:
    """
    Structured field extractor from raw OCR text.

    Handles multiple document types:
    - Medical invoices
    - Prescriptions
    - Discharge summaries
    - Motor repair estimates
    - Police reports
    """

    # ─────────────────────────────────────────────
    # Regex patterns
    # ─────────────────────────────────────────────

    PATTERNS = {
        # Amounts (handles INR, Rs., ₹, commas, decimals)
        "amounts": re.compile(
            r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)|"
            r"([\d,]+(?:\.\d{1,2})?)\s*(?:Rs\.?|INR|₹)",
            re.IGNORECASE
        ),

        # Total amount (lines with "total", "grand total", "net amount")
        "total_amount": re.compile(
            r"(?:grand\s+)?total(?:\s+amount)?[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
            re.IGNORECASE
        ),

        # Dates (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, "15 Jan 2024")
        "dates": re.compile(
            r"\b(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\b|"
            r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b|"
            r"\b(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})\b",
            re.IGNORECASE
        ),

        # Patient name (common patterns in medical docs)
        "patient_name": re.compile(
            r"(?:patient(?:'s)?\s+name|name of patient)[:\s]+([A-Za-z\s\.]+?)(?:\n|$|,|DOB|Age|D\.O\.B)",
            re.IGNORECASE
        ),

        # Hospital/Provider name
        "hospital_name": re.compile(
            r"^([A-Za-z\s]+(?:Hospital|Clinic|Medical Centre|Healthcare|Health Care|Labs?|Diagnostics))",
            re.IGNORECASE | re.MULTILINE
        ),

        # Invoice/Bill number
        "invoice_number": re.compile(
            r"(?:invoice|bill|receipt|voucher)\s*(?:no\.?|number|#)[:\s]*([A-Za-z0-9\-\/]+)",
            re.IGNORECASE
        ),

        # Policy number
        "policy_number": re.compile(
            r"(?:policy|pol\.?)\s*(?:no\.?|number|#)[:\s]*([A-Za-z0-9\-\/]+)",
            re.IGNORECASE
        ),

        # Vehicle number (for motor claims)
        "vehicle_number": re.compile(
            r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,2}\s*\d{4})\b",
            re.IGNORECASE
        ),

        # Diagnosis codes / ICD-10
        "icd_codes": re.compile(
            r"\b([A-Z]\d{2}(?:\.\d{1,3})?)\b"
        ),

        # Doctor name
        "doctor_name": re.compile(
            r"(?:Dr\.?|Doctor|Physician)[:\s]+([A-Za-z\s\.]+?)(?:\n|$|,|MD|MBBS|MS\b)",
            re.IGNORECASE
        ),

        # Hospital registration number
        "reg_number": re.compile(
            r"(?:reg(?:istration)?\.?\s*(?:no\.?|number|#))[:\s]*([A-Za-z0-9\-\/]+)",
            re.IGNORECASE
        ),

        # GST/Tax number
        "gst_number": re.compile(
            r"(?:GSTIN|GST\s*No\.?)[:\s]*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            re.IGNORECASE
        ),

        # Admission/Discharge dates
        "admission_date": re.compile(
            r"(?:admission|admitted|date of admission)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            re.IGNORECASE
        ),
        "discharge_date": re.compile(
            r"(?:discharge|discharged|date of discharge)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
            re.IGNORECASE
        ),
    }

    def parse(self, raw_text: str, document_type: str, table_data: list = None) -> Dict[str, Any]:
        """
        Parse raw OCR text into structured fields.

        Args:
            raw_text:      Raw OCR output text.
            document_type: Type of document (INVOICE, PRESCRIPTION, etc.).
            table_data:    Optional structured table rows from PPStructure —
                           list of rows, each row a list of cell strings.
                           When provided, amount and line-item extraction uses
                           table cells directly instead of regex on raw text.

        Returns:
            Dictionary of extracted fields.
        """
        if not raw_text or not raw_text.strip():
            return {"parse_error": "Empty OCR text", "document_type": document_type}

        table_data = table_data or []

        # Base extraction (common to all documents)
        result = {
            "document_type": document_type,
            "extracted_amounts": self._extract_amounts_from_tables(table_data)
                                 or self._extract_amounts(raw_text),
            "total_amount": self._extract_total_from_tables(table_data)
                            or self._extract_total_amount(raw_text),
            "dates": self._extract_dates(raw_text),
            "invoice_number": self._extract_field("invoice_number", raw_text),
            "hospital_name": self._extract_field("hospital_name", raw_text),
            "gst_number": self._extract_field("gst_number", raw_text),
            "reg_number": self._extract_field("reg_number", raw_text),
        }

        # Attach structured line items when available (invoices, discharge summaries)
        if table_data:
            result["line_items"] = self._build_line_items(table_data)

        # Document-specific extraction
        if document_type in ("INVOICE", "ESTIMATE"):
            result.update(self._parse_invoice(raw_text))

        elif document_type in ("PRESCRIPTION", "MEDICAL_REPORT"):
            result.update(self._parse_medical(raw_text))

        elif document_type == "DISCHARGE_SUMMARY":
            result.update(self._parse_discharge(raw_text))

        elif document_type == "POLICE_REPORT":
            result.update(self._parse_police_report(raw_text))

        elif document_type == "VEHICLE_RC":
            result.update(self._parse_vehicle_rc(raw_text))

        # Remove None values
        result = {k: v for k, v in result.items() if v is not None}

        logger.debug(f"Parsed {len(result)} fields from {document_type}")
        return result

    # ─────────────────────────────────────────────
    # Table-data helpers (PPStructure rows)
    # ─────────────────────────────────────────────

    def _extract_amounts_from_tables(self, table_data: list) -> list:
        """
        Extract all numeric amounts from structured table cells.
        More reliable than regex on raw_text for itemized invoices.
        """
        amounts = []
        amount_re = re.compile(r"[\d,]+(?:\.\d{1,2})?")
        for row in table_data:
            for cell in row:
                cell = str(cell).replace(",", "")
                for m in amount_re.finditer(cell):
                    try:
                        val = float(m.group())
                        if val > 0:
                            amounts.append(val)
                    except ValueError:
                        pass
        return sorted(set(amounts), reverse=True)[:20]

    def _extract_total_from_tables(self, table_data: list) -> Optional[float]:
        """
        Find the total amount from a table by scanning for 'total' keyword
        in the first cell and parsing the last cell as amount.
        """
        total_re = re.compile(r"\btotal\b", re.IGNORECASE)
        amount_re = re.compile(r"[\d,]+(?:\.\d{1,2})?")
        for row in table_data:
            if row and total_re.search(str(row[0])):
                # Scan cells right-to-left for first numeric value
                for cell in reversed(row):
                    cell_clean = str(cell).replace(",", "")
                    m = amount_re.search(cell_clean)
                    if m:
                        try:
                            return float(m.group())
                        except ValueError:
                            pass
        return None

    def _build_line_items(self, table_data: list) -> list:
        """
        Convert raw table rows into structured line-item dicts.
        Skips header rows (all-text rows at the top).

        Returns list like:
          [{"description": "Consultation", "quantity": 1, "amount": 500.0}, ...]
        """
        items = []
        amount_re = re.compile(r"^[\d,]+(?:\.\d{1,2})?$")
        for row in table_data:
            if len(row) < 2:
                continue
            cells = [str(c).strip() for c in row]
            # Skip pure header rows
            if all(not amount_re.match(c.replace(",", "")) for c in cells):
                continue
            # Last numeric cell = amount, first cell = description
            amount = None
            for cell in reversed(cells):
                clean = cell.replace(",", "")
                if amount_re.match(clean):
                    try:
                        amount = float(clean)
                        break
                    except ValueError:
                        pass
            if amount is not None:
                items.append({
                    "description": cells[0],
                    "amount": amount,
                    "raw_row": cells,
                })
        return items

    # ─────────────────────────────────────────────
    # Field extractors
    # ─────────────────────────────────────────────

    def _extract_amounts(self, text: str) -> list:
        """Extract all monetary amounts found in text"""
        amounts = []
        for match in self.PATTERNS["amounts"].finditer(text):
            raw = (match.group(1) or match.group(2) or "").replace(",", "")
            try:
                amounts.append(float(raw))
            except ValueError:
                continue
        return sorted(set(amounts), reverse=True)[:10]  # Top 10 amounts

    def _extract_total_amount(self, text: str) -> Optional[float]:
        """Extract the final total amount"""
        match = self.PATTERNS["total_amount"].search(text)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except (ValueError, AttributeError):
                pass

        # Fallback: largest amount is often the total
        amounts = self._extract_amounts(text)
        return amounts[0] if amounts else None

    def _extract_dates(self, text: str) -> list:
        """Extract and normalize all dates"""
        raw_dates = []
        for match in self.PATTERNS["dates"].finditer(text):
            date_str = match.group(1) or match.group(2) or match.group(3)
            if date_str:
                raw_dates.append(date_str.strip())

        # Normalize dates
        normalized = []
        for d in raw_dates:
            try:
                parsed = date_parser.parse(d, dayfirst=True)
                normalized.append(parsed.strftime("%Y-%m-%d"))
            except Exception:
                normalized.append(d)

        return list(dict.fromkeys(normalized))  # Deduplicate preserving order

    def _extract_field(self, pattern_key: str, text: str) -> Optional[str]:
        """Generic single field extractor"""
        match = self.PATTERNS[pattern_key].search(text)
        if match:
            return match.group(1).strip() if match.lastindex >= 1 else match.group(0).strip()
        return None

    # ─────────────────────────────────────────────
    # Document-type specific parsers
    # ─────────────────────────────────────────────

    def _parse_invoice(self, text: str) -> Dict[str, Any]:
        """Additional fields for medical invoices"""
        return {
            "patient_name": self._extract_field("patient_name", text),
            "doctor_name": self._extract_field("doctor_name", text),
            "hospital_name": self._extract_field("hospital_name", text),
        }

    def _parse_medical(self, text: str) -> Dict[str, Any]:
        """Additional fields for prescriptions and medical reports"""
        return {
            "patient_name": self._extract_field("patient_name", text),
            "doctor_name": self._extract_field("doctor_name", text),
            "diagnosis_codes": self.PATTERNS["icd_codes"].findall(text) or [],
        }

    def _parse_discharge(self, text: str) -> Dict[str, Any]:
        """Additional fields for discharge summaries"""
        return {
            "patient_name": self._extract_field("patient_name", text),
            "doctor_name": self._extract_field("doctor_name", text),
            "admission_date": self._extract_field("admission_date", text),
            "discharge_date": self._extract_field("discharge_date", text),
            "diagnosis_codes": self.PATTERNS["icd_codes"].findall(text) or [],
        }

    def _parse_police_report(self, text: str) -> Dict[str, Any]:
        """Additional fields for police/FIR reports"""
        return {
            "vehicle_number": self._extract_field("vehicle_number", text),
            "fir_number": self._extract_field("invoice_number", text),  # Reuse pattern
        }

    def _parse_vehicle_rc(self, text: str) -> Dict[str, Any]:
        """Fields for Vehicle RC documents (motor claims)."""
        return {
            "vehicle_number": self._extract_field("vehicle_number", text),
            "chassis_number": self._extract_re(
                r"(?:chassis|chasis|ch\.?\s*no\.?)[:\s]+([A-Za-z0-9]+)", text),
            "engine_number": self._extract_re(
                r"(?:engine|eng\.?\s*no\.?)[:\s]+([A-Za-z0-9]+)", text),
            "owner_name": self._extract_re(
                r"(?:owner(?:'s)?\s+name|registered owner)[:\s]+([A-Za-z\s\.]+?)(?:\n|$|,)", text),
            "rto_code": self._extract_re(
                r"(?:rto|registering authority)[:\s]+([A-Za-z0-9\s\-]+?)(?:\n|$)", text),
            "fuel_type": self._extract_re(
                r"(?:fuel\s+type|fuel)[:\s]+(petrol|diesel|electric|cng|lpg|hybrid)",
                text, flags=re.IGNORECASE),
            "registration_date": self._extract_re(
                r"(?:date of registration|reg(?:\.|\s+date)?)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})",
                text),
        }

    def _extract_re(
        self,
        pattern: str,
        text: str,
        flags: int = 0,
    ) -> Optional[str]:
        """One-off regex extraction without adding to PATTERNS dict."""
        m = re.search(pattern, text, flags)
        if m:
            return m.group(1).strip() if m.lastindex and m.lastindex >= 1 else m.group(0).strip()
        return None