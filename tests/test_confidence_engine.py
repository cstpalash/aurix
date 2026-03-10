"""
Tests for confidence engine.
"""

import pytest
from datetime import datetime, timedelta

from aurix.core.confidence_engine import (
    ConfidenceEngine,
    ConfidenceTracker,
    AutomationMode,
    Outcome,
    OutcomeType,
    ConfidenceScore,
)


class TestConfidenceEngine:
    """Tests for ConfidenceEngine."""
    
    def test_calculate_confidence_no_outcomes(self):
        """Test confidence calculation with no outcomes."""
        engine = ConfidenceEngine()
        
        score = engine.calculate_confidence(
            task_type="test",
            outcomes=[],
        )
        
        assert score.total_samples == 0
        assert score.success_rate == 0.0
    
    def test_calculate_confidence_all_success(self):
        """Test confidence calculation with all successful outcomes."""
        engine = ConfidenceEngine()
        
        outcomes = [
            Outcome(
                task_id="t1",
                decision_id=f"d{i}",
                outcome_type=OutcomeType.CORRECT,
                timestamp=datetime.utcnow(),
            )
            for i in range(100)
        ]
        
        score = engine.calculate_confidence(
            task_type="test",
            outcomes=outcomes,
        )
        
        assert score.total_samples == 100
        assert score.success_rate == 1.0
        assert score.overall_confidence >= 0.95
    
    def test_calculate_confidence_mixed(self):
        """Test confidence calculation with mixed outcomes."""
        engine = ConfidenceEngine()
        
        outcomes = []
        
        # 80 successful
        for i in range(80):
            outcomes.append(Outcome(
                task_id="t1",
                decision_id=f"s{i}",
                outcome_type=OutcomeType.CORRECT,
                timestamp=datetime.utcnow(),
            ))
        
        # 20 failures
        for i in range(20):
            outcomes.append(Outcome(
                task_id="t1",
                decision_id=f"f{i}",
                outcome_type=OutcomeType.INCORRECT,
                timestamp=datetime.utcnow(),
            ))
        
        score = engine.calculate_confidence(
            task_type="test",
            outcomes=outcomes,
        )
        
        assert score.total_samples == 100
        assert score.success_rate == 0.8
        assert score.error_rate == 0.2
    
    def test_recommend_mode_low_confidence(self):
        """Test mode recommendation for low confidence."""
        engine = ConfidenceEngine()
        
        outcomes = [
            Outcome(
                task_id="t1",
                decision_id=f"d{i}",
                outcome_type=OutcomeType.CORRECT if i % 2 == 0 else OutcomeType.INCORRECT,
                timestamp=datetime.utcnow(),
            )
            for i in range(10)
        ]
        
        score = engine.calculate_confidence(
            task_type="test",
            outcomes=outcomes,
            current_mode=AutomationMode.SHADOW,
        )
        
        assert score.recommended_mode == AutomationMode.SHADOW
    
    def test_recommend_mode_high_confidence(self):
        """Test mode recommendation for high confidence."""
        engine = ConfidenceEngine()
        
        outcomes = [
            Outcome(
                task_id="t1",
                decision_id=f"d{i}",
                outcome_type=OutcomeType.CORRECT,
                timestamp=datetime.utcnow(),
            )
            for i in range(500)
        ]
        
        score = engine.calculate_confidence(
            task_type="test",
            outcomes=outcomes,
            current_mode=AutomationMode.AUTO_WITH_REVIEW,
        )
        
        assert score.recommended_mode in [
            AutomationMode.AUTO_WITH_REVIEW,
            AutomationMode.FULL_AUTO,
        ]
    
    def test_check_degradation(self):
        """Test degradation detection."""
        engine = ConfidenceEngine()
        
        # Historical outcomes - all good
        old_outcomes = [
            Outcome(
                task_id="t1",
                decision_id=f"old{i}",
                outcome_type=OutcomeType.CORRECT,
                timestamp=datetime.utcnow() - timedelta(days=30),
            )
            for i in range(50)
        ]
        
        # Recent outcomes - some failures
        recent_outcomes = [
            Outcome(
                task_id="t1",
                decision_id=f"new{i}",
                outcome_type=OutcomeType.CORRECT if i % 3 != 0 else OutcomeType.INCORRECT,
                timestamp=datetime.utcnow() - timedelta(days=1),
            )
            for i in range(30)
        ]
        
        all_outcomes = old_outcomes + recent_outcomes
        
        result = engine.check_degradation(
            task_type="test",
            outcomes=all_outcomes,
            baseline_confidence=0.95,
        )
        
        assert "degraded" in result


class TestConfidenceTracker:
    """Tests for ConfidenceTracker."""
    
    def test_record_outcome(self):
        """Test recording an outcome."""
        engine = ConfidenceEngine()
        tracker = ConfidenceTracker(engine)
        
        outcome = Outcome(
            task_id="pr_review",
            decision_id="d1",
            outcome_type=OutcomeType.CORRECT,
            timestamp=datetime.utcnow(),
            automation_mode="shadow",
        )
        
        score = tracker.record(outcome)
        
        assert score.total_samples == 1
        assert score.success_rate == 1.0
    
    def test_get_graduation_status(self):
        """Test getting graduation status."""
        engine = ConfidenceEngine()
        tracker = ConfidenceTracker(engine)
        
        # Record some outcomes
        for i in range(50):
            outcome = Outcome(
                task_id="pr_review",
                decision_id=f"d{i}",
                outcome_type=OutcomeType.CORRECT,
                timestamp=datetime.utcnow() - timedelta(days=i % 14),
                automation_mode="shadow",
            )
            tracker.record(outcome)
        
        status = tracker.get_graduation_status("pr_review_shadow")
        
        assert "eligible" in status
        assert "requirements" in status
