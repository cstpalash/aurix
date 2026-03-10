"""
Risk Assessment Engine for Aurix Platform

This module provides comprehensive risk assessment for automating
human-in-the-loop tasks. It evaluates multiple dimensions of risk
to determine safe automation boundaries.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Risk levels for task automation."""
    
    MINIMAL = "minimal"      # Can be fully automated immediately
    LOW = "low"              # Safe to automate with basic monitoring
    MEDIUM = "medium"        # Requires careful monitoring and gradual rollout
    HIGH = "high"            # Requires human oversight, shadow mode first
    CRITICAL = "critical"    # Cannot be automated, human required
    

class RiskDimension(str, Enum):
    """Dimensions considered in risk assessment."""
    
    IMPACT = "impact"                    # Potential damage if wrong
    BLAST_RADIUS = "blast_radius"        # Scope of affected systems/users
    REVERSIBILITY = "reversibility"      # Can the action be undone
    COMPLIANCE = "compliance"            # Regulatory/legal requirements
    SECURITY = "security"                # Security implications
    DATA_SENSITIVITY = "data_sensitivity"  # PII, secrets, etc.
    FREQUENCY = "frequency"              # How often this occurs
    COMPLEXITY = "complexity"            # Cognitive complexity required


@dataclass
class RiskFactor:
    """Individual risk factor measurement."""
    
    dimension: RiskDimension
    score: float  # 0.0 (no risk) to 1.0 (maximum risk)
    weight: float = 1.0
    rationale: str = ""
    evidence: List[str] = field(default_factory=list)
    
    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


class RiskProfile(BaseModel):
    """Complete risk profile for a task or workflow."""
    
    id: str = Field(description="Unique identifier for this risk profile")
    task_id: str = Field(description="Associated task identifier")
    task_type: str = Field(description="Type of task being assessed")
    
    # Risk factors
    factors: Dict[str, float] = Field(default_factory=dict)
    factor_weights: Dict[str, float] = Field(default_factory=dict)
    factor_rationales: Dict[str, str] = Field(default_factory=dict)
    
    # Computed scores
    overall_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)
    
    # Confidence requirements
    required_confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    min_samples_required: int = Field(default=100)
    
    # Metadata
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    assessed_by: str = Field(default="system")
    version: str = Field(default="1.0")
    
    # Recommendations
    automation_ready: bool = Field(default=False)
    recommended_mode: str = Field(default="shadow")  # shadow, suggest, auto_review, full_auto
    mitigation_strategies: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RiskAssessor:
    """
    Main risk assessment engine.
    
    Evaluates tasks and workflows to determine:
    - Overall risk level
    - Required confidence threshold for automation
    - Recommended automation mode
    - Mitigation strategies
    """
    
    # Default weights for risk dimensions
    DEFAULT_WEIGHTS = {
        RiskDimension.IMPACT: 1.5,
        RiskDimension.BLAST_RADIUS: 1.3,
        RiskDimension.REVERSIBILITY: 1.2,
        RiskDimension.COMPLIANCE: 1.4,
        RiskDimension.SECURITY: 1.5,
        RiskDimension.DATA_SENSITIVITY: 1.3,
        RiskDimension.FREQUENCY: 0.8,
        RiskDimension.COMPLEXITY: 1.0,
    }
    
    # Risk level thresholds
    RISK_THRESHOLDS = {
        RiskLevel.MINIMAL: 0.1,
        RiskLevel.LOW: 0.3,
        RiskLevel.MEDIUM: 0.5,
        RiskLevel.HIGH: 0.7,
        RiskLevel.CRITICAL: 0.85,
    }
    
    # Confidence requirements by risk level
    CONFIDENCE_REQUIREMENTS = {
        RiskLevel.MINIMAL: 0.90,
        RiskLevel.LOW: 0.95,
        RiskLevel.MEDIUM: 0.98,
        RiskLevel.HIGH: 0.995,
        RiskLevel.CRITICAL: 0.999,
    }
    
    # Minimum samples by risk level
    MIN_SAMPLES = {
        RiskLevel.MINIMAL: 20,
        RiskLevel.LOW: 50,
        RiskLevel.MEDIUM: 100,
        RiskLevel.HIGH: 500,
        RiskLevel.CRITICAL: 1000,
    }
    
    def __init__(
        self,
        custom_weights: Optional[Dict[RiskDimension, float]] = None,
        custom_thresholds: Optional[Dict[RiskLevel, float]] = None,
    ):
        """Initialize the risk assessor with optional custom configuration."""
        self.weights = {**self.DEFAULT_WEIGHTS}
        if custom_weights:
            self.weights.update(custom_weights)
            
        self.thresholds = {**self.RISK_THRESHOLDS}
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)
    
    def assess(
        self,
        task_id: str,
        task_type: str,
        factors: List[RiskFactor],
        context: Optional[Dict[str, Any]] = None,
    ) -> RiskProfile:
        """
        Perform comprehensive risk assessment.
        
        Args:
            task_id: Unique identifier for the task
            task_type: Type/category of task
            factors: List of risk factors with scores
            context: Additional context for assessment
            
        Returns:
            Complete RiskProfile with recommendations
        """
        context = context or {}
        
        # Calculate weighted risk score
        total_weighted_score = 0.0
        total_weight = 0.0
        
        factor_dict = {}
        weight_dict = {}
        rationale_dict = {}
        
        for factor in factors:
            weight = self.weights.get(factor.dimension, 1.0) * factor.weight
            total_weighted_score += factor.score * weight
            total_weight += weight
            
            factor_dict[factor.dimension.value] = factor.score
            weight_dict[factor.dimension.value] = weight
            rationale_dict[factor.dimension.value] = factor.rationale
        
        # Normalize overall score
        overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.5
        
        # Determine risk level
        risk_level = self._determine_risk_level(overall_score)
        
        # Calculate required confidence
        required_confidence = self.CONFIDENCE_REQUIREMENTS.get(risk_level, 0.95)
        min_samples = self.MIN_SAMPLES.get(risk_level, 100)
        
        # Determine recommended mode
        recommended_mode = self._recommend_mode(risk_level, context)
        
        # Generate mitigation strategies
        mitigations = self._generate_mitigations(factors, risk_level)
        
        # Check if automation ready
        automation_ready = risk_level in [RiskLevel.MINIMAL, RiskLevel.LOW]
        
        # Generate unique ID
        profile_id = self._generate_profile_id(task_id, task_type)
        
        return RiskProfile(
            id=profile_id,
            task_id=task_id,
            task_type=task_type,
            factors=factor_dict,
            factor_weights=weight_dict,
            factor_rationales=rationale_dict,
            overall_risk_score=round(overall_score, 4),
            risk_level=risk_level,
            required_confidence=required_confidence,
            min_samples_required=min_samples,
            automation_ready=automation_ready,
            recommended_mode=recommended_mode,
            mitigation_strategies=mitigations,
        )
    
    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score."""
        if score <= self.thresholds[RiskLevel.MINIMAL]:
            return RiskLevel.MINIMAL
        elif score <= self.thresholds[RiskLevel.LOW]:
            return RiskLevel.LOW
        elif score <= self.thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        elif score <= self.thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _recommend_mode(
        self,
        risk_level: RiskLevel,
        context: Dict[str, Any],
    ) -> str:
        """Recommend automation mode based on risk level."""
        mode_mapping = {
            RiskLevel.MINIMAL: "full_auto",
            RiskLevel.LOW: "auto_with_review",
            RiskLevel.MEDIUM: "suggestion",
            RiskLevel.HIGH: "shadow",
            RiskLevel.CRITICAL: "human_required",
        }
        
        base_mode = mode_mapping.get(risk_level, "shadow")
        
        # Check for overrides in context
        if context.get("force_shadow_mode"):
            return "shadow"
        if context.get("new_deployment"):
            # New deployments always start conservative
            if base_mode in ["full_auto", "auto_with_review"]:
                return "suggestion"
                
        return base_mode
    
    def _generate_mitigations(
        self,
        factors: List[RiskFactor],
        risk_level: RiskLevel,
    ) -> List[str]:
        """Generate mitigation strategies based on risk factors."""
        mitigations = []
        
        for factor in factors:
            if factor.score > 0.5:
                mitigations.extend(
                    self._get_dimension_mitigations(factor.dimension, factor.score)
                )
        
        # Add general mitigations based on risk level
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            mitigations.append("Implement real-time human escalation path")
            mitigations.append("Enable automatic rollback on error detection")
            mitigations.append("Maintain comprehensive audit logging")
            
        if risk_level == RiskLevel.CRITICAL:
            mitigations.append("Require dual approval for full automation")
            mitigations.append("Implement circuit breaker pattern")
            
        return list(set(mitigations))  # Remove duplicates
    
    def _get_dimension_mitigations(
        self,
        dimension: RiskDimension,
        score: float,
    ) -> List[str]:
        """Get mitigations specific to a risk dimension."""
        mitigations = {
            RiskDimension.IMPACT: [
                "Implement staged rollout",
                "Add pre-execution validation",
                "Enable dry-run mode for testing",
            ],
            RiskDimension.BLAST_RADIUS: [
                "Limit batch sizes",
                "Implement rate limiting",
                "Add scope constraints",
            ],
            RiskDimension.REVERSIBILITY: [
                "Create automated backup before changes",
                "Implement undo capability",
                "Add state snapshots",
            ],
            RiskDimension.COMPLIANCE: [
                "Enable compliance audit trail",
                "Add regulatory checkpoint validation",
                "Implement approval workflows",
            ],
            RiskDimension.SECURITY: [
                "Add security scanning pre-execution",
                "Implement least-privilege access",
                "Enable anomaly detection",
            ],
            RiskDimension.DATA_SENSITIVITY: [
                "Implement data masking",
                "Add access logging",
                "Enable encryption at rest",
            ],
            RiskDimension.COMPLEXITY: [
                "Break into smaller sub-tasks",
                "Add intermediate checkpoints",
                "Increase monitoring granularity",
            ],
        }
        
        return mitigations.get(dimension, [])
    
    def _generate_profile_id(self, task_id: str, task_type: str) -> str:
        """Generate unique profile ID."""
        content = f"{task_id}:{task_type}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def combine_profiles(
        self,
        profiles: List[RiskProfile],
        combination_strategy: str = "max",
    ) -> RiskProfile:
        """
        Combine multiple risk profiles into one.
        
        Useful for workflows with multiple tasks.
        
        Args:
            profiles: List of profiles to combine
            combination_strategy: How to combine scores
                - "max": Take maximum risk (most conservative)
                - "avg": Take average risk
                - "weighted_avg": Weight by task importance
                
        Returns:
            Combined RiskProfile
        """
        if not profiles:
            raise ValueError("At least one profile required")
            
        if len(profiles) == 1:
            return profiles[0]
        
        # Combine factors
        combined_factors = {}
        for profile in profiles:
            for dim, score in profile.factors.items():
                if dim not in combined_factors:
                    combined_factors[dim] = []
                combined_factors[dim].append(score)
        
        # Apply combination strategy
        final_factors = {}
        for dim, scores in combined_factors.items():
            if combination_strategy == "max":
                final_factors[dim] = max(scores)
            elif combination_strategy == "avg":
                final_factors[dim] = sum(scores) / len(scores)
            else:
                final_factors[dim] = max(scores)  # Default to conservative
        
        # Calculate overall score
        if combination_strategy == "max":
            overall_score = max(p.overall_risk_score for p in profiles)
        else:
            overall_score = sum(p.overall_risk_score for p in profiles) / len(profiles)
        
        risk_level = self._determine_risk_level(overall_score)
        
        return RiskProfile(
            id=self._generate_profile_id("combined", "workflow"),
            task_id="combined",
            task_type="workflow",
            factors=final_factors,
            overall_risk_score=round(overall_score, 4),
            risk_level=risk_level,
            required_confidence=self.CONFIDENCE_REQUIREMENTS.get(risk_level, 0.95),
            min_samples_required=self.MIN_SAMPLES.get(risk_level, 100),
            automation_ready=risk_level in [RiskLevel.MINIMAL, RiskLevel.LOW],
            recommended_mode=self._recommend_mode(risk_level, {}),
            mitigation_strategies=list(set(
                m for p in profiles for m in p.mitigation_strategies
            )),
        )


class CodeReviewRiskAssessor(RiskAssessor):
    """
    Specialized risk assessor for code review automation.
    
    Considers code-specific risk factors like:
    - File types changed
    - Code complexity metrics
    - Security-sensitive patterns
    - Test coverage impact
    """
    
    # File type risk weights
    FILE_RISK_WEIGHTS = {
        ".py": 0.3,
        ".js": 0.3,
        ".ts": 0.3,
        ".java": 0.4,
        ".go": 0.3,
        ".rs": 0.4,
        ".c": 0.6,
        ".cpp": 0.6,
        ".sql": 0.7,
        ".sh": 0.5,
        ".yml": 0.4,
        ".yaml": 0.4,
        ".json": 0.2,
        ".md": 0.1,
        ".txt": 0.1,
        ".env": 0.9,
        ".pem": 1.0,
        ".key": 1.0,
    }
    
    # High-risk patterns in code
    HIGH_RISK_PATTERNS = [
        r"password|secret|api_key|token",
        r"exec\(|eval\(|system\(",
        r"sudo|chmod\s+777",
        r"DROP\s+TABLE|DELETE\s+FROM|TRUNCATE",
        r"\.env|credentials|private_key",
        r"rm\s+-rf|rmdir",
        r"\\x[0-9a-fA-F]{2}",  # Hex encoded strings
    ]
    
    # Critical file paths
    CRITICAL_PATHS = [
        "src/auth/",
        "src/security/",
        "config/",
        "secrets/",
        ".github/workflows/",
        "terraform/",
        "kubernetes/",
        "docker/",
        "infrastructure/",
    ]
    
    def assess_code_change(
        self,
        pr_id: str,
        changed_files: List[Dict[str, Any]],
        diff_stats: Dict[str, int],
        code_metrics: Optional[Dict[str, Any]] = None,
    ) -> RiskProfile:
        """
        Assess risk of a code change (PR/commit).
        
        Args:
            pr_id: Pull request or commit identifier
            changed_files: List of changed files with metadata
            diff_stats: Diff statistics (additions, deletions, etc.)
            code_metrics: Optional complexity metrics
            
        Returns:
            RiskProfile for the code change
        """
        factors = []
        
        # Assess file type risk
        file_risk = self._assess_file_types(changed_files)
        factors.append(RiskFactor(
            dimension=RiskDimension.SECURITY,
            score=file_risk["score"],
            rationale=file_risk["rationale"],
            evidence=file_risk["evidence"],
        ))
        
        # Assess change size (blast radius)
        size_risk = self._assess_change_size(diff_stats, len(changed_files))
        factors.append(RiskFactor(
            dimension=RiskDimension.BLAST_RADIUS,
            score=size_risk["score"],
            rationale=size_risk["rationale"],
        ))
        
        # Assess critical path changes
        path_risk = self._assess_critical_paths(changed_files)
        factors.append(RiskFactor(
            dimension=RiskDimension.IMPACT,
            score=path_risk["score"],
            rationale=path_risk["rationale"],
            evidence=path_risk["evidence"],
        ))
        
        # Assess code complexity
        if code_metrics:
            complexity_risk = self._assess_complexity(code_metrics)
            factors.append(RiskFactor(
                dimension=RiskDimension.COMPLEXITY,
                score=complexity_risk["score"],
                rationale=complexity_risk["rationale"],
            ))
        
        # Assess reversibility (always relatively easy for code)
        factors.append(RiskFactor(
            dimension=RiskDimension.REVERSIBILITY,
            score=0.2,  # Code changes are usually reversible
            rationale="Code changes can be reverted via git",
        ))
        
        return self.assess(
            task_id=pr_id,
            task_type="code_review",
            factors=factors,
            context={"changed_files": len(changed_files)},
        )
    
    def _assess_file_types(
        self,
        changed_files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Assess risk based on file types changed."""
        max_risk = 0.0
        high_risk_files = []
        
        for file_info in changed_files:
            filename = file_info.get("filename", "")
            
            # Check extension
            for ext, risk in self.FILE_RISK_WEIGHTS.items():
                if filename.endswith(ext):
                    if risk > max_risk:
                        max_risk = risk
                    if risk >= 0.7:
                        high_risk_files.append(filename)
                    break
        
        return {
            "score": max_risk,
            "rationale": f"Highest risk file type score: {max_risk}",
            "evidence": high_risk_files,
        }
    
    def _assess_change_size(
        self,
        diff_stats: Dict[str, int],
        file_count: int,
    ) -> Dict[str, Any]:
        """Assess risk based on change size."""
        additions = diff_stats.get("additions", 0)
        deletions = diff_stats.get("deletions", 0)
        total_changes = additions + deletions
        
        # Risk increases with change size
        if total_changes < 50:
            score = 0.1
            rationale = "Small change"
        elif total_changes < 200:
            score = 0.3
            rationale = "Medium change"
        elif total_changes < 500:
            score = 0.5
            rationale = "Large change"
        elif total_changes < 1000:
            score = 0.7
            rationale = "Very large change"
        else:
            score = 0.9
            rationale = "Massive change - manual review recommended"
        
        # Adjust for file count
        if file_count > 20:
            score = min(1.0, score + 0.2)
            rationale += f" across {file_count} files"
        
        return {
            "score": score,
            "rationale": f"{rationale}: +{additions}/-{deletions} lines",
        }
    
    def _assess_critical_paths(
        self,
        changed_files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Assess risk based on critical paths affected."""
        critical_files = []
        
        for file_info in changed_files:
            filename = file_info.get("filename", "")
            for critical_path in self.CRITICAL_PATHS:
                if critical_path in filename:
                    critical_files.append(filename)
                    break
        
        if not critical_files:
            return {
                "score": 0.1,
                "rationale": "No critical paths affected",
                "evidence": [],
            }
        
        score = min(1.0, 0.3 + (len(critical_files) * 0.15))
        
        return {
            "score": score,
            "rationale": f"{len(critical_files)} critical path(s) affected",
            "evidence": critical_files,
        }
    
    def _assess_complexity(
        self,
        code_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assess risk based on code complexity metrics."""
        cyclomatic = code_metrics.get("cyclomatic_complexity", 0)
        cognitive = code_metrics.get("cognitive_complexity", 0)
        
        # Use the higher of the two
        max_complexity = max(cyclomatic, cognitive)
        
        if max_complexity < 5:
            score = 0.1
        elif max_complexity < 10:
            score = 0.3
        elif max_complexity < 20:
            score = 0.5
        elif max_complexity < 30:
            score = 0.7
        else:
            score = 0.9
        
        return {
            "score": score,
            "rationale": f"Cyclomatic: {cyclomatic}, Cognitive: {cognitive}",
        }


class SDLCRiskAssessor(RiskAssessor):
    """
    Specialized risk assessor for SDLC automation.
    
    Considers SDLC-specific factors like:
    - Phase of development
    - Environment being affected
    - Deployment frequency
    - Rollback complexity
    """
    
    # SDLC phase risk levels
    PHASE_RISK = {
        "requirements": 0.6,      # High - affects entire project
        "design": 0.5,            # Medium-high
        "development": 0.3,       # Low-medium
        "testing": 0.2,           # Low - can rerun
        "staging_deploy": 0.4,    # Medium
        "production_deploy": 0.8, # High
        "release": 0.7,           # Medium-high
        "maintenance": 0.5,       # Medium
    }
    
    # Environment risk levels
    ENV_RISK = {
        "development": 0.1,
        "testing": 0.2,
        "staging": 0.4,
        "production": 0.9,
    }
    
    def assess_sdlc_task(
        self,
        task_id: str,
        phase: str,
        environment: str,
        has_rollback: bool = True,
        has_tests: bool = True,
        previous_failures: int = 0,
    ) -> RiskProfile:
        """
        Assess risk of an SDLC task.
        
        Args:
            task_id: Unique task identifier
            phase: SDLC phase
            environment: Target environment
            has_rollback: Whether rollback is available
            has_tests: Whether automated tests exist
            previous_failures: Number of recent failures
            
        Returns:
            RiskProfile for the SDLC task
        """
        factors = []
        
        # Phase risk
        phase_score = self.PHASE_RISK.get(phase, 0.5)
        factors.append(RiskFactor(
            dimension=RiskDimension.IMPACT,
            score=phase_score,
            rationale=f"SDLC phase: {phase}",
        ))
        
        # Environment risk
        env_score = self.ENV_RISK.get(environment, 0.5)
        factors.append(RiskFactor(
            dimension=RiskDimension.BLAST_RADIUS,
            score=env_score,
            rationale=f"Target environment: {environment}",
        ))
        
        # Reversibility based on rollback capability
        reversibility_score = 0.2 if has_rollback else 0.8
        factors.append(RiskFactor(
            dimension=RiskDimension.REVERSIBILITY,
            score=reversibility_score,
            rationale=f"Rollback {'available' if has_rollback else 'not available'}",
        ))
        
        # Complexity based on test coverage
        complexity_score = 0.3 if has_tests else 0.7
        factors.append(RiskFactor(
            dimension=RiskDimension.COMPLEXITY,
            score=complexity_score,
            rationale=f"Automated tests {'exist' if has_tests else 'missing'}",
        ))
        
        # Adjust for previous failures (historical risk)
        if previous_failures > 0:
            failure_adjustment = min(0.3, previous_failures * 0.1)
            factors.append(RiskFactor(
                dimension=RiskDimension.FREQUENCY,
                score=0.5 + failure_adjustment,
                rationale=f"{previous_failures} recent failure(s)",
            ))
        
        return self.assess(
            task_id=task_id,
            task_type=f"sdlc_{phase}",
            factors=factors,
            context={
                "environment": environment,
                "has_rollback": has_rollback,
                "has_tests": has_tests,
            },
        )
