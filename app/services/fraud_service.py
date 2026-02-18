"""
Fraud Service
Orchestrates AI fraud analysis agents
"""
from sqlalchemy.orm import Session
import uuid

from app.models.claim import Claim
from app.models.fraud import FraudAssessment
from app.schemas.fraud import FraudAnalysisResult
from app.ai_agents.orchestrator import FraudOrchestrator
from app.services.audit_service import AuditService
from app.services.claim_context_builder import ClaimContextBuilder
from app.core.constants import AuditAction


class FraudService:
    """
    Fraud detection service
    
    CRITICAL RESPONSIBILITIES:
    1. Orchestrate multi-agent fraud analysis
    2. Store explainable results
    3. Never auto-reject (human-in-loop enforcement)
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)
        self.orchestrator = FraudOrchestrator()
    
    def analyze_claim(self, claim: Claim) -> FraudAnalysisResult:
        """
        Analyze claim for fraud
        
        CRITICAL FLOW:
        1. Run multi-agent analysis
        2. Store explainable results
        3. Audit log
        4. Return result (caller decides status)
        
        Args:
            claim: Claim to analyze
        
        Returns:
            FraudAnalysisResult with score and explanation
        """
        # STEP 1: Build enriched claim context (includes historical features)
        builder = ClaimContextBuilder(self.db)
        claim_context = builder.build(claim)
        
        # STEP 2: Run multi-agent fraud analysis
        analysis_result = self.orchestrator.analyze(claim_context)
        
        # STEP 3: Store explainable fraud assessment with feature snapshot
        fraud_assessment = FraudAssessment(
            id=uuid.uuid4(),
            claim_id=claim.id,
            fraud_score=analysis_result.fraud_score,
            deterministic_signals_json=analysis_result.deterministic_flags,
            statistical_signals_json=analysis_result.statistical_flags,
            explanation_text=analysis_result.explanation,
            feature_snapshot_json=claim_context,
        )
        
        self.db.add(fraud_assessment)
        self.db.commit()
        self.db.refresh(fraud_assessment)
        
        # STEP 4: Audit log
        self.audit_service.log_action(
            actor_id=None,  # System action
            action_type=AuditAction.FRAUD_ANALYSIS_RUN,
            entity_type="CLAIM",
            entity_id=claim.id,
            metadata={
                "fraud_score": analysis_result.fraud_score,
                "deterministic_flags": analysis_result.deterministic_flags,
                "statistical_flags": analysis_result.statistical_flags,
            }
        )
        
        return analysis_result
    
    def get_fraud_assessment(self, claim_id: uuid.UUID) -> FraudAssessment:
        """
        Get fraud assessment for claim
        
        Args:
            claim_id: Claim ID
        
        Returns:
            FraudAssessment object or None
        """
        return self.db.query(FraudAssessment).filter(
            FraudAssessment.claim_id == claim_id
        ).order_by(FraudAssessment.created_at.desc()).first()