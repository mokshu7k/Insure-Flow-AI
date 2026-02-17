"""
Unit Tests: OCR Parser — no Tesseract needed, pure regex tests.
"""
import pytest
from app.ocr.parser import OCRParser


@pytest.fixture
def parser():
    return OCRParser()


class TestAmountExtraction:
    def test_rupee_symbol(self, parser):
        r = parser.parse("Total Amount: ₹75,000.00", "INVOICE")
        assert r["total_amount"] == 75_000.0

    def test_rs_prefix(self, parser):
        r = parser.parse("Grand Total Rs. 1,20,000", "INVOICE")
        assert r["total_amount"] == 120_000.0

    def test_inr_prefix(self, parser):
        r = parser.parse("Total Amount INR 45000", "INVOICE")
        assert r["total_amount"] == 45_000.0

    def test_multiple_amounts_collected(self, parser):
        r = parser.parse("Consult: ₹500\nMeds: ₹2,500\nTotal: ₹3,000", "INVOICE")
        assert len(r["extracted_amounts"]) >= 2
        assert r["total_amount"] == 3_000.0


class TestDateExtraction:
    def test_dd_mm_yyyy(self, parser):
        r = parser.parse("Date of Admission: 15/01/2024", "DISCHARGE_SUMMARY")
        assert "2024-01-15" in r["dates"]

    def test_yyyy_mm_dd(self, parser):
        r = parser.parse("Date: 2024-03-15", "OTHER")
        assert "2024-03-15" in r["dates"]


class TestDocumentTypeFields:
    def test_invoice_number(self, parser):
        r = parser.parse("Invoice No: INV-2024-00123", "INVOICE")
        assert r.get("invoice_number") == "INV-2024-00123"

    def test_gst_number(self, parser):
        r = parser.parse("GSTIN: 27AABCU9603R1ZX", "INVOICE")
        assert r.get("gst_number") == "27AABCU9603R1ZX"

    def test_icd_codes(self, parser):
        r = parser.parse("Diagnosis: I21.9 (Acute MI)\nSecondary: E11.9", "PRESCRIPTION")
        codes = r.get("diagnosis_codes", [])
        assert any("I21" in c for c in codes)

    def test_vehicle_number(self, parser):
        r = parser.parse("Vehicle No: MH 12 AB 1234", "POLICE_REPORT")
        assert r.get("vehicle_number") is not None


class TestEdgeCases:
    def test_empty_text(self, parser):
        r = parser.parse("", "INVOICE")
        assert "parse_error" in r

    def test_no_amounts(self, parser):
        r = parser.parse("No financial information here.", "OTHER")
        assert r["total_amount"] is None
        assert r["extracted_amounts"] == []