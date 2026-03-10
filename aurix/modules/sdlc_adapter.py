"""
SDLC module adapter for the generic Aurix interface.

This wraps the SDLCModule to conform to the BaseModule interface.
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
from aurix.core.risk_assessor import RiskProfile, RiskLevel, SDLCRiskAssessor
from aurix.core.confidence_engine import AutomationMode
from aurix.modules.sdlc import (
    SDLCModule as SDLCCore,
    PipelineExecution,
    StageResult,
    StageStatus,
)


class SDLCInput(BaseModel):
    """Input for SDLC module."""
    
    repo: str
    branch: str
    commit_sha: str = ""
    commit_message: str = ""
    pusher: str = ""
    environment: str = "staging"
    stages: list[str] | None = None  # If None, run all stages
    config: dict[str, Any] = Field(default_factory=dict)


@ModuleRegistry.register
class SDLCModuleAdapter(BaseModule[SDLCInput, ModuleResult]):
    """
    SDLC automation module for Aurix.
    
    Automates software development lifecycle stages with
    confidence-based progression to full automation.
    """
    
    name = "sdlc"
    description = "Automated SDLC pipeline with confidence-based deployment"
    version = "1.0.0"
    
    input_model_class = SDLCInput
    
    def __init__(self):
        super().__init__()
        self._core: SDLCCore | None = None
        self._risk_assessor = SDLCRiskAssessor()
    
    async def initialize(self) -> None:
        """Initialize the core SDLC module."""
        self._core = SDLCCore()
        await super().initialize()
    
    async def execute(
        self,
        input_data: SDLCInput,
        context: ModuleContext,
    ) -> ModuleResult:
        """Execute SDLC pipeline."""
        if self._core is None:
            await self.initialize()
        
        # Determine which stages to run based on automation mode
        stages_to_run = input_data.stages
        
        # In shadow/suggestion mode, we might limit what's auto-executed
        if context.automation_mode in [AutomationMode.SHADOW, AutomationMode.SUGGESTION]:
            # Don't auto-deploy in shadow mode
            if stages_to_run is None:
                stages_to_run = [
                    "checkout", "install_dependencies", "lint",
                    "unit_tests", "integration_tests", "security_scan", "build"
                ]
        
        # Run the pipeline
        execution = await self._core.execute_pipeline(
            repo=input_data.repo,
            branch=input_data.branch,
            commit_sha=input_data.commit_sha,
            environment=input_data.environment,
            stages=stages_to_run,
        )
        
        # Determine overall decision
        decision = self._determine_decision(execution)
        
        # Determine if human review required
        human_required = self._needs_human_review(execution, context)
        
        # Calculate confidence based on stage results
        confidence = self._calculate_confidence(execution)
        
        return ModuleResult(
            module_name=self.name,
            task_id=self.get_task_id(input_data),
            decision=decision,
            confidence=confidence,
            risk_profile=await self.assess_risk(input_data),
            automation_mode=context.automation_mode,
            human_review_required=human_required,
            details={
                "execution_id": execution.execution_id,
                "stages": [
                    {
                        "name": s.stage_name,
                        "status": s.status.value,
                        "duration": s.duration_seconds,
                        "error": s.error_message,
                    }
                    for s in execution.stage_results
                ],
                "environment": execution.environment,
                "total_duration": execution.total_duration_seconds,
            },
            summary=self._build_summary(execution),
            actions=self._build_actions(execution, context),
            warnings=self._collect_warnings(execution),
            errors=self._collect_errors(execution),
        )
    
    async def assess_risk(self, input_data: SDLCInput) -> RiskProfile:
        """Assess risk for this pipeline execution."""
        # Risk varies by environment
        env_risk = {
            "development": 0.1,
            "staging": 0.3,
            "production": 0.8,
        }
        
        base_risk = env_risk.get(input_data.environment, 0.5)
        
        return self._risk_assessor.assess({
            "environment": input_data.environment,
            "branch": input_data.branch,
            "base_risk": base_risk,
        })
    
    def get_task_id(self, input_data: SDLCInput) -> str:
        """Generate task ID for tracking."""
        # Track by repo + environment
        return f"sdlc:{input_data.repo}:{input_data.environment}"
    
    def _determine_decision(self, execution: PipelineExecution) -> ModuleDecision:
        """Determine overall decision from execution."""
        failed_stages = [
            s for s in execution.stage_results
            if s.status == StageStatus.FAILED
        ]
        
        if not failed_stages:
            return ModuleDecision.APPROVE
        
        # Check if any critical stage failed
        critical_stages = {"unit_tests", "security_scan", "build"}
        critical_failures = [s for s in failed_stages if s.stage_name in critical_stages]
        
        if critical_failures:
            return ModuleDecision.REJECT
        
        return ModuleDecision.NEEDS_REVIEW
    
    def _needs_human_review(
        self,
        execution: PipelineExecution,
        context: ModuleContext,
    ) -> bool:
        """Check if human review is needed."""
        if context.automation_mode == AutomationMode.SHADOW:
            return True
        
        if context.automation_mode == AutomationMode.SUGGESTION:
            return True
        
        # For production deployments, always require review in auto_with_review
        if execution.environment == "production":
            if context.automation_mode != AutomationMode.FULL_AUTO:
                return True
        
        # Review if any stage failed
        if any(s.status == StageStatus.FAILED for s in execution.stage_results):
            return True
        
        return False
    
    def _calculate_confidence(self, execution: PipelineExecution) -> float:
        """Calculate confidence based on execution results."""
        if not execution.stage_results:
            return 0.0
        
        successful = sum(
            1 for s in execution.stage_results
            if s.status == StageStatus.SUCCESS
        )
        
        return successful / len(execution.stage_results)
    
    def _build_summary(self, execution: PipelineExecution) -> str:
        """Build human-readable summary."""
        total = len(execution.stage_results)
        successful = sum(1 for s in execution.stage_results if s.status == StageStatus.SUCCESS)
        failed = sum(1 for s in execution.stage_results if s.status == StageStatus.FAILED)
        
        summary = f"Pipeline completed: {successful}/{total} stages passed"
        
        if failed > 0:
            failed_names = [
                s.stage_name for s in execution.stage_results
                if s.status == StageStatus.FAILED
            ]
            summary += f". Failed: {', '.join(failed_names)}"
        
        summary += f". Duration: {execution.total_duration_seconds:.1f}s"
        
        return summary
    
    def _build_actions(
        self,
        execution: PipelineExecution,
        context: ModuleContext,
    ) -> list[dict]:
        """Build actionable items."""
        actions = []
        
        # If all passed and in auto mode, suggest deployment
        all_passed = all(
            s.status == StageStatus.SUCCESS
            for s in execution.stage_results
        )
        
        if all_passed:
            if execution.environment == "staging":
                actions.append({
                    "type": "promote",
                    "message": "Promote to production",
                    "target_environment": "production",
                })
            elif execution.environment == "production":
                actions.append({
                    "type": "notify",
                    "message": "Deployment complete",
                })
        else:
            # Failed - suggest rollback if in production
            if execution.environment == "production":
                actions.append({
                    "type": "rollback",
                    "message": "Consider rollback",
                })
        
        return actions
    
    def _collect_warnings(self, execution: PipelineExecution) -> list[str]:
        """Collect warnings from execution."""
        warnings = []
        
        for stage in execution.stage_results:
            if stage.status == StageStatus.SKIPPED:
                warnings.append(f"Stage '{stage.stage_name}' was skipped")
            
            if stage.warnings:
                warnings.extend(stage.warnings)
        
        return warnings
    
    def _collect_errors(self, execution: PipelineExecution) -> list[str]:
        """Collect errors from execution."""
        errors = []
        
        for stage in execution.stage_results:
            if stage.status == StageStatus.FAILED and stage.error_message:
                errors.append(f"{stage.stage_name}: {stage.error_message}")
        
        return errors
