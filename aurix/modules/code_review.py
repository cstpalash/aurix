"""
Code Review Automation Module for Aurix Platform

Provides comprehensive automated code review with:
- Intent analysis
- Risk profiling
- Multi-stage review pipeline
- Confidence-based automation graduation
- AI-enhanced analysis via GPT-4o-mini
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aurix.ai.reviewer import AIReviewer

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
from aurix.core.task_decomposer import TaskDecomposer, TaskGraph, Task
from aurix.core.micro_agent import AgentOrchestrator, AgentResult


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
        orchestrator: Optional[AgentOrchestrator] = None,
        ai_reviewer: Optional["AIReviewer"] = None,
    ):
        """Initialize code review module."""
        self.confidence_engine = confidence_engine or ConfidenceEngine()
        self.risk_assessor = risk_assessor or CodeReviewRiskAssessor()
        self.orchestrator = orchestrator or AgentOrchestrator()
        self.task_decomposer = TaskDecomposer()
        
        # AI reviewer (optional - enhanced reviews when available)
        self._ai_reviewer = ai_reviewer
        self._ai_analysis: Optional[Any] = None  # Store last AI analysis
        
        # Tracking
        self.confidence_tracker = ConfidenceTracker(self.confidence_engine)
        self._review_history: List[ReviewResult] = []
        
        # Current automation mode per repo
        self._repo_modes: Dict[str, AutomationMode] = {}
    
    async def review_pull_request(
        self,
        pr_info: PullRequestInfo,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReviewResult:
        """
        Perform automated code review on a pull request.
        
        Args:
            pr_info: Pull request information
            context: Additional context
            
        Returns:
            ReviewResult with decision and details
        """
        context = context or {}
        start_time = datetime.utcnow()
        
        # Step 1: Detect code intent
        pr_info.detected_intent = self._detect_intent(pr_info)
        
        # Step 2: Assess risk
        risk_profile = self._assess_risk(pr_info)
        
        # Step 3: Decompose into review tasks
        review_graph = self.task_decomposer.decompose(
            f"review_{pr_info.pr_id}",
            pattern="code_review",
            context={"pr_info": pr_info.dict()},
        )
        
        # Step 4: Execute review checks
        automation_mode = self._get_automation_mode(pr_info.repo, risk_profile)
        
        check_results = await self._execute_checks(
            pr_info,
            review_graph,
            context,
        )
        
        # Step 5: Calculate overall score
        overall_score = self._calculate_overall_score(check_results)
        
        # Step 6: Make decision
        decision, confidence = self._make_decision(
            overall_score,
            check_results,
            risk_profile,
        )
        
        # Step 7: Determine if human review needed
        human_required, escalation_reason = self._check_escalation(
            decision,
            confidence,
            risk_profile,
            automation_mode,
            check_results,
        )
        
        # Step 8: Generate comments
        comments = self._generate_comments(check_results)
        summary = self._generate_summary(
            pr_info,
            check_results,
            decision,
            confidence,
            ai_analysis=self._ai_analysis,  # Include AI insights in summary
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
        review_graph: TaskGraph,
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
    ) -> str:
        """Generate review summary with optional AI insights."""
        # Check if AI-enhanced
        ai_enhanced = ai_analysis is not None and hasattr(ai_analysis, 'summary')
        
        lines = [
            "## Automated Code Review Summary",
            "",
        ]
        
        # Add AI badge if enhanced
        if ai_enhanced:
            lines.append("🤖 *AI-Enhanced Review (GPT-4o-mini)*")
            lines.append("")
        
        lines.extend([
            f"**PR**: {pr_info.title}",
            f"**Intent**: {pr_info.detected_intent.value if pr_info.detected_intent else 'Unknown'}",
            f"**Decision**: {decision.value.replace('_', ' ').title()}",
            f"**Confidence**: {confidence:.0%}",
            "",
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
