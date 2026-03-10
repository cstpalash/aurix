"""
SDLC Automation Module for Aurix Platform

Automates the Software Development Lifecycle with confidence-based
graduation from human oversight to full automation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from aurix.core.risk_assessor import SDLCRiskAssessor, RiskLevel, RiskProfile
from aurix.core.confidence_engine import (
    AutomationMode,
    ConfidenceEngine,
    ConfidenceTracker,
    Outcome,
    OutcomeType,
)
from aurix.core.task_decomposer import TaskDecomposer, TaskGraph, Task, TaskStatus
from aurix.core.micro_agent import AgentOrchestrator, AgentResult


class SDLCPhase(str, Enum):
    """Phases of the software development lifecycle."""
    
    PLANNING = "planning"
    REQUIREMENTS = "requirements"
    DESIGN = "design"
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    RELEASE = "release"
    MONITORING = "monitoring"
    MAINTENANCE = "maintenance"


class DeploymentEnvironment(str, Enum):
    """Deployment environments."""
    
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class DeploymentStrategy(str, Enum):
    """Deployment strategies."""
    
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    A_B_TEST = "ab_test"


class PipelineStatus(str, Enum):
    """Status of a pipeline execution."""
    
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"
    ROLLED_BACK = "rolled_back"


@dataclass
class PipelineStage:
    """A stage in the SDLC pipeline."""
    
    name: str
    phase: SDLCPhase
    environment: Optional[DeploymentEnvironment] = None
    
    # Execution
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    success: bool = False
    error: Optional[str] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    # Automation
    automation_mode: AutomationMode = AutomationMode.SHADOW
    requires_approval: bool = False
    approved_by: Optional[str] = None
    
    # Risk
    risk_score: float = 0.5
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class PipelineConfig(BaseModel):
    """Configuration for an SDLC pipeline."""
    
    name: str
    repo: str
    branch: str = "main"
    
    # Stages
    stages: List[str] = Field(default_factory=list)
    
    # Environment configuration
    environments: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    # Deployment
    deployment_strategy: DeploymentStrategy = DeploymentStrategy.ROLLING
    rollback_enabled: bool = True
    
    # Automation
    automation_modes: Dict[str, str] = Field(default_factory=dict)  # stage -> mode
    
    # Approval gates
    approval_required: Dict[str, bool] = Field(default_factory=dict)  # stage -> required
    
    # Notifications
    notify_on_failure: bool = True
    notify_on_success: bool = False
    notification_channels: List[str] = Field(default_factory=list)


class PipelineExecution(BaseModel):
    """A single execution of the SDLC pipeline."""
    
    execution_id: str
    config: PipelineConfig
    
    # Trigger information
    trigger_type: str = "manual"  # manual, push, schedule, webhook
    trigger_ref: str = ""  # commit SHA, tag, etc.
    triggered_by: str = ""
    
    # Stages
    stages: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    current_stage: Optional[str] = None
    
    # Status
    status: PipelineStatus = PipelineStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Risk
    overall_risk: float = 0.5
    
    # Results
    artifacts: Dict[str, str] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class SDLCModule:
    """
    Complete SDLC automation module.
    
    Manages the entire software development lifecycle with
    confidence-based automation graduation.
    """
    
    # Default stage configuration
    DEFAULT_STAGES = [
        {
            "name": "checkout",
            "phase": SDLCPhase.DEVELOPMENT,
            "risk": 0.1,
            "automation": AutomationMode.FULL_AUTO,
        },
        {
            "name": "lint",
            "phase": SDLCPhase.TESTING,
            "risk": 0.1,
            "automation": AutomationMode.FULL_AUTO,
        },
        {
            "name": "test",
            "phase": SDLCPhase.TESTING,
            "risk": 0.2,
            "automation": AutomationMode.FULL_AUTO,
        },
        {
            "name": "build",
            "phase": SDLCPhase.DEVELOPMENT,
            "risk": 0.2,
            "automation": AutomationMode.FULL_AUTO,
        },
        {
            "name": "security_scan",
            "phase": SDLCPhase.TESTING,
            "risk": 0.3,
            "automation": AutomationMode.AUTO_WITH_REVIEW,
        },
        {
            "name": "deploy_staging",
            "phase": SDLCPhase.STAGING,
            "environment": DeploymentEnvironment.STAGING,
            "risk": 0.4,
            "automation": AutomationMode.AUTO_WITH_REVIEW,
        },
        {
            "name": "integration_test",
            "phase": SDLCPhase.TESTING,
            "environment": DeploymentEnvironment.STAGING,
            "risk": 0.3,
            "automation": AutomationMode.FULL_AUTO,
        },
        {
            "name": "performance_test",
            "phase": SDLCPhase.TESTING,
            "environment": DeploymentEnvironment.STAGING,
            "risk": 0.3,
            "automation": AutomationMode.AUTO_WITH_REVIEW,
        },
        {
            "name": "approve_production",
            "phase": SDLCPhase.RELEASE,
            "risk": 0.8,
            "automation": AutomationMode.SUGGESTION,
            "requires_approval": True,
        },
        {
            "name": "deploy_production",
            "phase": SDLCPhase.PRODUCTION,
            "environment": DeploymentEnvironment.PRODUCTION,
            "risk": 0.9,
            "automation": AutomationMode.SUGGESTION,
        },
        {
            "name": "verify_deployment",
            "phase": SDLCPhase.MONITORING,
            "environment": DeploymentEnvironment.PRODUCTION,
            "risk": 0.3,
            "automation": AutomationMode.FULL_AUTO,
        },
        {
            "name": "notify",
            "phase": SDLCPhase.RELEASE,
            "risk": 0.1,
            "automation": AutomationMode.FULL_AUTO,
        },
    ]
    
    def __init__(
        self,
        confidence_engine: Optional[ConfidenceEngine] = None,
        risk_assessor: Optional[SDLCRiskAssessor] = None,
        orchestrator: Optional[AgentOrchestrator] = None,
    ):
        """Initialize SDLC module."""
        self.confidence_engine = confidence_engine or ConfidenceEngine()
        self.risk_assessor = risk_assessor or SDLCRiskAssessor()
        self.orchestrator = orchestrator or AgentOrchestrator()
        self.task_decomposer = TaskDecomposer()
        
        # Tracking
        self.confidence_tracker = ConfidenceTracker(self.confidence_engine)
        self._executions: Dict[str, PipelineExecution] = {}
        
        # Stage automation modes per repo
        self._stage_modes: Dict[str, Dict[str, AutomationMode]] = {}
        
        # Callbacks
        self._stage_handlers: Dict[str, Callable] = {}
        self._approval_callback: Optional[Callable] = None
    
    def create_pipeline(
        self,
        repo: str,
        name: Optional[str] = None,
        stages: Optional[List[str]] = None,
        **kwargs,
    ) -> PipelineConfig:
        """
        Create a new pipeline configuration.
        
        Args:
            repo: Repository name
            name: Pipeline name
            stages: List of stage names (uses defaults if not provided)
            **kwargs: Additional configuration
            
        Returns:
            PipelineConfig
        """
        if stages is None:
            stages = [s["name"] for s in self.DEFAULT_STAGES]
        
        config = PipelineConfig(
            name=name or f"pipeline_{repo}",
            repo=repo,
            stages=stages,
            **kwargs,
        )
        
        # Set default automation modes
        for stage_def in self.DEFAULT_STAGES:
            stage_name = stage_def["name"]
            if stage_name in stages:
                config.automation_modes[stage_name] = stage_def.get(
                    "automation", AutomationMode.SHADOW
                ).value
                config.approval_required[stage_name] = stage_def.get(
                    "requires_approval", False
                )
        
        return config
    
    async def execute_pipeline(
        self,
        config: PipelineConfig,
        trigger_type: str = "manual",
        trigger_ref: str = "",
        triggered_by: str = "system",
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineExecution:
        """
        Execute a complete pipeline.
        
        Args:
            config: Pipeline configuration
            trigger_type: Type of trigger
            trigger_ref: Reference (commit SHA, etc.)
            triggered_by: Who/what triggered
            context: Additional context
            
        Returns:
            PipelineExecution with results
        """
        context = context or {}
        
        # Create execution record
        import uuid
        execution_id = str(uuid.uuid4())[:12]
        
        execution = PipelineExecution(
            execution_id=execution_id,
            config=config,
            trigger_type=trigger_type,
            trigger_ref=trigger_ref,
            triggered_by=triggered_by,
            status=PipelineStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        
        self._executions[execution_id] = execution
        
        # Calculate overall risk
        execution.overall_risk = await self._calculate_pipeline_risk(config, context)
        
        # Execute stages
        try:
            for stage_name in config.stages:
                execution.current_stage = stage_name
                
                # Get stage configuration
                stage_def = next(
                    (s for s in self.DEFAULT_STAGES if s["name"] == stage_name),
                    {"name": stage_name, "risk": 0.5}
                )
                
                # Create stage record
                stage = PipelineStage(
                    name=stage_name,
                    phase=SDLCPhase(stage_def.get("phase", SDLCPhase.DEVELOPMENT)),
                    environment=stage_def.get("environment"),
                    risk_score=stage_def.get("risk", 0.5),
                    automation_mode=AutomationMode(
                        config.automation_modes.get(stage_name, "shadow")
                    ),
                    requires_approval=config.approval_required.get(stage_name, False),
                )
                
                # Execute stage
                stage = await self._execute_stage(
                    stage,
                    config,
                    execution,
                    context,
                )
                
                execution.stages[stage_name] = {
                    "status": stage.status.value,
                    "success": stage.success,
                    "error": stage.error,
                    "started_at": stage.started_at.isoformat() if stage.started_at else None,
                    "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
                    "outputs": stage.outputs,
                    "automation_mode": stage.automation_mode.value,
                }
                
                # Check for failure
                if not stage.success:
                    execution.status = PipelineStatus.FAILED
                    break
                
                # Update context with outputs
                context[f"stage_{stage_name}"] = stage.outputs
            
            if execution.status == PipelineStatus.RUNNING:
                execution.status = PipelineStatus.SUCCESS
                
        except Exception as e:
            execution.status = PipelineStatus.FAILED
            execution.stages[execution.current_stage or "unknown"] = {
                "status": PipelineStatus.FAILED.value,
                "error": str(e),
            }
        
        execution.completed_at = datetime.utcnow()
        execution.current_stage = None
        
        # Track outcome
        self._track_execution_outcome(execution)
        
        return execution
    
    async def _execute_stage(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        execution: PipelineExecution,
        context: Dict[str, Any],
    ) -> PipelineStage:
        """Execute a single pipeline stage."""
        stage.started_at = datetime.utcnow()
        stage.status = PipelineStatus.RUNNING
        
        try:
            # Check if approval is needed
            if stage.requires_approval:
                approved = await self._request_approval(stage, execution, context)
                if not approved:
                    stage.status = PipelineStatus.CANCELLED
                    stage.error = "Approval denied"
                    stage.completed_at = datetime.utcnow()
                    return stage
            
            # Get stage handler
            handler = self._stage_handlers.get(stage.name)
            
            if handler:
                # Custom handler
                result = await handler(stage, config, context)
                stage.success = result.get("success", False)
                stage.outputs = result.get("outputs", {})
                stage.error = result.get("error")
            else:
                # Default handlers
                result = await self._default_stage_handler(stage, config, context)
                stage.success = result["success"]
                stage.outputs = result.get("outputs", {})
                stage.error = result.get("error")
            
            stage.status = PipelineStatus.SUCCESS if stage.success else PipelineStatus.FAILED
            
        except Exception as e:
            stage.status = PipelineStatus.FAILED
            stage.success = False
            stage.error = str(e)
        
        stage.completed_at = datetime.utcnow()
        return stage
    
    async def _default_stage_handler(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Default handler for common stages."""
        
        # Simulate stage execution
        handlers = {
            "checkout": self._handle_checkout,
            "lint": self._handle_lint,
            "test": self._handle_test,
            "build": self._handle_build,
            "security_scan": self._handle_security_scan,
            "deploy_staging": self._handle_deploy,
            "deploy_production": self._handle_deploy,
            "integration_test": self._handle_test,
            "performance_test": self._handle_performance_test,
            "verify_deployment": self._handle_verify,
            "notify": self._handle_notify,
        }
        
        handler = handlers.get(stage.name, self._handle_generic)
        return await handler(stage, config, context)
    
    async def _handle_checkout(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle checkout stage."""
        # In real implementation, would clone/checkout repo
        return {
            "success": True,
            "outputs": {
                "repo": config.repo,
                "branch": config.branch,
                "commit": context.get("trigger_ref", "HEAD"),
            },
        }
    
    async def _handle_lint(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle lint stage."""
        # In real implementation, would run linters
        return {
            "success": True,
            "outputs": {
                "warnings": 0,
                "errors": 0,
            },
        }
    
    async def _handle_test(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle test stage."""
        # In real implementation, would run test suite
        return {
            "success": True,
            "outputs": {
                "total_tests": 100,
                "passed": 98,
                "failed": 2,
                "skipped": 0,
                "coverage": 85.5,
            },
        }
    
    async def _handle_build(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle build stage."""
        # In real implementation, would build artifacts
        import uuid
        artifact_id = str(uuid.uuid4())[:8]
        
        return {
            "success": True,
            "outputs": {
                "artifact_id": artifact_id,
                "artifact_path": f"/artifacts/{artifact_id}",
                "size_mb": 25.4,
            },
        }
    
    async def _handle_security_scan(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle security scan stage."""
        # In real implementation, would run security tools
        vulnerabilities = []  # Would be populated by actual scan
        
        return {
            "success": len([v for v in vulnerabilities if v.get("severity") == "critical"]) == 0,
            "outputs": {
                "vulnerabilities": vulnerabilities,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
            },
        }
    
    async def _handle_deploy(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle deployment stage."""
        environment = stage.environment
        
        # In real implementation, would perform deployment
        return {
            "success": True,
            "outputs": {
                "environment": environment.value if environment else "unknown",
                "deployment_id": f"deploy_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "strategy": config.deployment_strategy.value,
                "replicas": 3,
            },
        }
    
    async def _handle_performance_test(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle performance test stage."""
        # In real implementation, would run performance tests
        return {
            "success": True,
            "outputs": {
                "avg_response_time_ms": 45,
                "p95_response_time_ms": 120,
                "p99_response_time_ms": 250,
                "throughput_rps": 1000,
                "error_rate": 0.01,
            },
        }
    
    async def _handle_verify(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle deployment verification stage."""
        # In real implementation, would check deployment health
        return {
            "success": True,
            "outputs": {
                "health_check": "passed",
                "replicas_ready": 3,
                "replicas_total": 3,
            },
        }
    
    async def _handle_notify(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle notification stage."""
        # In real implementation, would send notifications
        return {
            "success": True,
            "outputs": {
                "channels_notified": config.notification_channels,
            },
        }
    
    async def _handle_generic(
        self,
        stage: PipelineStage,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generic handler for unknown stages."""
        return {
            "success": True,
            "outputs": {"message": f"Stage {stage.name} executed"},
        }
    
    async def _request_approval(
        self,
        stage: PipelineStage,
        execution: PipelineExecution,
        context: Dict[str, Any],
    ) -> bool:
        """Request approval for a stage."""
        stage.status = PipelineStatus.WAITING_APPROVAL
        
        if self._approval_callback:
            # Use custom approval callback
            return await self._approval_callback(stage, execution, context)
        
        # Default: auto-approve in non-production
        if stage.environment != DeploymentEnvironment.PRODUCTION:
            return True
        
        # In real implementation, would wait for human approval
        # For PoC, simulate approval based on automation mode
        if stage.automation_mode in [AutomationMode.FULL_AUTO, AutomationMode.AUTO_WITH_REVIEW]:
            return True
        
        return True  # Simulate approval for demo
    
    async def _calculate_pipeline_risk(
        self,
        config: PipelineConfig,
        context: Dict[str, Any],
    ) -> float:
        """Calculate overall pipeline risk."""
        risks = []
        
        for stage_name in config.stages:
            stage_def = next(
                (s for s in self.DEFAULT_STAGES if s["name"] == stage_name),
                {"risk": 0.5}
            )
            risks.append(stage_def.get("risk", 0.5))
        
        # Overall risk is max of individual stages
        return max(risks) if risks else 0.5
    
    def _track_execution_outcome(
        self,
        execution: PipelineExecution,
    ) -> None:
        """Track execution outcome for confidence scoring."""
        outcome_type = (
            OutcomeType.CORRECT
            if execution.status == PipelineStatus.SUCCESS
            else OutcomeType.INCORRECT
        )
        
        outcome = Outcome(
            task_id=f"pipeline_{execution.config.repo}",
            decision_id=execution.execution_id,
            outcome_type=outcome_type,
            timestamp=datetime.utcnow(),
            ai_decision=execution.status.value,
            risk_level=str(execution.overall_risk),
            automation_mode="mixed",  # Varies by stage
        )
        
        self.confidence_tracker.record(outcome)
    
    def register_stage_handler(
        self,
        stage_name: str,
        handler: Callable,
    ) -> None:
        """Register a custom handler for a stage."""
        self._stage_handlers[stage_name] = handler
    
    def set_approval_callback(
        self,
        callback: Callable,
    ) -> None:
        """Set callback for approval requests."""
        self._approval_callback = callback
    
    async def rollback(
        self,
        execution_id: str,
        target_stage: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rollback a pipeline execution.
        
        Args:
            execution_id: ID of execution to rollback
            target_stage: Optional stage to rollback to
            
        Returns:
            Rollback result
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return {"success": False, "error": "Execution not found"}
        
        if not execution.config.rollback_enabled:
            return {"success": False, "error": "Rollback not enabled"}
        
        # Find stages to rollback
        stages_to_rollback = []
        found_target = target_stage is None
        
        for stage_name in reversed(execution.config.stages):
            stage_info = execution.stages.get(stage_name, {})
            if stage_info.get("status") == PipelineStatus.SUCCESS.value:
                if target_stage and stage_name == target_stage:
                    found_target = True
                    break
                stages_to_rollback.append(stage_name)
        
        if not found_target:
            return {"success": False, "error": "Target stage not found"}
        
        # Perform rollback (simplified)
        rollback_results = {}
        for stage_name in stages_to_rollback:
            # In real implementation, would undo the stage
            rollback_results[stage_name] = {"rolled_back": True}
        
        execution.status = PipelineStatus.ROLLED_BACK
        
        return {
            "success": True,
            "execution_id": execution_id,
            "rolled_back_stages": stages_to_rollback,
            "results": rollback_results,
        }
    
    def get_execution(self, execution_id: str) -> Optional[PipelineExecution]:
        """Get execution by ID."""
        return self._executions.get(execution_id)
    
    def get_execution_history(
        self,
        repo: str,
        limit: int = 10,
    ) -> List[PipelineExecution]:
        """Get execution history for a repository."""
        executions = [
            e for e in self._executions.values()
            if e.config.repo == repo
        ]
        return sorted(
            executions,
            key=lambda x: x.started_at or datetime.min,
            reverse=True,
        )[:limit]
    
    def get_graduation_status(self, repo: str, stage: str) -> Dict[str, Any]:
        """Get graduation status for a stage."""
        task_type = f"sdlc_{repo}_{stage}"
        return self.confidence_tracker.get_graduation_status(task_type)
    
    def graduate_stage(
        self,
        repo: str,
        stage: str,
        target_mode: AutomationMode,
    ) -> bool:
        """Graduate a stage to a new automation mode."""
        status = self.get_graduation_status(repo, stage)
        
        if not status.get("eligible"):
            return False
        
        if repo not in self._stage_modes:
            self._stage_modes[repo] = {}
        
        self._stage_modes[repo][stage] = target_mode
        return True
    
    def get_pipeline_metrics(self, repo: str) -> Dict[str, Any]:
        """Get metrics for a pipeline."""
        executions = self.get_execution_history(repo, limit=100)
        
        if not executions:
            return {"message": "No executions found"}
        
        successful = sum(1 for e in executions if e.status == PipelineStatus.SUCCESS)
        failed = sum(1 for e in executions if e.status == PipelineStatus.FAILED)
        
        durations = [
            (e.completed_at - e.started_at).total_seconds()
            for e in executions
            if e.completed_at and e.started_at
        ]
        
        return {
            "total_executions": len(executions),
            "successful": successful,
            "failed": failed,
            "success_rate": successful / len(executions) if executions else 0,
            "average_duration_seconds": sum(durations) / len(durations) if durations else 0,
            "fastest_duration_seconds": min(durations) if durations else 0,
            "slowest_duration_seconds": max(durations) if durations else 0,
        }
