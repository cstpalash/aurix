"""
Review Actions and Human Review Request Models for Aurix Platform

Defines actionable review outcomes and structured human review requests
that specify exactly what needs attention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ReviewAction(Enum):
    """
    Actionable review outcomes.
    
    Unlike ReviewDecision which describes the review assessment,
    ReviewAction specifies what should actually happen next.
    """
    
    # Automatically merge the PR - all criteria met, no human needed
    AUTO_MERGE = "auto_merge"
    
    # Request specific human review - provide guidance on what to check
    HUMAN_REVIEW = "human_review"
    
    # Block the PR - critical issues found, must be fixed
    BLOCK = "block"
    
    # Request changes from author - AI found fixable issues
    REQUEST_CHANGES = "request_changes"
    
    # Escalate to senior reviewer - complex or sensitive changes
    ESCALATE = "escalate"


class ReviewPriority(Enum):
    """Priority level for human review requests."""
    
    LOW = "low"          # Can wait, routine review
    MEDIUM = "medium"    # Should be reviewed soon
    HIGH = "high"        # Needs attention today
    CRITICAL = "critical"  # Needs immediate attention


@dataclass
class LineRange:
    """A range of lines in a file."""
    
    start: int
    end: int
    
    def __str__(self) -> str:
        if self.start == self.end:
            return f"L{self.start}"
        return f"L{self.start}-{self.end}"


@dataclass
class FileAnnotation:
    """
    Specific file/line annotation for human review.
    
    Tells the human reviewer exactly where to focus attention
    and what to look for.
    """
    
    file_path: str
    line_ranges: List[LineRange] = field(default_factory=list)
    reason: str = ""
    category: str = ""  # security, logic, performance, etc.
    severity: str = "medium"  # low, medium, high, critical
    ai_confidence: float = 0.0  # How confident is AI about this annotation
    suggested_fix: Optional[str] = None
    context: Optional[str] = None  # Code context around the issue
    
    @property
    def location_str(self) -> str:
        """Human-readable location string."""
        if not self.line_ranges:
            return self.file_path
        ranges = ", ".join(str(r) for r in self.line_ranges)
        return f"{self.file_path}:{ranges}"
    
    def to_github_comment(self) -> str:
        """Format as GitHub inline comment."""
        comment = f"**{self.category.upper()}** ({self.severity})\n\n{self.reason}"
        
        if self.suggested_fix:
            comment += f"\n\n**Suggested fix:**\n```suggestion\n{self.suggested_fix}\n```"
        
        return comment


@dataclass
class HumanReviewRequest:
    """
    Structured request for human review.
    
    When Aurix determines that human review is needed, this
    dataclass provides specific guidance on what to review,
    why, and how urgent it is.
    """
    
    # Core metadata
    pr_number: int
    repository: str
    title: str = ""
    
    # Review guidance
    reason: str = ""
    priority: ReviewPriority = ReviewPriority.MEDIUM
    
    # Specific files/lines to review
    annotations: List[FileAnnotation] = field(default_factory=list)
    
    # Summary of what AI already verified
    ai_verified: List[str] = field(default_factory=list)
    
    # What the human should focus on
    focus_areas: List[str] = field(default_factory=list)
    
    # Context from AI analysis
    ai_summary: str = ""
    risk_level: str = "medium"
    risk_score: float = 0.5
    confidence_score: float = 0.5
    
    # Escalation path
    suggested_reviewers: List[str] = field(default_factory=list)
    escalation_reason: Optional[str] = None
    
    # Time expectations
    expected_review_time_minutes: int = 15
    deadline: Optional[str] = None
    
    @property
    def critical_annotations(self) -> List[FileAnnotation]:
        """Get only critical severity annotations."""
        return [a for a in self.annotations if a.severity == "critical"]
    
    @property
    def high_priority_annotations(self) -> List[FileAnnotation]:
        """Get high and critical severity annotations."""
        return [a for a in self.annotations if a.severity in ("high", "critical")]
    
    def to_github_body(self) -> str:
        """Format as GitHub PR comment body."""
        lines = [
            f"## 🔍 Human Review Requested",
            "",
            f"**Priority:** {self.priority.value.upper()}",
            f"**Risk Level:** {self.risk_level}",
            f"**Estimated Review Time:** ~{self.expected_review_time_minutes} minutes",
            "",
        ]
        
        if self.reason:
            lines.extend([
                "### Why Human Review?",
                self.reason,
                "",
            ])
        
        if self.ai_verified:
            lines.extend([
                "### ✅ AI Already Verified",
                *[f"- {item}" for item in self.ai_verified],
                "",
            ])
        
        if self.focus_areas:
            lines.extend([
                "### 🎯 Please Focus On",
                *[f"- {area}" for area in self.focus_areas],
                "",
            ])
        
        if self.annotations:
            lines.extend([
                "### 📍 Specific Locations to Review",
                "",
            ])
            
            for ann in sorted(self.annotations, key=lambda a: (
                {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(a.severity, 2),
                a.file_path
            )):
                severity_emoji = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢",
                }.get(ann.severity, "⚪")
                
                lines.append(f"- {severity_emoji} **{ann.location_str}** - {ann.reason}")
                if ann.suggested_fix:
                    lines.append(f"  - 💡 Suggested: {ann.suggested_fix[:100]}...")
            
            lines.append("")
        
        if self.ai_summary:
            lines.extend([
                "### 🤖 AI Analysis Summary",
                self.ai_summary,
                "",
            ])
        
        if self.suggested_reviewers:
            lines.extend([
                "### 👥 Suggested Reviewers",
                *[f"- @{reviewer}" for reviewer in self.suggested_reviewers],
                "",
            ])
        
        lines.extend([
            "---",
            f"*Confidence: {self.confidence_score:.0%} | Risk Score: {self.risk_score:.0%}*",
        ])
        
        return "\n".join(lines)
    
    def to_slack_blocks(self) -> List[Dict[str, Any]]:
        """Format as Slack Block Kit message."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔍 Human Review Needed: {self.repository}#{self.pr_number}",
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Priority:* {self.priority.value.upper()}"},
                    {"type": "mrkdwn", "text": f"*Risk:* {self.risk_level}"},
                    {"type": "mrkdwn", "text": f"*Est. Time:* ~{self.expected_review_time_minutes}m"},
                    {"type": "mrkdwn", "text": f"*Confidence:* {self.confidence_score:.0%}"},
                ]
            },
        ]
        
        if self.reason:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Reason:* {self.reason}"}
            })
        
        if self.focus_areas:
            focus_text = "\n".join(f"• {area}" for area in self.focus_areas[:5])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Focus Areas:*\n{focus_text}"}
            })
        
        if self.annotations:
            ann_text = "\n".join(
                f"• `{a.location_str}` - {a.reason}"
                for a in self.annotations[:5]
            )
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Review Locations:*\n{ann_text}"}
            })
        
        return blocks


@dataclass
class ReviewActionResult:
    """
    Complete result of review action determination.
    
    Combines the action to take with supporting context
    and human review request if applicable.
    """
    
    action: ReviewAction
    reason: str
    
    # Scores and metrics
    confidence_score: float = 0.0
    risk_score: float = 0.0
    risk_level: str = "medium"
    quality_score: float = 0.0
    
    # Human review request (if action is HUMAN_REVIEW)
    human_review: Optional[HumanReviewRequest] = None
    
    # Changes requested (if action is REQUEST_CHANGES)
    changes_requested: List[str] = field(default_factory=list)
    
    # Blocking issues (if action is BLOCK)
    blocking_issues: List[str] = field(default_factory=list)
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    processing_time_ms: int = 0
    
    @property
    def is_autonomous(self) -> bool:
        """Check if this action can proceed without human intervention."""
        return self.action == ReviewAction.AUTO_MERGE
    
    @property
    def needs_human(self) -> bool:
        """Check if human intervention is needed."""
        return self.action in (
            ReviewAction.HUMAN_REVIEW,
            ReviewAction.ESCALATE,
        )
    
    @property
    def is_blocking(self) -> bool:
        """Check if this blocks the PR."""
        return self.action == ReviewAction.BLOCK
    
    def to_github_status(self) -> Dict[str, str]:
        """Convert to GitHub commit status payload."""
        status_map = {
            ReviewAction.AUTO_MERGE: ("success", "Auto-merge approved"),
            ReviewAction.HUMAN_REVIEW: ("pending", "Human review requested"),
            ReviewAction.REQUEST_CHANGES: ("failure", "Changes requested"),
            ReviewAction.BLOCK: ("failure", "PR blocked - critical issues"),
            ReviewAction.ESCALATE: ("pending", "Escalation required"),
        }
        
        state, description = status_map.get(
            self.action, ("pending", "Review in progress")
        )
        
        return {
            "state": state,
            "description": f"{description} (confidence: {self.confidence_score:.0%})",
            "context": "aurix/review",
        }
