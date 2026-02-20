"""
Example integration of DocumentGatekeeper with claim processing flow.

This demonstrates:
1. Document upload with automatic validation
2. Fraud analysis consuming validation signals
3. Narrative context generation for AI agents
"""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.document_service import upload_document
from app.services.fraud_service import run_fraud_analysis, get_document_validation_context


async def example_claim_workflow(
    claim_id: str,
    user_id: str,
    role: str,
    document_file,
    db: AsyncSession
):
    """
    Complete claim processing workflow with document validation.
    
    Flow:
    1. Upload document → DocumentGatekeeper validates
    2. Run fraud analysis → Consumes validation signals
    3. Get narrative context → For AI agent explanation
    """
    
    # ── Step 1: Upload and validate document ─────────────────────────────────
    # This automatically:
    # - Validates structure (MIME, size, corruption)
    # - Classifies with Gemini (type matching)
    # - Verifies authenticity (Aadhaar QR / PAN rules)
    # - Rejects with user-friendly error if invalid
    
    try:
        document = await upload_document(
            claim_id=claim_id,
            uploader_id=user_id,
            role=role,
            file=document_file,
            document_type="aadhaar",  # or "pan", "medical_bill", etc.
            db=db
        )
        
        print(f"✓ Document uploaded: {document.id}")
        print(f"  Validation status: {document.validation_status}")
        print(f"  Fraud signal weight: {document.fraud_signal_weight}")
        
    except Exception as exc:
        # User sees friendly message: "The uploaded document is incorrect"
        print(f"✗ Document rejected: {exc}")
        return
    
    # ── Step 2: Run fraud analysis ───────────────────────────────────────────
    # Fraud engine automatically:
    # - Loads document validation status
    # - Factors in fraud_signal_weight
    # - Overrides score if FLAGGED_CRITICAL
    
    fraud_assessment = await run_fraud_analysis(
        claim_id=claim_id,
        actor_id=user_id,
        role="ADJUSTER",
        db=db
    )
    
    print(f"✓ Fraud analysis complete")
    print(f"  Fraud score: {fraud_assessment.fraud_score}")
    print(f"  Risk level: {fraud_assessment.risk_level}")
    
    # ── Step 3: Get validation context for narrative ─────────────────────────
    # This provides structured data for Layer 6 narrative generation
    
    validation_context = await get_document_validation_context(
        claim_id=claim_id,
        db=db
    )
    
    print(f"✓ Validation context for AI agent:")
    print(f"  Status: {validation_context['validation_status']}")
    print(f"  Reason: {validation_context['validation_reason']}")
    print(f"  Authenticity verified: {validation_context['authenticity_verified']}")


# ── Direct DocumentGatekeeper usage (without DB) ──────────────────────────────
from app.services.document_gatekeeper import DocumentGatekeeper
from app.services.gov_adapters.aadhaar_verification import AadhaarQRVerifier
from app.services.gov_adapters.pan_verification import PANRuleVerifier
from app.config import settings


async def validate_document_standalone(file_bytes: bytes, filename: str):
    """
    Standalone validation without database persistence.
    
    Useful for:
    - Pre-upload validation in UI
    - Batch processing
    - Testing
    """
    
    # Initialize gatekeeper
    gatekeeper = DocumentGatekeeper(
        aadhaar_verifier=AadhaarQRVerifier(),
        pan_verifier=PANRuleVerifier(),
        gemini_api_key=settings.GCP_API_KEY
    )
    
    # Validate
    decision = await gatekeeper.validate_document(
        file_bytes=file_bytes,
        filename=filename,
        expected_type="aadhaar",
        extracted_text=None,
        holder_name=None
    )
    
    # Check result
    if decision.status == "accepted":
        print("✓ Document accepted")
        print(f"  Reason: {decision.reason}")
        print(f"  Fraud signal: {decision.fraud_signal_weight}")
    
    elif decision.status == "rejected_invalid":
        print("✗ Document rejected")
        print(f"  Reason: {decision.reason}")  # User-friendly message
        # Show to user: "The uploaded document is incorrect"
    
    elif decision.status in ("flagged_high_risk", "flagged_critical"):
        print("⚠ Document flagged")
        print(f"  Status: {decision.status}")
        print(f"  Reason: {decision.reason}")
        print(f"  Fraud signal: {decision.fraud_signal_weight}")
    
    return decision


# ── Fraud Engine Integration Example ──────────────────────────────────────────
def consume_validation_in_fraud_layer(context: dict):
    """
    Example of how fraud engine layer 1 consumes validation signals.
    
    This is called internally by the fraud orchestrator.
    """
    doc_validation = context.get("document_validation", {})
    
    validation_status = doc_validation.get("validation_status")
    fraud_signal_weight = doc_validation.get("fraud_signal_weight", 0.0)
    
    # Critical override: If document has critical issues, max fraud score
    if validation_status == "flagged_critical":
        return {
            "score": 1.0,
            "reason": "Critical document authenticity failure detected",
            "override": True
        }
    
    # High risk: Add weighted signal
    if validation_status == "flagged_high_risk":
        return {
            "score": fraud_signal_weight,
            "reason": doc_validation.get("validation_reason", "Document verification concern"),
            "override": False
        }
    
    # Accepted: No fraud signal from documents
    return {
        "score": 0.0,
        "reason": "Document validation passed",
        "override": False
    }


# ── Narrative Layer Integration Example ───────────────────────────────────────
async def build_narrative_prompt(claim_id: str, db: AsyncSession) -> str:
    """
    Example of building narrative prompt with validation context.
    
    Used in Layer 6 (AI narrative generation).
    """
    validation_context = await get_document_validation_context(claim_id, db)
    
    prompt = f"""Generate fraud explanation for claim {claim_id}.

Document Validation Context:
- Status: {validation_context['validation_status']}
- Reason: {validation_context['validation_reason']}
- Authenticity Verified: {validation_context['authenticity_verified']}
- Fraud Signal Weight: {validation_context['fraud_signal_weight']}

If document was flagged, explain why and how it impacts fraud risk.
If document was accepted, mention authentic verification passed.
"""
    
    return prompt
