"""
Confidence Engine for Aurix Platform

This module tracks and calculates confidence scores for automated tasks,
enabling data-driven graduation from human oversight to full automation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
import numpy as np
from scipy import stats


class AutomationMode(str, Enum):
    """Automation modes representing graduation levels."""
    
    SHADOW = "shadow"                  # AI runs but human decides
    SUGGESTION = "suggestion"          # AI suggests, human approves
    AUTO_WITH_REVIEW = "auto_review"   # AI decides, human spot-checks
    FULL_AUTO = "full_auto"            # Complete automation
    HUMAN_REQUIRED = "human_required"  # Cannot automate


class OutcomeType(str, Enum):
    """Types of outcomes for automated decisions."""
    
    CORRECT = "correct"           # AI decision was correct
    INCORRECT = "incorrect"       # AI decision was wrong
    PARTIAL = "partial"           # AI decision was partially correct
    OVERRIDDEN = "overridden"     # Human overrode AI decision
    ESCALATED = "escalated"       # AI correctly escalated to human
    TIMEOUT = "timeout"           # Decision timed out


@dataclass
class Outcome:
    """Single outcome record for an automated decision."""
    
    task_id: str
    decision_id: str
    outcome_type: OutcomeType
    timestamp: datetime
    
    # Details
    ai_decision: Any = None
    human_decision: Optional[Any] = None
    severity: float = 1.0  # 0.0 (minor) to 1.0 (critical)
    
    # Context
    risk_level: str = "medium"
    automation_mode: str = "shadow"
    
    # Feedback
    feedback_provided: bool = False
    feedback_text: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """Check if outcome is considered successful."""
        return self.outcome_type in [
            OutcomeType.CORRECT,
            OutcomeType.ESCALATED,
        ]
    
    @property
    def is_failure(self) -> bool:
        """Check if outcome is a failure."""
        return self.outcome_type in [
            OutcomeType.INCORRECT,
        ]


class ConfidenceScore(BaseModel):
    """Confidence score with statistical backing."""
    
    task_type: str = Field(description="Type of task")
    
    # Core metrics
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    override_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Sample information
    total_samples: int = Field(default=0)
    successful_samples: int = Field(default=0)
    failed_samples: int = Field(default=0)
    overridden_samples: int = Field(default=0)
    
    # Statistical confidence
    confidence_interval: Tuple[float, float] = Field(default=(0.0, 1.0))
    confidence_level: float = Field(default=0.95)
    standard_error: float = Field(default=0.0)
    
    # Time-based metrics
    recent_success_rate: float = Field(default=0.0)  # Last 7 days
    trend: str = Field(default="stable")  # improving, stable, declining
    
    # Computed overall confidence
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Graduation eligibility
    meets_threshold: bool = Field(default=False)
    required_threshold: float = Field(default=0.95)
    samples_until_eligible: int = Field(default=0)
    
    # Current status
    current_mode: AutomationMode = Field(default=AutomationMode.SHADOW)
    recommended_mode: AutomationMode = Field(default=AutomationMode.SHADOW)
    
    # Timestamps
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    observation_start: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ConfidenceEngine:
    """
    Engine for calculating and tracking confidence in automated decisions.
    
    Key responsibilities:
    - Track outcomes of automated decisions
    - Calculate statistical confidence scores
    - Determine graduation eligibility
    - Detect performance degradation
    """
    
    # Default graduation thresholds
    GRADUATION_THRESHOLDS = {
        AutomationMode.SHADOW: 0.0,           # Always allowed
        AutomationMode.SUGGESTION: 0.85,      # 85% confidence
        AutomationMode.AUTO_WITH_REVIEW: 0.95, # 95% confidence
        AutomationMode.FULL_AUTO: 0.99,       # 99% confidence
    }
    
    # Minimum samples for graduation
    MIN_SAMPLES = {
        AutomationMode.SHADOW: 0,
        AutomationMode.SUGGESTION: 30,
        AutomationMode.AUTO_WITH_REVIEW: 100,
        AutomationMode.FULL_AUTO: 500,
    }
    
    # Observation period requirements (days)
    OBSERVATION_PERIODS = {
        AutomationMode.SHADOW: 0,
        AutomationMode.SUGGESTION: 7,
        AutomationMode.AUTO_WITH_REVIEW: 14,
        AutomationMode.FULL_AUTO: 30,
    }
    
    def __init__(
        self,
        custom_thresholds: Optional[Dict[AutomationMode, float]] = None,
        confidence_level: float = 0.95,
    ):
        """Initialize confidence engine."""
        self.thresholds = {**self.GRADUATION_THRESHOLDS}
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)
        
        self.confidence_level = confidence_level
        self._outcomes: Dict[str, List[Outcome]] = {}  # task_type -> outcomes
    
    def record_outcome(self, outcome: Outcome) -> None:
        """Record an outcome for tracking."""
        task_type = f"{outcome.risk_level}_{outcome.automation_mode}"
        
        if task_type not in self._outcomes:
            self._outcomes[task_type] = []
        
        self._outcomes[task_type].append(outcome)
    
    def calculate_confidence(
        self,
        task_type: str,
        outcomes: List[Outcome],
        required_threshold: float = 0.95,
        current_mode: AutomationMode = AutomationMode.SHADOW,
    ) -> ConfidenceScore:
        """
        Calculate confidence score from outcomes.
        
        Args:
            task_type: Type of task being assessed
            outcomes: List of outcomes to analyze
            required_threshold: Required confidence for graduation
            current_mode: Current automation mode
            
        Returns:
            ConfidenceScore with detailed metrics
        """
        if not outcomes:
            return ConfidenceScore(
                task_type=task_type,
                current_mode=current_mode,
                required_threshold=required_threshold,
            )
        
        # Count outcomes
        total = len(outcomes)
        successful = sum(1 for o in outcomes if o.is_success)
        failed = sum(1 for o in outcomes if o.is_failure)
        overridden = sum(1 for o in outcomes if o.outcome_type == OutcomeType.OVERRIDDEN)
        
        # Calculate rates
        success_rate = successful / total
        error_rate = failed / total
        override_rate = overridden / total
        
        # Calculate confidence interval using Wilson score
        ci_lower, ci_upper = self._wilson_score_interval(
            successful, total, self.confidence_level
        )
        
        # Calculate standard error
        standard_error = math.sqrt(
            (success_rate * (1 - success_rate)) / total
        ) if total > 0 else 0.0
        
        # Calculate recent metrics (last 7 days)
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_outcomes = [o for o in outcomes if o.timestamp > recent_cutoff]
        recent_success_rate = (
            sum(1 for o in recent_outcomes if o.is_success) / len(recent_outcomes)
            if recent_outcomes else success_rate
        )
        
        # Determine trend
        trend = self._calculate_trend(outcomes)
        
        # Calculate overall confidence (weighted by severity)
        weighted_success = sum(
            1.0 if o.is_success else 0.0
            for o in outcomes
        )
        weighted_total = sum(1.0 for o in outcomes)
        overall_confidence = weighted_success / weighted_total if weighted_total > 0 else 0.0
        
        # Apply penalty for recent errors
        if recent_success_rate < success_rate:
            penalty = (success_rate - recent_success_rate) * 0.5
            overall_confidence = max(0, overall_confidence - penalty)
        
        # Check graduation eligibility
        meets_threshold = (
            ci_lower >= required_threshold and
            total >= self.MIN_SAMPLES.get(current_mode, 100)
        )
        
        # Calculate samples until eligible
        samples_until = self._samples_until_threshold(
            successful, total, required_threshold
        )
        
        # Determine recommended mode
        recommended_mode = self._recommend_mode(
            overall_confidence, total, current_mode
        )
        
        # Get observation start
        observation_start = min(o.timestamp for o in outcomes) if outcomes else None
        
        return ConfidenceScore(
            task_type=task_type,
            success_rate=round(success_rate, 4),
            error_rate=round(error_rate, 4),
            override_rate=round(override_rate, 4),
            total_samples=total,
            successful_samples=successful,
            failed_samples=failed,
            overridden_samples=overridden,
            confidence_interval=(round(ci_lower, 4), round(ci_upper, 4)),
            confidence_level=self.confidence_level,
            standard_error=round(standard_error, 4),
            recent_success_rate=round(recent_success_rate, 4),
            trend=trend,
            overall_confidence=round(overall_confidence, 4),
            meets_threshold=meets_threshold,
            required_threshold=required_threshold,
            samples_until_eligible=samples_until,
            current_mode=current_mode,
            recommended_mode=recommended_mode,
            observation_start=observation_start,
        )
    
    def _wilson_score_interval(
        self,
        successes: int,
        total: int,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """
        Calculate Wilson score confidence interval.
        
        More accurate than normal approximation for small samples.
        """
        if total == 0:
            return (0.0, 1.0)
        
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p = successes / total
        
        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * math.sqrt(
            (p * (1 - p) + z**2 / (4 * total)) / total
        ) / denominator
        
        return (max(0, center - margin), min(1, center + margin))
    
    def _calculate_trend(self, outcomes: List[Outcome]) -> str:
        """Calculate trend direction from recent outcomes."""
        if len(outcomes) < 10:
            return "stable"
        
        # Split into first and second half
        sorted_outcomes = sorted(outcomes, key=lambda o: o.timestamp)
        mid = len(sorted_outcomes) // 2
        
        first_half = sorted_outcomes[:mid]
        second_half = sorted_outcomes[mid:]
        
        first_rate = sum(1 for o in first_half if o.is_success) / len(first_half)
        second_rate = sum(1 for o in second_half if o.is_success) / len(second_half)
        
        diff = second_rate - first_rate
        
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        else:
            return "stable"
    
    def _samples_until_threshold(
        self,
        current_successes: int,
        current_total: int,
        threshold: float,
    ) -> int:
        """
        Estimate samples needed to reach threshold.
        
        Assumes future success rate equals current rate.
        """
        if current_total == 0:
            return 100  # Default estimate
        
        current_rate = current_successes / current_total
        
        if current_rate >= threshold:
            return 0
        
        # Simple estimation: how many perfect outcomes needed
        # to bring lower CI bound above threshold
        for additional in range(1, 10000):
            new_total = current_total + additional
            new_successes = current_successes + additional
            ci_lower, _ = self._wilson_score_interval(
                new_successes, new_total, self.confidence_level
            )
            if ci_lower >= threshold:
                return additional
        
        return 10000  # Cap at 10000
    
    def _recommend_mode(
        self,
        confidence: float,
        samples: int,
        current_mode: AutomationMode,
    ) -> AutomationMode:
        """Recommend automation mode based on confidence."""
        # Check each mode from most automated to least
        modes = [
            AutomationMode.FULL_AUTO,
            AutomationMode.AUTO_WITH_REVIEW,
            AutomationMode.SUGGESTION,
            AutomationMode.SHADOW,
        ]
        
        for mode in modes:
            threshold = self.thresholds.get(mode, 1.0)
            min_samples = self.MIN_SAMPLES.get(mode, 0)
            
            if confidence >= threshold and samples >= min_samples:
                # Don't skip levels - can only go up one at a time
                current_idx = modes.index(current_mode) if current_mode in modes else 3
                recommended_idx = modes.index(mode)
                
                if recommended_idx < current_idx - 1:
                    # Would skip levels, only go up one
                    return modes[current_idx - 1]
                
                return mode
        
        return AutomationMode.SHADOW
    
    def check_degradation(
        self,
        task_type: str,
        outcomes: List[Outcome],
        baseline_confidence: float,
        degradation_threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Check for performance degradation.
        
        Returns alert if recent performance is below baseline.
        """
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_outcomes = [o for o in outcomes if o.timestamp > recent_cutoff]
        
        if len(recent_outcomes) < 10:
            return {
                "degraded": False,
                "message": "Insufficient recent data",
                "recent_samples": len(recent_outcomes),
            }
        
        recent_success = sum(1 for o in recent_outcomes if o.is_success)
        recent_rate = recent_success / len(recent_outcomes)
        
        degradation = baseline_confidence - recent_rate
        
        if degradation > degradation_threshold:
            return {
                "degraded": True,
                "message": f"Performance degraded by {degradation:.1%}",
                "baseline": baseline_confidence,
                "current": recent_rate,
                "degradation": degradation,
                "recent_samples": len(recent_outcomes),
                "recommendation": "Consider reverting to more conservative mode",
            }
        
        return {
            "degraded": False,
            "message": "Performance within acceptable range",
            "baseline": baseline_confidence,
            "current": recent_rate,
        }
    
    def simulate_graduation(
        self,
        current_confidence: float,
        current_samples: int,
        target_mode: AutomationMode,
        assumed_success_rate: float = None,
    ) -> Dict[str, Any]:
        """
        Simulate path to graduation for planning.
        
        Args:
            current_confidence: Current confidence level
            current_samples: Current sample count
            target_mode: Target automation mode
            assumed_success_rate: Assumed future success rate
            
        Returns:
            Graduation timeline estimation
        """
        if assumed_success_rate is None:
            assumed_success_rate = current_confidence
        
        target_threshold = self.thresholds.get(target_mode, 0.99)
        min_samples = self.MIN_SAMPLES.get(target_mode, 500)
        observation_days = self.OBSERVATION_PERIODS.get(target_mode, 30)
        
        # Calculate needed samples
        samples_needed = max(0, min_samples - current_samples)
        
        # Estimate additional samples for confidence
        if current_confidence < target_threshold:
            additional_for_confidence = self._samples_until_threshold(
                int(current_confidence * current_samples),
                current_samples,
                target_threshold,
            )
            samples_needed = max(samples_needed, additional_for_confidence)
        
        # Estimate timeline (assuming 10 samples per day average)
        samples_per_day = 10
        days_for_samples = samples_needed / samples_per_day
        total_days = max(days_for_samples, observation_days)
        
        return {
            "target_mode": target_mode.value,
            "current_confidence": current_confidence,
            "target_threshold": target_threshold,
            "current_samples": current_samples,
            "min_samples_required": min_samples,
            "additional_samples_needed": samples_needed,
            "observation_period_days": observation_days,
            "estimated_days_to_graduation": int(total_days),
            "estimated_date": (
                datetime.utcnow() + timedelta(days=total_days)
            ).isoformat(),
            "assumptions": {
                "success_rate": assumed_success_rate,
                "samples_per_day": samples_per_day,
            },
        }


class ConfidenceTracker:
    """
    Persistent confidence tracking with history.
    
    Tracks confidence over time for trend analysis
    and graduation decisions.
    """
    
    def __init__(self, engine: ConfidenceEngine):
        """Initialize with confidence engine."""
        self.engine = engine
        self._history: Dict[str, List[ConfidenceScore]] = {}
        self._outcomes: Dict[str, List[Outcome]] = {}
    
    def record(self, outcome: Outcome) -> ConfidenceScore:
        """Record outcome and return updated confidence."""
        key = f"{outcome.task_id}_{outcome.automation_mode}"
        
        if key not in self._outcomes:
            self._outcomes[key] = []
        
        self._outcomes[key].append(outcome)
        
        # Calculate new confidence
        confidence = self.engine.calculate_confidence(
            task_type=key,
            outcomes=self._outcomes[key],
            current_mode=AutomationMode(outcome.automation_mode),
        )
        
        # Store in history
        if key not in self._history:
            self._history[key] = []
        
        self._history[key].append(confidence)
        
        return confidence
    
    def get_history(
        self,
        task_type: str,
        days: int = 30,
    ) -> List[ConfidenceScore]:
        """Get confidence history for a task type."""
        if task_type not in self._history:
            return []
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [
            score for score in self._history[task_type]
            if score.calculated_at > cutoff
        ]
    
    def get_graduation_status(
        self,
        task_type: str,
    ) -> Dict[str, Any]:
        """Get comprehensive graduation status."""
        if task_type not in self._outcomes:
            return {
                "eligible": False,
                "reason": "No data available",
            }
        
        outcomes = self._outcomes[task_type]
        
        if not outcomes:
            return {
                "eligible": False,
                "reason": "No outcomes recorded",
            }
        
        # Get current confidence
        current_mode = AutomationMode(outcomes[-1].automation_mode)
        confidence = self.engine.calculate_confidence(
            task_type=task_type,
            outcomes=outcomes,
            current_mode=current_mode,
        )
        
        # Get next mode
        modes = list(AutomationMode)
        current_idx = modes.index(current_mode)
        next_mode = modes[current_idx + 1] if current_idx < len(modes) - 1 else None
        
        if next_mode is None:
            return {
                "eligible": False,
                "reason": "Already at maximum automation",
                "current_mode": current_mode.value,
            }
        
        # Check requirements
        threshold = self.engine.thresholds.get(next_mode, 0.99)
        min_samples = self.engine.MIN_SAMPLES.get(next_mode, 100)
        observation_days = self.engine.OBSERVATION_PERIODS.get(next_mode, 14)
        
        # Check observation period
        first_outcome = min(o.timestamp for o in outcomes)
        days_observed = (datetime.utcnow() - first_outcome).days
        
        requirements_met = {
            "confidence": confidence.overall_confidence >= threshold,
            "samples": len(outcomes) >= min_samples,
            "observation_period": days_observed >= observation_days,
        }
        
        eligible = all(requirements_met.values())
        
        return {
            "eligible": eligible,
            "current_mode": current_mode.value,
            "next_mode": next_mode.value,
            "requirements": {
                "confidence": {
                    "required": threshold,
                    "current": confidence.overall_confidence,
                    "met": requirements_met["confidence"],
                },
                "samples": {
                    "required": min_samples,
                    "current": len(outcomes),
                    "met": requirements_met["samples"],
                },
                "observation_period": {
                    "required_days": observation_days,
                    "observed_days": days_observed,
                    "met": requirements_met["observation_period"],
                },
            },
            "confidence_details": confidence.dict(),
        }
