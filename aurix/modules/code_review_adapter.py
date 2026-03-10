"""
Code Review module adapter for the generic Aurix interface.

This wraps the CodeReviewModule to conform to the BaseModule interface.
"""

from typing import Any

from pydantic import BaseModel, Field

from aurix.core.module import (
    BaseModule,
    ModuleContext,
    ModuleResult,
    ModuleDecision,
    ModuleRegistry,
)
from aurix.core.risk_assessor import RiskProfile, RiskLevel
from aurix.core.confidence_engine import AutomationMode
from aurix.modules.code_review import (
    CodeReviewModule as CodeReviewCore,
    PullRequestInfo,
    ReviewDecision,
    ReviewResult,
)


class CodeReviewInput(BaseModel):
    """Input for code review module."""
    
    pr_id: str
    repo: str
    title: str = ""
    description: str = ""
    author: str = ""
    files: list[dict] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    changed_files_count: int = 0
    labels: list[str] = Field(default_factory=list)
    base_branch: str = "main"
    head_branch: str = ""
    draft: bool = False


@ModuleRegistry.register
class CodeReviewModuleAdapter(BaseModule[CodeReviewInput, ModuleResult]):
    """
    Code review module for Aurix.
    
    Analyzes pull requests and provides automated review decisions
    with confidence-based automation graduation.
    """
    
    name = "code_review"
    description = "Automated code review with risk-based decisions"
    version = "1.0.0"
    
    input_model_class = CodeReviewInput
    
    def __init__(self):
        super().__init__()
        self._core: CodeReviewCore | None = None
    
    async def initialize(self) -> None:
        """Initialize the core code review module."""
        self._core = CodeReviewCore()
        await super().initialize()
    
    async def execute(
        self,
        input_data: CodeReviewInput,
        context: ModuleContext,
    ) -> ModuleResult:
        """Execute code review analysis."""
        if self._core is None:
            await self.initialize()
        
        # Convert to PullRequestInfo
        pr_info = PullRequestInfo(
            pr_id=input_data.pr_id,
            repo=input_data.repo,
            title=input_data.title,
            description=input_data.description,
            author=input_data.author,
            files=input_data.files,
            additions=input_data.additions,
            deletions=input_data.deletions,
            changed_files_count=input_data.changed_files_count,
            labels=input_data.labels,
            base_branch=input_data.base_branch,
            head_branch=input_data.head_branch,
        )
        
        # Run core review
        result = await self._core.review_pull_request(pr_info)
        
        # Map review decision to module decision
        decision_map = {
            ReviewDecision.APPROVE: ModuleDecision.APPROVE,
            ReviewDecision.REQUEST_CHANGES: ModuleDecision.REJECT,
            ReviewDecision.NEEDS_DISCUSSION: ModuleDecision.NEEDS_REVIEW,
            ReviewDecision.BLOCK: ModuleDecision.REJECT,
        }
        
        # Determine if human review required based on mode
        human_required = True
        if context.automation_mode == AutomationMode.FULL_AUTO:
            human_required = result.risk_profile.overall_level.value > RiskLevel.LOW.value
        elif context.automation_mode == AutomationMode.AUTO_WITH_REVIEW:
            human_required = result.risk_profile.overall_level.value > RiskLevel.MEDIUM.value
        
        return ModuleResult(
            module_name=self.name,
            task_id=self.get_task_id(input_data),
            decision=decision_map.get(result.decision, ModuleDecision.NEEDS_REVIEW),
            confidence=result.confidence,
            risk_profile=result.risk_profile,
            automation_mode=context.automation_mode,
            human_review_required=human_required or result.human_review_required,
            details={
                "checks": result.checks,
                "overall_score": result.overall_score,
                "comments": result.comments,
                "intent": result.pr_info.detected_intent.value if result.pr_info.detected_intent else None,
            },
            summary=result.summary,
            actions=self._build_actions(result),
            warnings=[],
            errors=[],
        )
    
    async def assess_risk(self, input_data: CodeReviewInput) -> RiskProfile:
        """Assess risk for this PR."""
        if self._core is None:
            await self.initialize()
        
        pr_info = PullRequestInfo(
            pr_id=input_data.pr_id,
            repo=input_data.repo,
            title=input_data.title,
            description=input_data.description,
            additions=input_data.additions,
            deletions=input_data.deletions,
            changed_files_count=input_data.changed_files_count,
            labels=input_data.labels,
        )
        
        return self._core.risk_assessor.assess({
            "pr_info": pr_info,
            "files": input_data.files,
        })
    
    def get_task_id(self, input_data: CodeReviewInput) -> str:
        """Generate task ID for tracking."""
        # Group by repo for confidence tracking
        # This means all PRs in a repo share confidence metrics
        return f"code_review:{input_data.repo}"
    
    def _build_actions(self, result: ReviewResult) -> list[dict]:
        """Build actionable items from review result."""
        actions = []
        
        if result.decision == ReviewDecision.APPROVE:
            actions.append({
                "type": "approve_pr",
                "message": "Approve pull request",
            })
        elif result.decision == ReviewDecision.REQUEST_CHANGES:
            actions.append({
                "type": "request_changes",
                "comments": result.comments,
            })
        
        return actions
