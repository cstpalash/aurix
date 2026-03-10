"""
Code Review Automation Module for Aurix Platform

Provides comprehensive automated code review with:
- AI-powered intent analysis (understands what code DOES)
- AI-powered semantic risk assessment (detects auth, data, security changes)
- Multi-stage review pipeline
- Confidence-based automation graduation
- AI-enhanced code analysis via GPT-4o-mini
- Auto-merge when confidence thresholds are met
- Specific file/line annotations for human review
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aurix.ai.reviewer import AIReviewer, IntentAnalysis, SemanticRiskAnalysis

from aurix.core.risk_assessor import (
    CodeReviewRiskAssessor,
    RiskLevel,
    RiskProfile,
    RiskDimension,
    RiskFactor,
)
from aurix.core.confidence_engine import (
    AutomationMode,
    ConfidenceEngine,
    ConfidenceScore,
    ConfidenceTracker,
    Outcome,
    OutcomeType,
)
from aurix.models.review_action import (
    ReviewAction,
    ReviewActionResult,
    ReviewPriority,
    HumanReviewRequest,
    FileAnnotation,
    LineRange,
)
from aurix.config.team_config import (
    TeamConfig,
    ConfigLoader,
    load_team_config,
)


class ReviewDecision(str, Enum):
    """Possible review decisions."""
    
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    NEEDS_DISCUSSION = "needs_discussion"
    BLOCK = "block"


class ReviewCheckType(str, Enum):
    """Types of automated checks in code review."""
    
    STYLE = "style"
    SECURITY = "security"
    COMPLEXITY = "complexity"
    COVERAGE = "coverage"
    DOCUMENTATION = "documentation"
    LOGIC = "logic"
    PERFORMANCE = "performance"
    DEPENDENCIES = "dependencies"


class CodeIntent(str, Enum):
    """Detected intent of code changes."""
    
    FEATURE = "feature"           # New feature
    BUGFIX = "bugfix"             # Bug fix
    REFACTOR = "refactor"         # Code refactoring
    HOTFIX = "hotfix"             # Emergency fix
    DOCUMENTATION = "documentation"
    DEPENDENCY_UPDATE = "dependency_update"
    SECURITY_PATCH = "security_patch"
    PERFORMANCE = "performance"
    TEST = "test"
    CONFIG = "config"
    UNKNOWN = "unknown"


@dataclass
class ReviewCheck:
    """Result of a single review check."""
    
    check_type: ReviewCheckType
    passed: bool
    score: float  # 0.0 to 1.0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def issue_count(self) -> int:
        return len(self.issues)
    
    @property
    def critical_issues(self) -> List[Dict[str, Any]]:
        return [i for i in self.issues if i.get("severity") == "critical"]


class PullRequestInfo(BaseModel):
    """Information about a pull request."""
    
    pr_id: str
    repo: str
    title: str
    description: str = ""
    author: str = ""
    
    # Files changed
    files: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Statistics
    additions: int = 0
    deletions: int = 0
    changed_files_count: int = 0
    
    # Labels and metadata
    labels: List[str] = Field(default_factory=list)
    base_branch: str = "main"
    head_branch: str = ""
    
    # Detected properties
    detected_intent: Optional[CodeIntent] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReviewResult(BaseModel):
    """Complete result of automated code review."""
    
    pr_info: PullRequestInfo
    
    # Risk assessment
    risk_profile: RiskProfile
    
    # Check results
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Decision
    decision: ReviewDecision = ReviewDecision.NEEDS_DISCUSSION
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Automation status
    automation_mode: AutomationMode = AutomationMode.SHADOW
    human_review_required: bool = True
    escalation_reason: Optional[str] = None
    
    # Comments to post
    comments: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    
    # Timing
    review_duration_ms: int = 0
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)


class CodeReviewModule:
    """
    Complete code review automation module.
    
    Orchestrates the entire code review process with
    confidence-based automation graduation.
    """
    
    # Check weights for overall score
    CHECK_WEIGHTS = {
        ReviewCheckType.SECURITY: 2.0,
        ReviewCheckType.LOGIC: 1.5,
        ReviewCheckType.COMPLEXITY: 1.2,
        ReviewCheckType.COVERAGE: 1.0,
        ReviewCheckType.STYLE: 0.5,
        ReviewCheckType.DOCUMENTATION: 0.5,
        ReviewCheckType.PERFORMANCE: 1.0,
        ReviewCheckType.DEPENDENCIES: 1.0,
    }
    
    # Intent to risk mapping
    INTENT_RISK_ADJUSTMENT = {
        CodeIntent.HOTFIX: 0.3,      # Higher risk
        CodeIntent.SECURITY_PATCH: 0.2,
        CodeIntent.FEATURE: 0.0,
        CodeIntent.BUGFIX: -0.1,
        CodeIntent.REFACTOR: 0.1,
        CodeIntent.TEST: -0.2,       # Lower risk
        CodeIntent.DOCUMENTATION: -0.3,
    }
    
    def __init__(
        self,
        confidence_engine: Optional[ConfidenceEngine] = None,
        risk_assessor: Optional[CodeReviewRiskAssessor] = None,
        ai_reviewer: Optional["AIReviewer"] = None,
    ):
        """Initialize code review module."""
        self.confidence_engine = confidence_engine or ConfidenceEngine()
        self.risk_assessor = risk_assessor or CodeReviewRiskAssessor()
        
        # AI reviewer (optional - enhanced reviews when available)
        self._ai_reviewer = ai_reviewer
        self._ai_analysis: Optional[Any] = None  # Store last AI analysis
        
        # Tracking
        self.confidence_tracker = ConfidenceTracker(self.confidence_engine)
        self._review_history: List[ReviewResult] = []
        
        # Current automation mode per repo
        self._repo_modes: Dict[str, AutomationMode] = {}
        
        # Cache for AI analysis results
        self._intent_analysis: Optional[Any] = None
        self._semantic_risk: Optional[Any] = None
    
    async def review_pull_request(
        self,
        pr_info: PullRequestInfo,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReviewResult:
        """
        Perform automated code review on a pull request.
        
        The review pipeline:
        1. AI Intent Detection - Understand what the code DOES (not just title matching)
        2. AI Semantic Risk Assessment - Identify auth, data, security implications
        3. Execute Checks - Security, logic, style, complexity analysis
        4. Calculate Score - Weighted combination of all checks
        5. Make Decision - APPROVE, REQUEST_CHANGES, NEEDS_DISCUSSION, or BLOCK
        6. Check Escalation - Determine if human review is needed
        7. Generate Summary - Create PR comment with findings
        
        Args:
            pr_info: Pull request information
            context: Additional context
            
        Returns:
            ReviewResult with decision and details
        """
        context = context or {}
        start_time = datetime.utcnow()
        
        # Initialize AI reviewer
        await self._ensure_ai_reviewer()
        
        # Step 1: AI-powered intent detection
        # This reads the actual code to understand what changes do
        pr_info.detected_intent = await self._detect_intent_with_ai(pr_info)
        
        # Step 2: AI-powered semantic risk assessment
        # This identifies if code touches auth, data, security, etc.
        risk_profile = await self._assess_risk_with_ai(pr_info)
        
        # Step 3: Execute review checks (security, logic, style, etc.)
        automation_mode = self._get_automation_mode(pr_info.repo, risk_profile)
        
        check_results = await self._execute_checks(
            pr_info,
            context,
        )
        
        # Step 4: Calculate overall score
        overall_score = self._calculate_overall_score(check_results)
        
        # Step 5: Make decision
        decision, confidence = self._make_decision(
            overall_score,
            check_results,
            risk_profile,
        )
        
        # Step 6: Determine if human review needed
        human_required, escalation_reason = self._check_escalation(
            decision,
            confidence,
            risk_profile,
            automation_mode,
            check_results,
        )
        
        # Step 7: Generate comments
        comments = self._generate_comments(check_results)
        summary = self._generate_summary(
            pr_info,
            check_results,
            decision,
            confidence,
            ai_analysis=self._ai_analysis,
            intent_analysis=self._intent_analysis,
            semantic_risk=self._semantic_risk,
        )
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = ReviewResult(
            pr_info=pr_info,
            risk_profile=risk_profile,
            checks={k.value: v.__dict__ for k, v in check_results.items()},
            overall_score=overall_score,
            decision=decision,
            confidence=confidence,
            automation_mode=automation_mode,
            human_review_required=human_required,
            escalation_reason=escalation_reason,
            comments=comments,
            summary=summary,
            review_duration_ms=int(duration),
        )
        
        # Track for confidence scoring
        self._track_outcome(result)
        self._review_history.append(result)
        
        return result
    
    def _detect_intent(self, pr_info: PullRequestInfo) -> CodeIntent:
        """Detect the intent of the code changes."""
        title_lower = pr_info.title.lower()
        desc_lower = pr_info.description.lower()
        combined = f"{title_lower} {desc_lower}"
        
        # Check labels first
        label_mapping = {
            "hotfix": CodeIntent.HOTFIX,
            "bugfix": CodeIntent.BUGFIX,
            "bug": CodeIntent.BUGFIX,
            "feature": CodeIntent.FEATURE,
            "enhancement": CodeIntent.FEATURE,
            "security": CodeIntent.SECURITY_PATCH,
            "documentation": CodeIntent.DOCUMENTATION,
            "docs": CodeIntent.DOCUMENTATION,
            "refactor": CodeIntent.REFACTOR,
            "test": CodeIntent.TEST,
            "dependencies": CodeIntent.DEPENDENCY_UPDATE,
        }
        
        for label in pr_info.labels:
            label_lower = label.lower()
            for key, intent in label_mapping.items():
                if key in label_lower:
                    return intent
        
        # Check title/description patterns
        patterns = {
            CodeIntent.HOTFIX: r"hotfix|urgent|critical fix|emergency",
            CodeIntent.BUGFIX: r"fix|bug|issue|resolve|closes?\s*#\d+",
            CodeIntent.FEATURE: r"feat|feature|add|implement|new",
            CodeIntent.SECURITY_PATCH: r"security|cve|vulnerability|patch",
            CodeIntent.REFACTOR: r"refactor|clean|improve|optimize",
            CodeIntent.DOCUMENTATION: r"docs?|readme|documentation|comment",
            CodeIntent.TEST: r"test|spec|coverage",
            CodeIntent.PERFORMANCE: r"perf|performance|speed|optimize",
            CodeIntent.DEPENDENCY_UPDATE: r"bump|upgrade|dependency|update.+version",
            CodeIntent.CONFIG: r"config|settings|env",
        }
        
        for intent, pattern in patterns.items():
            if re.search(pattern, combined, re.IGNORECASE):
                return intent
        
        # Check file patterns
        file_names = [f.get("filename", "") for f in pr_info.files]
        file_str = " ".join(file_names).lower()
        
        if all("test" in f or "spec" in f for f in file_names if f):
            return CodeIntent.TEST
        if all(".md" in f or "readme" in f or "doc" in f for f in file_names if f):
            return CodeIntent.DOCUMENTATION
        if any("package.json" in f or "requirements" in f or "cargo.toml" in f for f in file_names):
            if pr_info.changed_files_count <= 3:
                return CodeIntent.DEPENDENCY_UPDATE
        
        return CodeIntent.UNKNOWN
    
    async def _ensure_ai_reviewer(self) -> None:
        """Initialize AI reviewer if not already done."""
        if self._ai_reviewer is None:
            try:
                from aurix.ai.reviewer import AIReviewer
                self._ai_reviewer = AIReviewer()
                if not self._ai_reviewer.is_available():
                    self._ai_reviewer = None
            except ImportError:
                pass
    
    async def _detect_intent_with_ai(self, pr_info: PullRequestInfo) -> CodeIntent:
        """
        AI-powered intent detection.
        
        Instead of just pattern matching on titles, this actually reads
        the code diff and uses AI to understand what the changes do.
        Falls back to heuristic detection if AI unavailable.
        
        Args:
            pr_info: Pull request information with code diffs
            
        Returns:
            Detected intent (CodeIntent enum)
        """
        # Try AI-powered intent detection
        if self._ai_reviewer is not None:
            try:
                from aurix.ai.reviewer import IntentAnalysis
                
                # Call AI to analyze the actual code
                intent_analysis: IntentAnalysis = await self._ai_reviewer.analyze_intent(
                    title=pr_info.title,
                    description=pr_info.description,
                    files=pr_info.files,
                    labels=pr_info.labels,
                )
                
                # Cache for summary generation
                self._intent_analysis = intent_analysis
                
                # Map AI-detected intent to our CodeIntent enum
                intent_mapping = {
                    "feature": CodeIntent.FEATURE,
                    "bugfix": CodeIntent.BUGFIX,
                    "bug_fix": CodeIntent.BUGFIX,
                    "hotfix": CodeIntent.HOTFIX,
                    "hot_fix": CodeIntent.HOTFIX,
                    "refactor": CodeIntent.REFACTOR,
                    "refactoring": CodeIntent.REFACTOR,
                    "test": CodeIntent.TEST,
                    "testing": CodeIntent.TEST,
                    "tests": CodeIntent.TEST,
                    "documentation": CodeIntent.DOCUMENTATION,
                    "docs": CodeIntent.DOCUMENTATION,
                    "security": CodeIntent.SECURITY_PATCH,
                    "security_patch": CodeIntent.SECURITY_PATCH,
                    "security_fix": CodeIntent.SECURITY_PATCH,
                    "performance": CodeIntent.PERFORMANCE,
                    "optimization": CodeIntent.PERFORMANCE,
                    "dependency": CodeIntent.DEPENDENCY_UPDATE,
                    "dependency_update": CodeIntent.DEPENDENCY_UPDATE,
                    "dependencies": CodeIntent.DEPENDENCY_UPDATE,
                    "config": CodeIntent.CONFIG,
                    "configuration": CodeIntent.CONFIG,
                    "infrastructure": CodeIntent.CONFIG,
                }
                
                primary = intent_analysis.primary_intent.lower().replace(" ", "_")
                
                # Check for exact or partial match
                for key, intent in intent_mapping.items():
                    if key in primary or primary in key:
                        return intent
                
                # High confidence AI response but unknown mapping - trust it
                if intent_analysis.confidence > 0.7:
                    # Return FEATURE as default for high-confidence unknown
                    return CodeIntent.FEATURE
                    
            except Exception:
                # AI failed - fall back to heuristics
                pass
        
        # Fall back to pattern-based detection
        return self._detect_intent(pr_info)
    
    async def _assess_risk_with_ai(self, pr_info: PullRequestInfo) -> RiskProfile:
        """
        AI-powered semantic risk assessment.
        
        This analyzes the actual code to detect if changes touch:
        - Authentication/authorization logic
        - Payment processing
        - PII/sensitive data handling
        - Database schemas
        - API endpoints
        - Security configurations
        - Infrastructure code
        
        Falls back to heuristic risk assessment if AI unavailable.
        
        Args:
            pr_info: Pull request information with code diffs
            
        Returns:
            RiskProfile with semantic understanding
        """
        # Start with heuristic risk assessment
        risk_profile = self._assess_risk(pr_info)
        
        # Enhance with AI semantic analysis
        if self._ai_reviewer is not None:
            try:
                from aurix.ai.reviewer import SemanticRiskAnalysis
                
                # Call AI to analyze semantic risk
                semantic_risk: SemanticRiskAnalysis = await self._ai_reviewer.analyze_semantic_risk(
                    title=pr_info.title,
                    description=pr_info.description,
                    files=pr_info.files,
                    labels=pr_info.labels,
                )
                
                # Cache for summary generation
                self._semantic_risk = semantic_risk
                
                # Calculate additional risk from semantic analysis
                semantic_risk_score = 0.0
                
                # High-risk areas (each adds to risk)
                if semantic_risk.touches_authentication:
                    semantic_risk_score += 0.25
                    if "authentication" not in [f.factor_name for f in risk_profile.factors]:
                        risk_profile.factors.append(
                            RiskFactor(
                                factor_name="authentication",
                                factor_type="security",
                                impact_score=0.8,
                                description="AI detected changes to authentication logic",
                            )
                        )
                
                if semantic_risk.touches_authorization:
                    semantic_risk_score += 0.25
                    if "authorization" not in [f.factor_name for f in risk_profile.factors]:
                        risk_profile.factors.append(
                            RiskFactor(
                                factor_name="authorization",
                                factor_type="security",
                                impact_score=0.8,
                                description="AI detected changes to authorization/permissions",
                            )
                        )
                
                if semantic_risk.touches_payment:
                    semantic_risk_score += 0.35
                    if "payment" not in [f.factor_name for f in risk_profile.factors]:
                        risk_profile.factors.append(
                            RiskFactor(
                                factor_name="payment",
                                factor_type="financial",
                                impact_score=0.95,
                                description="AI detected changes to payment processing",
                            )
                        )
                
                if semantic_risk.touches_pii:
                    semantic_risk_score += 0.30
                    if "pii" not in [f.factor_name for f in risk_profile.factors]:
                        risk_profile.factors.append(
                            RiskFactor(
                                factor_name="pii",
                                factor_type="compliance",
                                impact_score=0.85,
                                description="AI detected handling of personally identifiable information",
                            )
                        )
                
                if semantic_risk.touches_database:
                    semantic_risk_score += 0.20
                    if "database_schema" not in [f.factor_name for f in risk_profile.factors]:
                        risk_profile.factors.append(
                            RiskFactor(
                                factor_name="database_schema",
                                factor_type="data",
                                impact_score=0.7,
                                description="AI detected database schema or query changes",
                            )
                        )
                
                if semantic_risk.touches_security_config:
                    semantic_risk_score += 0.25
                    if "security_config" not in [f.factor_name for f in risk_profile.factors]:
                        risk_profile.factors.append(
                            RiskFactor(
                                factor_name="security_config",
                                factor_type="security",
                                impact_score=0.8,
                                description="AI detected changes to security configuration",
                            )
                        )
                
                if semantic_risk.touches_infrastructure:
                    semantic_risk_score += 0.20
                    if "infrastructure" not in [f.factor_name for f in risk_profile.factors]:
                        risk_profile.factors.append(
                            RiskFactor(
                                factor_name="infrastructure",
                                factor_type="infrastructure",
                                impact_score=0.7,
                                description="AI detected infrastructure/deployment changes",
                            )
                        )
                
                # Adjust blast radius
                blast_radius_map = {"low": 0.0, "medium": 0.1, "high": 0.2, "critical": 0.3}
                semantic_risk_score += blast_radius_map.get(semantic_risk.blast_radius, 0.0)
                
                # Reversibility adjustment
                reversibility_map = {"easy": -0.1, "moderate": 0.0, "difficult": 0.1, "impossible": 0.25}
                semantic_risk_score += reversibility_map.get(semantic_risk.reversibility, 0.0)
                
                # Merge with existing risk score (weighted average)
                combined_score = (risk_profile.overall_risk_score * 0.4) + (semantic_risk_score * 0.6)
                risk_profile.overall_risk_score = min(1.0, round(combined_score, 4))
                
                # Recalculate risk level
                risk_profile.risk_level = self.risk_assessor._determine_risk_level(
                    risk_profile.overall_risk_score
                )
                
            except Exception:
                # AI failed - use heuristic risk only
                pass
        
        return risk_profile
    
    def _assess_risk(self, pr_info: PullRequestInfo) -> RiskProfile:
        """Assess risk of the pull request."""
        # Build diff stats
        diff_stats = {
            "additions": pr_info.additions,
            "deletions": pr_info.deletions,
        }
        
        # Get risk profile
        profile = self.risk_assessor.assess_code_change(
            pr_id=pr_info.pr_id,
            changed_files=pr_info.files,
            diff_stats=diff_stats,
        )
        
        # Adjust based on intent
        if pr_info.detected_intent:
            adjustment = self.INTENT_RISK_ADJUSTMENT.get(pr_info.detected_intent, 0)
            new_score = max(0, min(1, profile.overall_risk_score + adjustment))
            profile.overall_risk_score = round(new_score, 4)
            
            # Recalculate risk level
            profile.risk_level = self.risk_assessor._determine_risk_level(new_score)
        
        return profile
    
    async def _execute_checks(
        self,
        pr_info: PullRequestInfo,
        context: Dict[str, Any],
    ) -> Dict[ReviewCheckType, ReviewCheck]:
        """Execute all review checks."""
        results = {}
        
        # Try AI review first (if available)
        ai_analysis = await self._run_ai_review(pr_info)
        if ai_analysis:
            self._ai_analysis = ai_analysis
        
        # Style check
        results[ReviewCheckType.STYLE] = await self._check_style(pr_info)
        
        # Security check (enhanced with AI if available)
        results[ReviewCheckType.SECURITY] = await self._check_security(pr_info, ai_analysis)
        
        # Complexity check
        results[ReviewCheckType.COMPLEXITY] = await self._check_complexity(pr_info)
        
        # Documentation check
        results[ReviewCheckType.DOCUMENTATION] = await self._check_documentation(pr_info)
        
        # Logic check (enhanced with AI if available)
        results[ReviewCheckType.LOGIC] = await self._check_logic(pr_info, ai_analysis)
        
        return results
    
    async def _run_ai_review(self, pr_info: PullRequestInfo) -> Optional[Any]:
        """
        Run AI-powered code review if available.
        
        Returns AI analysis or None if unavailable.
        """
        # Try to get AI reviewer
        if self._ai_reviewer is None:
            try:
                from aurix.ai.reviewer import AIReviewer
                self._ai_reviewer = AIReviewer()
            except ImportError:
                return None
        
        if not self._ai_reviewer.is_available():
            return None
        
        try:
            analysis = await self._ai_reviewer.review_code(
                title=pr_info.title,
                description=pr_info.description,
                files=pr_info.files,
                labels=pr_info.labels,
                base_branch=pr_info.base_branch,
            )
            return analysis
        except Exception:
            # Silently fall back to rule-based
            return None
    
    async def _check_style(self, pr_info: PullRequestInfo) -> ReviewCheck:
        """Check code style."""
        issues = []
        
        for file_info in pr_info.files:
            content = file_info.get("content", "")
            filename = file_info.get("filename", "")
            
            lines = content.split("\n") if content else []
            
            for i, line in enumerate(lines):
                # Line length
                if len(line) > 120:
                    issues.append({
                        "file": filename,
                        "line": i + 1,
                        "rule": "line-length",
                        "severity": "low",
                        "message": f"Line exceeds 120 characters ({len(line)})",
                    })
                
                # Trailing whitespace
                if line.endswith(" ") or line.endswith("\t"):
                    issues.append({
                        "file": filename,
                        "line": i + 1,
                        "rule": "trailing-whitespace",
                        "severity": "low",
                        "message": "Trailing whitespace",
                    })
        
        # Calculate score
        total_lines = sum(
            len(f.get("content", "").split("\n"))
            for f in pr_info.files
        )
        
        score = max(0, 1 - (len(issues) / max(total_lines, 1)))
        
        return ReviewCheck(
            check_type=ReviewCheckType.STYLE,
            passed=len(issues) == 0,
            score=round(score, 3),
            issues=issues,
            suggestions=["Run auto-formatter before committing"] if issues else [],
        )
    
    async def _check_security(
        self, 
        pr_info: PullRequestInfo, 
        ai_analysis: Optional[Any] = None,
    ) -> ReviewCheck:
        """Check for security issues (enhanced with AI if available)."""
        issues = []
        
        # If we have AI analysis, use its security findings
        if ai_analysis and hasattr(ai_analysis, 'issues'):
            for ai_issue in ai_analysis.issues:
                if ai_issue.category == "security":
                    issues.append({
                        "file": ai_issue.file,
                        "line": ai_issue.line,
                        "rule": f"ai-{ai_issue.category}",
                        "severity": ai_issue.severity.value,
                        "message": ai_issue.message,
                        "suggestion": ai_issue.suggestion,
                        "source": "ai",
                    })
        
        # Always run rule-based patterns too (catches obvious issues even if AI misses)
        patterns = [
            (r"password\s*=\s*['\"][^'\"]+['\"]", "hardcoded-password", "critical"),
            (r"api_key\s*=\s*['\"][^'\"]+['\"]", "hardcoded-api-key", "critical"),
            (r"secret\s*=\s*['\"][^'\"]+['\"]", "hardcoded-secret", "critical"),
            (r"eval\s*\(", "unsafe-eval", "high"),
            (r"exec\s*\(", "unsafe-exec", "high"),
            (r"__import__\s*\(", "dynamic-import", "medium"),
            (r"pickle\.loads?\s*\(", "unsafe-pickle", "high"),
            (r"yaml\.load\s*\((?!.*Loader)", "unsafe-yaml", "high"),
            (r"subprocess\.(call|run|Popen)\s*\(.*shell\s*=\s*True", "shell-injection", "critical"),
            (r"http://(?!localhost|127\.0\.0\.1)", "insecure-http", "medium"),
        ]
        
        for file_info in pr_info.files:
            content = file_info.get("content", "")
            filename = file_info.get("filename", "")
            
            for pattern, rule, severity in patterns:
                matches = list(re.finditer(pattern, content, re.IGNORECASE))
                for match in matches:
                    # Calculate line number
                    line_num = content[:match.start()].count("\n") + 1
                    issues.append({
                        "file": filename,
                        "line": line_num,
                        "rule": rule,
                        "severity": severity,
                        "message": f"Potential security issue: {rule}",
                        "match": match.group()[:50] + "..." if len(match.group()) > 50 else match.group(),
                        "source": "rule",
                    })
        
        # Deduplicate issues (prefer AI issues as they have better suggestions)
        seen = set()
        unique_issues = []
        for issue in issues:
            key = (issue.get("file"), issue.get("line"), issue.get("rule", "")[:20])
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)
        
        # Calculate score based on severity
        severity_weights = {"critical": 1.0, "high": 0.5, "medium": 0.2, "low": 0.1}
        total_weight = sum(
            severity_weights.get(i.get("severity", "low"), 0.1)
            for i in unique_issues
        )
        score = max(0, 1 - total_weight)
        
        return ReviewCheck(
            check_type=ReviewCheckType.SECURITY,
            passed=len([i for i in unique_issues if i.get("severity") in ["critical", "high"]]) == 0,
            score=round(score, 3),
            issues=unique_issues,
            suggestions=[
                "Review and remove any hardcoded credentials",
                "Use environment variables for sensitive data",
            ] if unique_issues else [],
            metadata={"ai_enhanced": ai_analysis is not None},
        )
    
    async def _check_complexity(self, pr_info: PullRequestInfo) -> ReviewCheck:
        """Check code complexity."""
        issues = []
        total_complexity = 0
        file_count = 0
        
        for file_info in pr_info.files:
            content = file_info.get("content", "")
            filename = file_info.get("filename", "")
            
            if not content:
                continue
            
            # Simple complexity heuristics
            lines = content.split("\n")
            
            # Count nesting depth
            max_depth = 0
            current_depth = 0
            
            for line in lines:
                stripped = line.strip()
                
                # Increase depth for control structures
                if any(k in stripped for k in ["if ", "for ", "while ", "try:", "with "]):
                    current_depth += 1
                    max_depth = max(max_depth, current_depth)
                
                # Decrease depth for closing (simplified)
                if stripped.startswith(("return", "break", "continue", "raise")):
                    current_depth = max(0, current_depth - 1)
            
            if max_depth > 5:
                issues.append({
                    "file": filename,
                    "type": "nesting-depth",
                    "severity": "medium" if max_depth <= 7 else "high",
                    "message": f"High nesting depth: {max_depth}",
                })
            
            # Check function length
            function_lengths = self._estimate_function_lengths(content)
            for func_name, length in function_lengths.items():
                if length > 50:
                    issues.append({
                        "file": filename,
                        "function": func_name,
                        "type": "function-length",
                        "severity": "medium" if length <= 100 else "high",
                        "message": f"Function too long: {length} lines",
                    })
            
            file_count += 1
            total_complexity += max_depth
        
        avg_complexity = total_complexity / max(file_count, 1)
        score = max(0, 1 - (avg_complexity / 10))  # Normalize to 0-1
        
        return ReviewCheck(
            check_type=ReviewCheckType.COMPLEXITY,
            passed=len([i for i in issues if i.get("severity") == "high"]) == 0,
            score=round(score, 3),
            issues=issues,
            suggestions=[
                "Consider breaking down complex functions",
                "Reduce nesting by using early returns",
            ] if issues else [],
        )
    
    def _estimate_function_lengths(self, content: str) -> Dict[str, int]:
        """Estimate function lengths in code."""
        result = {}
        
        # Python function pattern
        func_pattern = r"^\s*(async\s+)?def\s+(\w+)\s*\("
        
        lines = content.split("\n")
        current_func = None
        current_start = 0
        base_indent = 0
        
        for i, line in enumerate(lines):
            match = re.match(func_pattern, line)
            if match:
                # Save previous function
                if current_func:
                    result[current_func] = i - current_start
                
                current_func = match.group(2)
                current_start = i
                base_indent = len(line) - len(line.lstrip())
        
        # Don't forget last function
        if current_func:
            result[current_func] = len(lines) - current_start
        
        return result
    
    async def _check_documentation(self, pr_info: PullRequestInfo) -> ReviewCheck:
        """Check documentation quality."""
        issues = []
        
        for file_info in pr_info.files:
            content = file_info.get("content", "")
            filename = file_info.get("filename", "")
            
            if not content:
                continue
            
            # Check for docstrings in Python files
            if filename.endswith(".py"):
                # Find functions without docstrings
                func_pattern = r"^\s*(async\s+)?def\s+(\w+)\s*\([^)]*\)\s*:"
                
                for match in re.finditer(func_pattern, content, re.MULTILINE):
                    func_name = match.group(2)
                    
                    # Skip private functions
                    if func_name.startswith("_"):
                        continue
                    
                    # Check for docstring after function definition
                    after_func = content[match.end():match.end() + 200]
                    if not re.search(r'^\s*["\']["\']["\']', after_func):
                        issues.append({
                            "file": filename,
                            "function": func_name,
                            "type": "missing-docstring",
                            "severity": "low",
                            "message": f"Function '{func_name}' lacks docstring",
                        })
        
        # Calculate score
        total_functions = len(issues) + 10  # Assume some have docs
        missing = len(issues)
        score = max(0, 1 - (missing / max(total_functions, 1)))
        
        return ReviewCheck(
            check_type=ReviewCheckType.DOCUMENTATION,
            passed=len(issues) < 5,  # Allow some missing docs
            score=round(score, 3),
            issues=issues,
            suggestions=[
                "Add docstrings to public functions",
            ] if issues else [],
        )
    
    async def _check_logic(
        self, 
        pr_info: PullRequestInfo,
        ai_analysis: Optional[Any] = None,
    ) -> ReviewCheck:
        """Check for logic issues (enhanced with AI if available)."""
        issues = []
        
        # If we have AI analysis, use its logic findings
        if ai_analysis and hasattr(ai_analysis, 'issues'):
            for ai_issue in ai_analysis.issues:
                if ai_issue.category == "logic":
                    issues.append({
                        "file": ai_issue.file,
                        "line": ai_issue.line,
                        "type": f"ai-logic",
                        "severity": ai_issue.severity.value,
                        "message": ai_issue.message,
                        "suggestion": ai_issue.suggestion,
                        "source": "ai",
                    })
        
        # Run rule-based checks too
        for file_info in pr_info.files:
            content = file_info.get("content", "")
            filename = file_info.get("filename", "")
            
            if not content:
                continue
            
            lines = content.split("\n")
            
            for i, line in enumerate(lines):
                # Check for common logic issues
                
                # Empty except blocks
                if re.search(r"except\s*:", line):
                    next_line = lines[i + 1] if i + 1 < len(lines) else ""
                    if "pass" in next_line or not next_line.strip():
                        issues.append({
                            "file": filename,
                            "line": i + 1,
                            "type": "bare-except",
                            "severity": "medium",
                            "message": "Bare except clause - catches all exceptions",
                            "source": "rule",
                        })
                
                # Debugging statements
                if re.search(r"print\s*\(|console\.log\s*\(|debugger;", line):
                    issues.append({
                        "file": filename,
                        "line": i + 1,
                        "type": "debug-statement",
                        "severity": "low",
                        "message": "Debug statement found",
                        "source": "rule",
                    })
        
        score = max(0, 1 - (len(issues) * 0.1))
        
        # If AI provided analysis, boost confidence
        if ai_analysis:
            ai_confidence = getattr(ai_analysis, 'confidence', 0.5)
            score = (score + ai_confidence) / 2  # Blend scores
        
        return ReviewCheck(
            check_type=ReviewCheckType.LOGIC,
            passed=len([i for i in issues if i.get("severity") in ["critical", "high"]]) == 0,
            score=round(score, 3),
            issues=issues,
            suggestions=[
                "Remove debug statements before merging",
                "Handle exceptions explicitly",
            ] if issues else [],
            metadata={"ai_enhanced": ai_analysis is not None},
        )
    
    def _calculate_overall_score(
        self,
        check_results: Dict[ReviewCheckType, ReviewCheck],
    ) -> float:
        """Calculate weighted overall score."""
        total_weight = 0
        weighted_score = 0
        
        for check_type, check in check_results.items():
            weight = self.CHECK_WEIGHTS.get(check_type, 1.0)
            weighted_score += check.score * weight
            total_weight += weight
        
        return round(weighted_score / total_weight, 3) if total_weight > 0 else 0.5
    
    def _make_decision(
        self,
        overall_score: float,
        check_results: Dict[ReviewCheckType, ReviewCheck],
        risk_profile: RiskProfile,
    ) -> Tuple[ReviewDecision, float]:
        """Make review decision based on scores."""
        # Check for critical issues
        has_critical = any(
            any(i.get("severity") == "critical" for i in c.issues)
            for c in check_results.values()
        )
        
        has_high = any(
            any(i.get("severity") == "high" for i in c.issues)
            for c in check_results.values()
        )
        
        security_failed = not check_results.get(ReviewCheckType.SECURITY, ReviewCheck(
            check_type=ReviewCheckType.SECURITY, passed=True, score=1.0
        )).passed
        
        # Decision logic
        if has_critical or security_failed:
            decision = ReviewDecision.BLOCK
            confidence = 0.95
        elif has_high:
            decision = ReviewDecision.REQUEST_CHANGES
            confidence = 0.85
        elif overall_score >= 0.8:
            decision = ReviewDecision.APPROVE
            confidence = min(0.95, overall_score)
        elif overall_score >= 0.6:
            decision = ReviewDecision.REQUEST_CHANGES
            confidence = overall_score
        else:
            decision = ReviewDecision.NEEDS_DISCUSSION
            confidence = overall_score
        
        # Adjust confidence based on risk
        if risk_profile.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            confidence *= 0.8  # Less confident for high-risk changes
        
        return decision, round(confidence, 3)
    
    def _check_escalation(
        self,
        decision: ReviewDecision,
        confidence: float,
        risk_profile: RiskProfile,
        automation_mode: AutomationMode,
        check_results: Dict[ReviewCheckType, ReviewCheck],
    ) -> Tuple[bool, Optional[str]]:
        """Check if human escalation is needed."""
        # Always escalate in shadow mode
        if automation_mode == AutomationMode.SHADOW:
            return True, "Shadow mode - all decisions require human review"
        
        # Escalate for low confidence
        if confidence < 0.8:
            return True, f"Low confidence: {confidence:.0%}"
        
        # Escalate for high risk
        if risk_profile.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return True, f"High risk: {risk_profile.risk_level.value}"
        
        # Escalate for blocking decisions unless full auto
        if decision == ReviewDecision.BLOCK and automation_mode != AutomationMode.FULL_AUTO:
            return True, "Blocking decision requires human confirmation"
        
        # Escalate for approval in suggestion mode
        if decision == ReviewDecision.APPROVE and automation_mode == AutomationMode.SUGGESTION:
            return True, "Approval decisions require human confirmation in suggestion mode"
        
        return False, None
    
    def _generate_comments(
        self,
        check_results: Dict[ReviewCheckType, ReviewCheck],
    ) -> List[Dict[str, Any]]:
        """Generate review comments from check results."""
        comments = []
        
        for check_type, check in check_results.items():
            for issue in check.issues:
                if issue.get("severity") in ["critical", "high", "medium"]:
                    comments.append({
                        "file": issue.get("file"),
                        "line": issue.get("line"),
                        "body": f"**{check_type.value.upper()}**: {issue.get('message')}",
                        "severity": issue.get("severity"),
                    })
        
        return comments
    
    def _generate_summary(
        self,
        pr_info: PullRequestInfo,
        check_results: Dict[ReviewCheckType, ReviewCheck],
        decision: ReviewDecision,
        confidence: float,
        ai_analysis: Optional[Any] = None,
        intent_analysis: Optional[Any] = None,
        semantic_risk: Optional[Any] = None,
    ) -> str:
        """Generate review summary with optional AI insights."""
        # Check if AI-enhanced
        ai_enhanced = ai_analysis is not None and hasattr(ai_analysis, 'summary')
        has_intent_ai = intent_analysis is not None
        has_semantic_ai = semantic_risk is not None
        
        lines = [
            "## Automated Code Review Summary",
            "",
        ]
        
        # Add AI badge if enhanced
        if ai_enhanced or has_intent_ai or has_semantic_ai:
            lines.append("🤖 *AI-Enhanced Review (GPT-4o-mini)*")
            lines.append("")
        
        lines.extend([
            f"**PR**: {pr_info.title}",
            f"**Intent**: {pr_info.detected_intent.value if pr_info.detected_intent else 'Unknown'}",
            f"**Decision**: {decision.value.replace('_', ' ').title()}",
            f"**Confidence**: {confidence:.0%}",
            "",
        ])
        
        # Add AI Intent Analysis section
        if has_intent_ai:
            lines.extend([
                "### 🎯 AI Intent Analysis",
                "",
            ])
            if hasattr(intent_analysis, 'summary') and intent_analysis.summary:
                lines.append(f"**Summary**: {intent_analysis.summary}")
            if hasattr(intent_analysis, 'primary_intent'):
                lines.append(f"**Primary Intent**: {intent_analysis.primary_intent}")
            if hasattr(intent_analysis, 'confidence'):
                lines.append(f"**Intent Confidence**: {intent_analysis.confidence:.0%}")
            
            # Flag potential issues
            if hasattr(intent_analysis, 'hidden_changes') and intent_analysis.hidden_changes:
                lines.append("")
                lines.append("⚠️ **Hidden Changes Detected:**")
                for change in intent_analysis.hidden_changes[:5]:
                    lines.append(f"- {change}")
            
            if hasattr(intent_analysis, 'scope_creep') and intent_analysis.scope_creep:
                lines.append("")
                lines.append("⚠️ **Scope Creep Warning:** PR may be doing more than stated")
            
            if hasattr(intent_analysis, 'title_matches_changes') and not intent_analysis.title_matches_changes:
                lines.append("")
                lines.append("⚠️ **Title Mismatch:** PR title may not reflect actual changes")
            
            lines.append("")
        
        # Add AI Semantic Risk section
        if has_semantic_ai:
            lines.extend([
                "### 🔒 AI Semantic Risk Analysis",
                "",
            ])
            
            risk_areas = []
            if hasattr(semantic_risk, 'touches_authentication') and semantic_risk.touches_authentication:
                risk_areas.append("🔐 Authentication")
            if hasattr(semantic_risk, 'touches_authorization') and semantic_risk.touches_authorization:
                risk_areas.append("🛡️ Authorization")
            if hasattr(semantic_risk, 'touches_payment') and semantic_risk.touches_payment:
                risk_areas.append("💳 Payment Processing")
            if hasattr(semantic_risk, 'touches_pii') and semantic_risk.touches_pii:
                risk_areas.append("👤 PII/Personal Data")
            if hasattr(semantic_risk, 'touches_database') and semantic_risk.touches_database:
                risk_areas.append("🗄️ Database/Schema")
            if hasattr(semantic_risk, 'touches_api_endpoints') and semantic_risk.touches_api_endpoints:
                risk_areas.append("🌐 API Endpoints")
            if hasattr(semantic_risk, 'touches_security_config') and semantic_risk.touches_security_config:
                risk_areas.append("⚙️ Security Config")
            if hasattr(semantic_risk, 'touches_infrastructure') and semantic_risk.touches_infrastructure:
                risk_areas.append("🏗️ Infrastructure")
            
            if risk_areas:
                lines.append("**Areas Touched:**")
                for area in risk_areas:
                    lines.append(f"- {area}")
                lines.append("")
            else:
                lines.append("✅ No high-risk areas detected")
                lines.append("")
            
            if hasattr(semantic_risk, 'blast_radius'):
                lines.append(f"**Blast Radius**: {semantic_risk.blast_radius}")
            if hasattr(semantic_risk, 'reversibility'):
                lines.append(f"**Reversibility**: {semantic_risk.reversibility}")
            if hasattr(semantic_risk, 'recommended_reviewers') and semantic_risk.recommended_reviewers:
                lines.append(f"**Recommended Reviewers**: {', '.join(semantic_risk.recommended_reviewers[:3])}")
            
            lines.append("")
        
        lines.extend([
            "### Check Results",
            "",
        ])
        
        for check_type, check in check_results.items():
            emoji = "✅" if check.passed else "❌"
            lines.append(f"- {emoji} **{check_type.value.title()}**: {check.score:.0%}")
        
        # Add AI summary if available
        if ai_enhanced and ai_analysis.summary:
            lines.extend([
                "",
                "### AI Analysis Summary",
                "",
                ai_analysis.summary,
            ])
            
            # Add strengths if any
            if ai_analysis.strengths:
                lines.extend([
                    "",
                    "**Strengths:**",
                ])
                for strength in ai_analysis.strengths[:5]:  # Top 5
                    lines.append(f"- ✨ {strength}")
            
            # Add risk factors if any
            if ai_analysis.risk_factors:
                lines.extend([
                    "",
                    "**Risk Factors:**",
                ])
                for risk in ai_analysis.risk_factors[:5]:  # Top 5
                    lines.append(f"- ⚠️ {risk}")
        
        # Add issue counts
        total_issues = sum(len(c.issues) for c in check_results.values())
        critical_issues = sum(
            len([i for i in c.issues if i.get("severity") == "critical"])
            for c in check_results.values()
        )
        
        lines.extend([
            "",
            "### Statistics",
            f"- Total issues: {total_issues}",
            f"- Critical issues: {critical_issues}",
            f"- Files changed: {pr_info.changed_files_count}",
            f"- Lines added: {pr_info.additions}",
            f"- Lines removed: {pr_info.deletions}",
        ])
        
        # Add AI token usage if available
        if ai_enhanced:
            lines.extend([
                "",
                f"*AI tokens used: ~{ai_analysis.tokens_used or 'N/A'} | Est. cost: ${(ai_analysis.tokens_used or 0) * 0.00000015:.6f}*",
            ])
        
        return "\n".join(lines)
    
    def determine_action(
        self,
        review_result: ReviewResult,
        team_config: Optional[TeamConfig] = None,
        check_results: Optional[Dict[ReviewCheckType, ReviewCheck]] = None,
    ) -> ReviewActionResult:
        """
        Determine the actionable outcome for a review.
        
        This is the key method that decides:
        - AUTO_MERGE: PR can be merged automatically
        - HUMAN_REVIEW: Specific human review needed (with annotations)
        - BLOCK: PR is blocked due to critical issues
        - REQUEST_CHANGES: Changes needed before proceeding
        
        Args:
            review_result: The complete review result
            team_config: Team-specific configuration (optional)
            check_results: Detailed check results for annotations
            
        Returns:
            ReviewActionResult with action and supporting context
        """
        import time
        start_time = time.time()
        
        # Load team config if not provided
        if team_config is None:
            team_config = load_team_config(repo=review_result.pr_info.repo)
        
        pr_info = review_result.pr_info
        risk_profile = review_result.risk_profile
        decision = review_result.decision
        confidence = review_result.confidence
        
        # Get changed file paths
        changed_paths = [f.get("filename", f.get("path", "")) for f in pr_info.files]
        
        # Check auto-merge eligibility using team config
        config_loader = ConfigLoader()
        eligible, ineligible_reason = config_loader.get_auto_merge_eligible(
            config=team_config,
            score=review_result.overall_score,
            risk_level=risk_profile.risk_level.value,
            changed_paths=changed_paths,
            labels=pr_info.labels,
        )
        
        # Determine action based on decision and eligibility
        if decision == ReviewDecision.BLOCK:
            # Critical issues - block the PR
            blocking_issues = self._extract_blocking_issues(check_results or {})
            
            return ReviewActionResult(
                action=ReviewAction.BLOCK,
                reason="Critical issues detected that must be resolved",
                confidence_score=confidence,
                risk_score=risk_profile.overall_score,
                risk_level=risk_profile.risk_level.value,
                quality_score=review_result.overall_score,
                blocking_issues=blocking_issues,
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
        
        elif decision == ReviewDecision.REQUEST_CHANGES:
            # Changes needed from author
            changes = self._extract_requested_changes(check_results or {})
            
            return ReviewActionResult(
                action=ReviewAction.REQUEST_CHANGES,
                reason="Code changes required before this can be merged",
                confidence_score=confidence,
                risk_score=risk_profile.overall_score,
                risk_level=risk_profile.risk_level.value,
                quality_score=review_result.overall_score,
                changes_requested=changes,
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
        
        elif decision == ReviewDecision.APPROVE and eligible:
            # All criteria met - auto-merge!
            return ReviewActionResult(
                action=ReviewAction.AUTO_MERGE,
                reason="All quality and risk thresholds met for automatic merge",
                confidence_score=confidence,
                risk_score=risk_profile.overall_score,
                risk_level=risk_profile.risk_level.value,
                quality_score=review_result.overall_score,
                processing_time_ms=int((time.time() - start_time) * 1000),
                metadata={
                    "auto_merge_eligible": True,
                    "team_config_applied": team_config.team_name or "default",
                },
            )
        
        else:
            # Human review needed - create detailed request
            human_review = self._create_human_review_request(
                pr_info=pr_info,
                risk_profile=risk_profile,
                check_results=check_results or {},
                ineligible_reason=ineligible_reason,
                review_result=review_result,
            )
            
            return ReviewActionResult(
                action=ReviewAction.HUMAN_REVIEW,
                reason=ineligible_reason or "Human review required based on risk assessment",
                confidence_score=confidence,
                risk_score=risk_profile.overall_score,
                risk_level=risk_profile.risk_level.value,
                quality_score=review_result.overall_score,
                human_review=human_review,
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def _extract_blocking_issues(
        self,
        check_results: Dict[ReviewCheckType, ReviewCheck],
    ) -> List[str]:
        """Extract list of blocking issues from check results."""
        blocking = []
        
        for check_type, check in check_results.items():
            for issue in check.issues:
                if issue.get("severity") == "critical":
                    location = ""
                    if issue.get("file"):
                        location = f" in {issue.get('file')}"
                        if issue.get("line"):
                            location += f":{issue.get('line')}"
                    
                    blocking.append(
                        f"[{check_type.value.upper()}]{location}: {issue.get('message', 'Critical issue')}"
                    )
        
        return blocking
    
    def _extract_requested_changes(
        self,
        check_results: Dict[ReviewCheckType, ReviewCheck],
    ) -> List[str]:
        """Extract list of requested changes from check results."""
        changes = []
        
        for check_type, check in check_results.items():
            for issue in check.issues:
                if issue.get("severity") in ("high", "medium"):
                    changes.append(
                        f"[{check_type.value}]: {issue.get('message', 'Issue found')}"
                    )
            
            # Include suggestions
            for suggestion in check.suggestions:
                changes.append(f"[{check_type.value}]: {suggestion}")
        
        return changes[:20]  # Limit to top 20
    
    def _create_human_review_request(
        self,
        pr_info: PullRequestInfo,
        risk_profile: RiskProfile,
        check_results: Dict[ReviewCheckType, ReviewCheck],
        ineligible_reason: Optional[str],
        review_result: ReviewResult,
    ) -> HumanReviewRequest:
        """
        Create a detailed human review request with specific file/line annotations.
        
        This tells the human reviewer exactly what to look at and why.
        """
        # Determine priority based on risk and confidence
        if risk_profile.risk_level == RiskLevel.CRITICAL:
            priority = ReviewPriority.CRITICAL
        elif risk_profile.risk_level == RiskLevel.HIGH:
            priority = ReviewPriority.HIGH
        elif review_result.confidence < 0.6:
            priority = ReviewPriority.HIGH
        elif review_result.confidence < 0.8:
            priority = ReviewPriority.MEDIUM
        else:
            priority = ReviewPriority.LOW
        
        # Create file annotations from issues
        annotations = []
        for check_type, check in check_results.items():
            for issue in check.issues:
                if issue.get("file"):
                    line_ranges = []
                    if issue.get("line"):
                        start_line = issue.get("line")
                        end_line = issue.get("end_line", start_line)
                        line_ranges.append(LineRange(start=start_line, end=end_line))
                    
                    annotations.append(FileAnnotation(
                        file_path=issue.get("file"),
                        line_ranges=line_ranges,
                        reason=issue.get("message", "Review needed"),
                        category=check_type.value,
                        severity=issue.get("severity", "medium"),
                        ai_confidence=check.score,
                        suggested_fix=issue.get("suggestion"),
                        context=issue.get("context"),
                    ))
        
        # Determine what AI already verified (passed checks)
        ai_verified = []
        for check_type, check in check_results.items():
            if check.passed and check.score >= 0.8:
                ai_verified.append(f"{check_type.value.title()} check passed ({check.score:.0%})")
        
        # Determine focus areas based on failed/low-score checks
        focus_areas = []
        for check_type, check in check_results.items():
            if not check.passed or check.score < 0.7:
                focus_areas.append(
                    f"{check_type.value.title()}: Score {check.score:.0%} - needs attention"
                )
        
        # Add focus based on risk factors
        for factor in risk_profile.risk_factors[:3]:  # Top 3 risk factors
            focus_areas.append(f"Risk: {factor.description} (weight: {factor.weight:.0%})")
        
        # Estimate review time based on complexity
        base_time = 10  # minutes
        if pr_info.changed_files_count > 10:
            base_time += 10
        if pr_info.additions + pr_info.deletions > 500:
            base_time += 10
        if len(annotations) > 5:
            base_time += 5
        if risk_profile.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            base_time += 10
        
        return HumanReviewRequest(
            pr_number=int(pr_info.pr_id.split("/")[-1]) if "/" in pr_info.pr_id else 0,
            repository=pr_info.repo,
            title=pr_info.title,
            reason=ineligible_reason or "Human review required based on risk assessment",
            priority=priority,
            annotations=annotations,
            ai_verified=ai_verified,
            focus_areas=focus_areas,
            ai_summary=f"Review of {pr_info.detected_intent.value if pr_info.detected_intent else 'change'} "
                      f"with {pr_info.changed_files_count} files changed",
            risk_level=risk_profile.risk_level.value,
            risk_score=risk_profile.overall_score,
            confidence_score=review_result.confidence,
            expected_review_time_minutes=base_time,
        )

    def _get_automation_mode(
        self,
        repo: str,
        risk_profile: RiskProfile,
    ) -> AutomationMode:
        """Get automation mode for a repository."""
        # Check if repo has established mode
        if repo in self._repo_modes:
            base_mode = self._repo_modes[repo]
        else:
            # Default to shadow for new repos
            base_mode = AutomationMode.SHADOW
        
        # Downgrade mode for high-risk PRs
        if risk_profile.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            if base_mode == AutomationMode.FULL_AUTO:
                return AutomationMode.AUTO_WITH_REVIEW
            elif base_mode == AutomationMode.AUTO_WITH_REVIEW:
                return AutomationMode.SUGGESTION
        
        return base_mode
    
    def _track_outcome(self, result: ReviewResult) -> None:
        """Track outcome for confidence scoring."""
        # This would be called when human provides feedback
        # For now, we assume shadow mode results are tracked later
        pass
    
    def record_human_feedback(
        self,
        pr_id: str,
        human_decision: ReviewDecision,
        feedback: Optional[str] = None,
    ) -> None:
        """Record human feedback on a review."""
        # Find the review
        review = next(
            (r for r in self._review_history if r.pr_info.pr_id == pr_id),
            None
        )
        
        if not review:
            return
        
        # Determine outcome
        if human_decision == review.decision:
            outcome_type = OutcomeType.CORRECT
        else:
            outcome_type = OutcomeType.OVERRIDDEN
        
        outcome = Outcome(
            task_id=f"review_{pr_id}",
            decision_id=pr_id,
            outcome_type=outcome_type,
            timestamp=datetime.utcnow(),
            ai_decision=review.decision.value,
            human_decision=human_decision.value,
            risk_level=review.risk_profile.risk_level.value,
            automation_mode=review.automation_mode.value,
            feedback_provided=feedback is not None,
            feedback_text=feedback,
        )
        
        self.confidence_tracker.record(outcome)
    
    def get_graduation_status(self, repo: str) -> Dict[str, Any]:
        """Get graduation status for a repository."""
        task_type = f"review_{repo}"
        return self.confidence_tracker.get_graduation_status(task_type)
    
    def graduate_repo(
        self,
        repo: str,
        target_mode: AutomationMode,
    ) -> bool:
        """Graduate a repository to a new automation mode."""
        status = self.get_graduation_status(repo)
        
        if not status.get("eligible"):
            return False
        
        self._repo_modes[repo] = target_mode
        return True
