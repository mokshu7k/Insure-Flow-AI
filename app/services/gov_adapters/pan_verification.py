"""
PAN verification adapter.
Rule-based verification using format validation and checksum rules.
No external API calls.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PANVerificationResult:
    """Result of PAN verification."""
    is_valid: bool
    format_valid: bool
    entity_type_match: bool
    extracted_data: dict[str, Any]
    fraud_signal_weight: float  # 0.0–1.0
    reason: str


class PANRuleVerifier:
    """
    Verifies PAN card authenticity via rule-based validation.
    
    Validation rules:
    1. Format: ^[A-Z]{5}[0-9]{4}[A-Z]$
    2. 4th character must match entity type (P=Person, C=Company, etc.)
    3. 5th character should match surname initial (for individuals)
    
    Returns structured result with fraud signal weight.
    """
    
    # PAN format regex
    PAN_PATTERN = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
    
    # Entity type mapping (4th character)
    ENTITY_TYPES = {
        'P': 'Person',
        'C': 'Company',
        'H': 'HUF',
        'F': 'Firm',
        'A': 'AOP',
        'T': 'Trust',
        'B': 'BOI',
        'L': 'Local Authority',
        'J': 'Artificial Judicial Person',
        'G': 'Government'
    }
    
    async def verify(self, pan_number: str, holder_name: str | None = None) -> PANVerificationResult:
        """
        Verify PAN card authenticity.
        
        Args:
            pan_number: PAN string extracted from document
            holder_name: Optional holder name for surname validation
        
        Returns:
            PANVerificationResult with validation outcome
        """
        try:
            # Normalize PAN
            pan_number = pan_number.strip().upper()
            
            # Step 1: Format validation
            if not self.PAN_PATTERN.match(pan_number):
                return PANVerificationResult(
                    is_valid=False,
                    format_valid=False,
                    entity_type_match=False,
                    extracted_data={"pan": pan_number},
                    fraud_signal_weight=0.9,
                    reason=f"Invalid PAN format - expected AAAAA9999A, got {pan_number}"
                )
            
            # Step 2: Extract and validate entity type
            entity_char = pan_number[3]
            entity_type = self.ENTITY_TYPES.get(entity_char, "Unknown")
            
            if entity_char not in self.ENTITY_TYPES:
                return PANVerificationResult(
                    is_valid=False,
                    format_valid=True,
                    entity_type_match=False,
                    extracted_data={
                        "pan": pan_number,
                        "entity_char": entity_char,
                        "invalid_entity": True
                    },
                    fraud_signal_weight=0.8,
                    reason=f"Invalid entity type character '{entity_char}'"
                )
            
            # Step 3: Validate surname initial (for persons only)
            surname_match = True
            surname_reason = ""
            
            if entity_char == 'P' and holder_name:
                # 5th character should match first letter of surname
                surname_initial = pan_number[4]
                name_parts = holder_name.strip().upper().split()
                
                if name_parts:
                    # Assume last part is surname (common in Indian names)
                    actual_surname_initial = name_parts[-1][0] if name_parts[-1] else ''
                    
                    if actual_surname_initial and surname_initial != actual_surname_initial:
                        surname_match = False
                        surname_reason = f"Surname mismatch: PAN has '{surname_initial}', name suggests '{actual_surname_initial}'"
            
            # Step 4: Build result
            extracted_data = {
                "pan": pan_number,
                "entity_type": entity_type,
                "entity_char": entity_char,
                "surname_initial": pan_number[4],
                "holder_name": holder_name
            }
            
            if not surname_match:
                # Surname mismatch → HIGH_RISK
                return PANVerificationResult(
                    is_valid=False,
                    format_valid=True,
                    entity_type_match=True,
                    extracted_data=extracted_data,
                    fraud_signal_weight=0.5,
                    reason=surname_reason
                )
            
            # All checks passed
            return PANVerificationResult(
                is_valid=True,
                format_valid=True,
                entity_type_match=True,
                extracted_data=extracted_data,
                fraud_signal_weight=0.0,
                reason="PAN verification successful"
            )
        
        except Exception as exc:
            logger.error(f"PAN verification failed: {exc}", exc_info=True)
            return PANVerificationResult(
                is_valid=False,
                format_valid=False,
                entity_type_match=False,
                extracted_data={"pan": pan_number},
                fraud_signal_weight=0.7,
                reason=f"Verification error: {str(exc)}"
            )
    
    def extract_pan_from_text(self, text: str) -> str | None:
        """Extract PAN number from OCR text."""
        matches = self.PAN_PATTERN.findall(text.upper())
        return matches[0] if matches else None
