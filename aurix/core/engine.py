"""
Aurix - the orchestration engine.

This is the main entry point that ties together modules, storage,
and the confidence engine into a cohesive system.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aurix.core.module import (
    BaseModule,
    ModuleContext,
    ModuleResult,
    ModuleRegistry,
    ModuleDecision,
)
from aurix.core.confidence_engine import (
    ConfidenceEngine,
    ConfidenceTracker,
    AutomationMode,
    Outcome,
)
from aurix.core.risk_assessor import RiskLevel
from aurix.storage.base import Storage, OutcomeRecord, TaskState, ConfidenceSnapshot
from aurix.storage.file_storage import FileStorage


class ExecutionRequest(BaseModel):
    """Request to execute a module."""
    
    module: str
    input_data: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ExecutionResponse(BaseModel):
    """Response from module execution."""
    
    correlation_id: str
    module: str
    task_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    result: ModuleResult
    automation_mode: AutomationMode
    confidence_score: float
    can_graduate: bool
    graduation_info: dict[str, Any] = Field(default_factory=dict)


class Aurix:
    """
    Main Aurix orchestration engine.
    
    This class coordinates:
    - Module execution
    - Confidence tracking
    - Storage persistence
    - Automation mode management
    
    Usage:
        aurix = Aurix()
        await aurix.initialize()
        
        result = await aurix.execute(
            module="code_review",
            input_data={"repo": "owner/repo", "pr_number": 123}
        )
        
        await aurix.record_outcome(
            task_id=result.task_id,
            success=True,
            human_correction=False
        )
    """
    
    def __init__(
        self,
        storage: Storage | None = None,
        confidence_engine: ConfidenceEngine | None = None,
    ):
        self.storage = storage or FileStorage()
        self.confidence_engine = confidence_engine or ConfidenceEngine()
        self._trackers: dict[str, ConfidenceTracker] = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the Aurix engine."""
        await self.storage.initialize()
        
        # Load existing task states into trackers
        tasks = await self.storage.list_tasks()
        for task in tasks:
            tracker = self._get_or_create_tracker(task.task_id, task.module)
            tracker.current_mode = AutomationMode(task.current_mode)
            
            # Replay outcomes to restore state
            outcomes = await self.storage.get_outcomes(task.task_id)
            for outcome in outcomes:
                tracker.record_outcome(Outcome(
                    success=outcome.success,
                    human_correction=outcome.human_correction,
                    error_type=outcome.error_type,
                ))
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown the Aurix engine."""
        await self.storage.close()
        self._initialized = False
    
    def _get_or_create_tracker(self, task_id: str, module: str) -> ConfidenceTracker:
        """Get or create a confidence tracker for a task."""
        if task_id not in self._trackers:
            self._trackers[task_id] = ConfidenceTracker(
                task_id=task_id,
                module=module,
            )
        return self._trackers[task_id]
    
    async def execute(
        self,
        module: str,
        input_data: dict[str, Any],
        context: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> ExecutionResponse:
        """
        Execute a module with the given input.
        
        This is the main entry point for running any Aurix module.
        
        Args:
            module: Name of the module to execute
            input_data: Module-specific input data
            context: Optional execution context
            correlation_id: Optional correlation ID for tracing
        
        Returns:
            ExecutionResponse with result and confidence info
        """
        if not self._initialized:
            await self.initialize()
        
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Get the module
        module_instance = ModuleRegistry.get(module)
        if module_instance is None:
            raise ValueError(f"Unknown module: {module}")
        
        # Initialize module if needed
        if not module_instance._initialized:
            await module_instance.initialize()
        
        # Parse input data into the module's input model
        # This requires knowing the module's input type
        input_model = self._parse_input(module_instance, input_data)
        
        # Get task ID for tracking
        task_id = module_instance.get_task_id(input_model)
        
        # Get or create tracker
        tracker = self._get_or_create_tracker(task_id, module)
        
        # Determine automation mode
        automation_mode = tracker.current_mode
        
        # Build context
        ctx = ModuleContext(
            automation_mode=automation_mode,
            correlation_id=correlation_id,
            **(context or {}),
        )
        
        # Execute the module
        result = await module_instance.run(input_model, ctx)
        
        # Calculate current confidence
        confidence_score = self.confidence_engine.calculate_confidence(
            tracker.outcomes
        )
        
        # Check graduation status
        graduation = self.confidence_engine.check_graduation(
            tracker.outcomes,
            tracker.current_mode,
        )
        
        # Save confidence snapshot
        await self.storage.save_confidence_snapshot(ConfidenceSnapshot(
            task_id=task_id,
            confidence_score=confidence_score,
            success_rate=tracker.success_rate,
            total_outcomes=len(tracker.outcomes),
            current_mode=automation_mode.value,
            can_graduate=graduation.can_graduate,
        ))
        
        return ExecutionResponse(
            correlation_id=correlation_id,
            module=module,
            task_id=task_id,
            result=result,
            automation_mode=automation_mode,
            confidence_score=confidence_score,
            can_graduate=graduation.can_graduate,
            graduation_info={
                "current_mode": automation_mode.value,
                "next_mode": graduation.next_mode.value if graduation.next_mode else None,
                "reason": graduation.reason,
                "requirements": graduation.requirements,
            },
        )
    
    def _parse_input(self, module: BaseModule, input_data: dict[str, Any]) -> Any:
        """Parse input data into the module's input model."""
        # Get the type hint for InputT from the module
        # For now, we'll rely on modules accepting dict input
        # In a full implementation, we'd introspect the Generic type
        
        # Try to get the input_model_class if defined on the module
        if hasattr(module, 'input_model_class'):
            return module.input_model_class(**input_data)
        
        # Fall back to passing the dict directly
        # Module's execute() should handle this
        from pydantic import BaseModel
        
        class DynamicInput(BaseModel):
            class Config:
                extra = "allow"
        
        return DynamicInput(**input_data)
    
    async def record_outcome(
        self,
        task_id: str,
        module: str,
        success: bool,
        human_correction: bool = False,
        error_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Record the outcome of a task execution.
        
        This is called after the human (or automation) has made a decision.
        It updates the confidence tracker and potentially triggers graduation.
        
        Args:
            task_id: The task identifier
            module: The module name
            success: Whether the automation's decision was correct
            human_correction: Whether a human had to correct the decision
            error_type: Type of error if any
            metadata: Additional metadata
        
        Returns:
            Updated confidence information
        """
        if not self._initialized:
            await self.initialize()
        
        # Record in storage
        outcome_record = OutcomeRecord(
            id=str(uuid.uuid4()),
            task_id=task_id,
            module=module,
            success=success,
            human_correction=human_correction,
            error_type=error_type,
            metadata=metadata or {},
        )
        await self.storage.record_outcome(outcome_record)
        
        # Update tracker
        tracker = self._get_or_create_tracker(task_id, module)
        tracker.record_outcome(Outcome(
            success=success,
            human_correction=human_correction,
            error_type=error_type,
        ))
        
        # Calculate confidence
        confidence_score = self.confidence_engine.calculate_confidence(
            tracker.outcomes
        )
        tracker.confidence_score = confidence_score
        
        # Check for graduation
        graduation = self.confidence_engine.check_graduation(
            tracker.outcomes,
            tracker.current_mode,
        )
        
        # Auto-graduate if possible
        graduated = False
        if graduation.can_graduate and graduation.next_mode:
            tracker.current_mode = graduation.next_mode
            graduated = True
            
            # Update task state
            state = await self.storage.get_task_state(task_id)
            if state:
                state.current_mode = graduation.next_mode.value
                state.last_confidence_score = confidence_score
                await self.storage.update_task_state(state)
        
        # Check for degradation
        if self.confidence_engine.check_degradation(tracker.outcomes):
            # Demote mode if degraded
            if tracker.current_mode != AutomationMode.SHADOW:
                mode_order = [
                    AutomationMode.SHADOW,
                    AutomationMode.SUGGESTION,
                    AutomationMode.AUTO_WITH_REVIEW,
                    AutomationMode.FULL_AUTO,
                ]
                current_idx = mode_order.index(tracker.current_mode)
                tracker.current_mode = mode_order[max(0, current_idx - 1)]
        
        return {
            "task_id": task_id,
            "confidence_score": confidence_score,
            "success_rate": tracker.success_rate,
            "total_outcomes": len(tracker.outcomes),
            "current_mode": tracker.current_mode.value,
            "graduated": graduated,
            "can_graduate": graduation.can_graduate,
        }
    
    async def get_status(
        self,
        task_id: str | None = None,
        module: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get status of tracked tasks.
        
        Args:
            task_id: Optional specific task to get status for
            module: Optional filter by module
        
        Returns:
            List of task status dictionaries
        """
        if not self._initialized:
            await self.initialize()
        
        if task_id:
            tracker = self._trackers.get(task_id)
            if tracker:
                return [self._tracker_to_status(tracker)]
            return []
        
        statuses = []
        for tid, tracker in self._trackers.items():
            if module is None or tracker.module == module:
                statuses.append(self._tracker_to_status(tracker))
        
        return statuses
    
    def _tracker_to_status(self, tracker: ConfidenceTracker) -> dict[str, Any]:
        """Convert a tracker to a status dict."""
        graduation = self.confidence_engine.check_graduation(
            tracker.outcomes,
            tracker.current_mode,
        )
        
        return {
            "task_id": tracker.task_id,
            "module": tracker.module,
            "current_mode": tracker.current_mode.value,
            "confidence_score": tracker.confidence_score,
            "success_rate": tracker.success_rate,
            "total_outcomes": len(tracker.outcomes),
            "human_corrections": sum(1 for o in tracker.outcomes if o.human_correction),
            "can_graduate": graduation.can_graduate,
            "next_mode": graduation.next_mode.value if graduation.next_mode else None,
            "graduation_reason": graduation.reason,
        }
    
    async def get_dashboard(self) -> dict[str, Any]:
        """
        Get a dashboard summary of all tasks.
        
        Returns:
            Dashboard data with aggregated statistics
        """
        if not self._initialized:
            await self.initialize()
        
        tasks = await self.storage.list_tasks()
        
        # Aggregate by module
        by_module: dict[str, dict] = {}
        for task in tasks:
            if task.module not in by_module:
                by_module[task.module] = {
                    "total_tasks": 0,
                    "total_outcomes": 0,
                    "successful_outcomes": 0,
                    "human_corrections": 0,
                    "modes": {m.value: 0 for m in AutomationMode},
                }
            
            stats = by_module[task.module]
            stats["total_tasks"] += 1
            stats["total_outcomes"] += task.total_outcomes
            stats["successful_outcomes"] += task.successful_outcomes
            stats["human_corrections"] += task.human_corrections
            stats["modes"][task.current_mode] += 1
        
        # Calculate overall stats
        total_outcomes = sum(t.total_outcomes for t in tasks)
        successful_outcomes = sum(t.successful_outcomes for t in tasks)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_tasks": len(tasks),
            "total_outcomes": total_outcomes,
            "overall_success_rate": (
                successful_outcomes / total_outcomes if total_outcomes > 0 else 0
            ),
            "by_module": by_module,
            "mode_distribution": {
                m.value: sum(1 for t in tasks if t.current_mode == m.value)
                for m in AutomationMode
            },
        }


# Global instance
_aurix: Aurix | None = None


async def get_aurix() -> Aurix:
    """Get or create the global Aurix instance."""
    global _aurix
    if _aurix is None:
        _aurix = Aurix()
        await _aurix.initialize()
    return _aurix
