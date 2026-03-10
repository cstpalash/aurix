"""
Tests for risk assessment engine.
"""

import pytest
from datetime import datetime

from aurix.core.risk_assessor import (
    RiskAssessor,
    RiskLevel,
    RiskDimension,
    RiskFactor,
    RiskProfile,
    CodeReviewRiskAssessor,
    SDLCRiskAssessor,
)


class TestRiskAssessor:
    """Tests for the base RiskAssessor."""
    
    def test_assess_minimal_risk(self):
        """Test assessment of minimal risk factors."""
        assessor = RiskAssessor()
        
        factors = [
            RiskFactor(
                dimension=RiskDimension.IMPACT,
                score=0.05,
                rationale="Minimal impact",
            ),
            RiskFactor(
                dimension=RiskDimension.REVERSIBILITY,
                score=0.1,
                rationale="Easily reversible",
            ),
        ]
        
        profile = assessor.assess(
            task_id="test-001",
            task_type="test",
            factors=factors,
        )
        
        assert profile.risk_level == RiskLevel.MINIMAL
        assert profile.overall_risk_score < 0.1
        assert profile.automation_ready is True
    
    def test_assess_high_risk(self):
        """Test assessment of high risk factors."""
        assessor = RiskAssessor()
        
        factors = [
            RiskFactor(
                dimension=RiskDimension.IMPACT,
                score=0.9,
                rationale="Critical impact",
            ),
            RiskFactor(
                dimension=RiskDimension.SECURITY,
                score=0.8,
                rationale="Security sensitive",
            ),
            RiskFactor(
                dimension=RiskDimension.REVERSIBILITY,
                score=0.7,
                rationale="Difficult to reverse",
            ),
        ]
        
        profile = assessor.assess(
            task_id="test-002",
            task_type="critical_task",
            factors=factors,
        )
        
        assert profile.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert profile.overall_risk_score > 0.7
        assert profile.automation_ready is False
    
    def test_risk_profile_fields(self):
        """Test that risk profile contains all required fields."""
        assessor = RiskAssessor()
        
        factors = [
            RiskFactor(
                dimension=RiskDimension.COMPLEXITY,
                score=0.5,
                rationale="Medium complexity",
            ),
        ]
        
        profile = assessor.assess(
            task_id="test-003",
            task_type="test",
            factors=factors,
        )
        
        assert profile.id is not None
        assert profile.task_id == "test-003"
        assert profile.task_type == "test"
        assert profile.required_confidence > 0
        assert profile.min_samples_required > 0
        assert len(profile.mitigation_strategies) >= 0
    
    def test_combine_profiles(self):
        """Test combining multiple risk profiles."""
        assessor = RiskAssessor()
        
        profile1 = RiskProfile(
            id="p1",
            task_id="t1",
            task_type="test",
            overall_risk_score=0.3,
            risk_level=RiskLevel.LOW,
        )
        
        profile2 = RiskProfile(
            id="p2",
            task_id="t2",
            task_type="test",
            overall_risk_score=0.7,
            risk_level=RiskLevel.HIGH,
        )
        
        combined = assessor.combine_profiles([profile1, profile2], "max")
        
        assert combined.overall_risk_score == 0.7
        assert combined.risk_level == RiskLevel.HIGH


class TestCodeReviewRiskAssessor:
    """Tests for CodeReviewRiskAssessor."""
    
    def test_assess_simple_change(self):
        """Test assessment of a simple code change."""
        assessor = CodeReviewRiskAssessor()
        
        changed_files = [
            {"filename": "src/utils.py", "content": "def helper(): pass"},
        ]
        
        diff_stats = {"additions": 10, "deletions": 5}
        
        profile = assessor.assess_code_change(
            pr_id="pr-123",
            changed_files=changed_files,
            diff_stats=diff_stats,
        )
        
        assert profile.risk_level in [RiskLevel.MINIMAL, RiskLevel.LOW]
    
    def test_assess_sensitive_files(self):
        """Test assessment with sensitive file types."""
        assessor = CodeReviewRiskAssessor()
        
        changed_files = [
            {"filename": ".env", "content": "SECRET=xxx"},
            {"filename": "config/secrets.key", "content": "---"},
        ]
        
        diff_stats = {"additions": 5, "deletions": 0}
        
        profile = assessor.assess_code_change(
            pr_id="pr-456",
            changed_files=changed_files,
            diff_stats=diff_stats,
        )
        
        assert profile.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def test_assess_large_change(self):
        """Test assessment of a large code change."""
        assessor = CodeReviewRiskAssessor()
        
        changed_files = [
            {"filename": f"src/module{i}.py", "content": ""}
            for i in range(30)
        ]
        
        diff_stats = {"additions": 1500, "deletions": 500}
        
        profile = assessor.assess_code_change(
            pr_id="pr-789",
            changed_files=changed_files,
            diff_stats=diff_stats,
        )
        
        assert profile.overall_risk_score > 0.5


class TestSDLCRiskAssessor:
    """Tests for SDLCRiskAssessor."""
    
    def test_assess_staging_deployment(self):
        """Test assessment of staging deployment."""
        assessor = SDLCRiskAssessor()
        
        profile = assessor.assess_sdlc_task(
            task_id="deploy-staging",
            phase="staging_deploy",
            environment="staging",
            has_rollback=True,
            has_tests=True,
        )
        
        assert profile.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
    
    def test_assess_production_deployment(self):
        """Test assessment of production deployment."""
        assessor = SDLCRiskAssessor()
        
        profile = assessor.assess_sdlc_task(
            task_id="deploy-prod",
            phase="production_deploy",
            environment="production",
            has_rollback=True,
            has_tests=True,
        )
        
        assert profile.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
    
    def test_assess_without_rollback(self):
        """Test assessment without rollback capability."""
        assessor = SDLCRiskAssessor()
        
        profile = assessor.assess_sdlc_task(
            task_id="deploy-no-rollback",
            phase="production_deploy",
            environment="production",
            has_rollback=False,
            has_tests=True,
        )
        
        # Should have higher risk without rollback
        assert profile.overall_risk_score > 0.7
