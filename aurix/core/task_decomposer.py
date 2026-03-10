"""
Task Decomposition Engine for Aurix Platform

Breaks down complex human workflows into smaller, automatable tasks.
Identifies dependencies, parallelization opportunities, and risk boundaries.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Types of tasks in a workflow."""
    
    DECISION = "decision"          # Requires judgment/choice
    VALIDATION = "validation"      # Checks/verifies something
    TRANSFORMATION = "transform"   # Changes/modifies data
    ANALYSIS = "analysis"          # Examines/evaluates
    NOTIFICATION = "notification"  # Communicates/alerts
    APPROVAL = "approval"          # Requires sign-off
    EXECUTION = "execution"        # Performs action
    MONITORING = "monitoring"      # Observes/tracks


class TaskStatus(str, Enum):
    """Status of a task."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class AutomationLevel(str, Enum):
    """How automated a task can be."""
    
    FULLY_AUTOMATED = "fully_automated"      # No human needed
    MOSTLY_AUTOMATED = "mostly_automated"    # Human spot-check
    SEMI_AUTOMATED = "semi_automated"        # Human approval
    HUMAN_ASSISTED = "human_assisted"        # AI assists human
    HUMAN_ONLY = "human_only"                # Cannot automate


class Task(BaseModel):
    """
    Represents a single automatable task.
    
    Tasks are the atomic units of workflow automation.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(description="Human-readable task name")
    description: str = Field(default="", description="Detailed description")
    
    # Task properties
    task_type: TaskType = Field(default=TaskType.EXECUTION)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    
    # Dependencies
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    
    # Automation properties
    automation_level: AutomationLevel = Field(default=AutomationLevel.SEMI_AUTOMATED)
    estimated_duration_seconds: int = Field(default=60)
    can_parallelize: bool = Field(default=True)
    
    # Risk indicators
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    requires_human_approval: bool = Field(default=False)
    is_reversible: bool = Field(default=True)
    
    # Execution context
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    handler: Optional[str] = None  # Name of function/agent to handle
    
    # Results
    result: Optional[Any] = None
    error: Optional[str] = None
    executed_at: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def mark_completed(self, result: Any = None) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.executed_at = datetime.utcnow()
    
    def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.executed_at = datetime.utcnow()


class TaskGraph(BaseModel):
    """
    Directed acyclic graph of tasks.
    
    Represents the complete workflow with dependencies.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str = Field(description="Workflow name")
    description: str = Field(default="")
    
    # Tasks
    tasks: Dict[str, Task] = Field(default_factory=dict)
    
    # Graph properties
    root_tasks: List[str] = Field(default_factory=list)
    terminal_tasks: List[str] = Field(default_factory=list)
    
    # Execution tracking
    current_tasks: List[str] = Field(default_factory=list)
    completed_tasks: List[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def add_task(self, task: Task) -> None:
        """Add a task to the graph."""
        self.tasks[task.id] = task
        
        # Update root/terminal lists
        if not task.dependencies:
            if task.id not in self.root_tasks:
                self.root_tasks.append(task.id)
        
        if not task.dependents:
            if task.id not in self.terminal_tasks:
                self.terminal_tasks.append(task.id)
    
    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """Add a dependency between tasks."""
        if task_id not in self.tasks or depends_on not in self.tasks:
            raise ValueError("Both tasks must exist in graph")
        
        self.tasks[task_id].dependencies.append(depends_on)
        self.tasks[depends_on].dependents.append(task_id)
        
        # Update root/terminal lists
        if task_id in self.root_tasks:
            self.root_tasks.remove(task_id)
        if depends_on in self.terminal_tasks:
            self.terminal_tasks.remove(depends_on)
    
    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute (all dependencies met)."""
        ready = []
        
        for task_id, task in self.tasks.items():
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check all dependencies are completed
            deps_met = all(
                self.tasks[dep].status == TaskStatus.COMPLETED
                for dep in task.dependencies
            )
            
            if deps_met:
                ready.append(task)
        
        return ready
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get tasks in execution order (topological sort).
        
        Returns list of lists (each inner list can be parallelized).
        """
        levels: List[List[str]] = []
        remaining = set(self.tasks.keys())
        completed: Set[str] = set()
        
        while remaining:
            # Find tasks with all dependencies completed
            current_level = []
            for task_id in remaining:
                task = self.tasks[task_id]
                if all(dep in completed for dep in task.dependencies):
                    current_level.append(task_id)
            
            if not current_level:
                # Circular dependency detected
                raise ValueError("Circular dependency detected in task graph")
            
            levels.append(current_level)
            completed.update(current_level)
            remaining -= set(current_level)
        
        return levels
    
    def get_critical_path(self) -> List[str]:
        """
        Get the critical path (longest path through graph).
        
        Useful for identifying bottlenecks.
        """
        # Calculate earliest start time for each task
        earliest: Dict[str, int] = {}
        
        for level in self.get_execution_order():
            for task_id in level:
                task = self.tasks[task_id]
                if not task.dependencies:
                    earliest[task_id] = 0
                else:
                    earliest[task_id] = max(
                        earliest[dep] + self.tasks[dep].estimated_duration_seconds
                        for dep in task.dependencies
                    )
        
        # Find task with latest earliest start + duration
        end_times = {
            tid: earliest[tid] + self.tasks[tid].estimated_duration_seconds
            for tid in self.tasks
        }
        
        last_task = max(end_times.keys(), key=lambda x: end_times[x])
        
        # Backtrack to find critical path
        path = [last_task]
        current = last_task
        
        while self.tasks[current].dependencies:
            # Find dependency that ends latest
            deps = self.tasks[current].dependencies
            next_task = max(
                deps,
                key=lambda x: earliest[x] + self.tasks[x].estimated_duration_seconds
            )
            path.insert(0, next_task)
            current = next_task
        
        return path


class TaskDecomposer:
    """
    Decomposes complex workflows into automatable tasks.
    
    Uses templates and patterns to identify:
    - Atomic tasks
    - Dependencies
    - Risk boundaries
    - Parallelization opportunities
    """
    
    # Common workflow patterns
    PATTERNS = {
        "code_review": [
            {
                "name": "fetch_changes",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.1,
            },
            {
                "name": "static_analysis",
                "type": TaskType.ANALYSIS,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.2,
                "depends_on": ["fetch_changes"],
            },
            {
                "name": "security_scan",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": ["fetch_changes"],
            },
            {
                "name": "style_check",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.1,
                "depends_on": ["fetch_changes"],
            },
            {
                "name": "test_coverage_analysis",
                "type": TaskType.ANALYSIS,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.2,
                "depends_on": ["fetch_changes"],
            },
            {
                "name": "complexity_analysis",
                "type": TaskType.ANALYSIS,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.2,
                "depends_on": ["fetch_changes"],
            },
            {
                "name": "logic_review",
                "type": TaskType.ANALYSIS,
                "automation": AutomationLevel.SEMI_AUTOMATED,
                "risk": 0.6,
                "depends_on": ["static_analysis", "complexity_analysis"],
            },
            {
                "name": "generate_review_summary",
                "type": TaskType.TRANSFORMATION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": [
                    "security_scan",
                    "style_check",
                    "test_coverage_analysis",
                    "logic_review",
                ],
            },
            {
                "name": "make_approval_decision",
                "type": TaskType.DECISION,
                "automation": AutomationLevel.SEMI_AUTOMATED,
                "risk": 0.7,
                "depends_on": ["generate_review_summary"],
            },
            {
                "name": "post_review_comments",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": ["make_approval_decision"],
            },
        ],
        "sdlc_deployment": [
            {
                "name": "validate_prerequisites",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.2,
            },
            {
                "name": "run_tests",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": ["validate_prerequisites"],
            },
            {
                "name": "build_artifacts",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": ["run_tests"],
            },
            {
                "name": "security_scan",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.4,
                "depends_on": ["build_artifacts"],
            },
            {
                "name": "compliance_check",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.5,
                "depends_on": ["build_artifacts"],
            },
            {
                "name": "deploy_staging",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.4,
                "depends_on": ["security_scan", "compliance_check"],
            },
            {
                "name": "run_integration_tests",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": ["deploy_staging"],
            },
            {
                "name": "performance_validation",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.4,
                "depends_on": ["deploy_staging"],
            },
            {
                "name": "approve_production",
                "type": TaskType.APPROVAL,
                "automation": AutomationLevel.SEMI_AUTOMATED,
                "risk": 0.8,
                "depends_on": ["run_integration_tests", "performance_validation"],
            },
            {
                "name": "deploy_production",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.SEMI_AUTOMATED,
                "risk": 0.9,
                "depends_on": ["approve_production"],
            },
            {
                "name": "verify_deployment",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": ["deploy_production"],
            },
            {
                "name": "notify_stakeholders",
                "type": TaskType.NOTIFICATION,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.1,
                "depends_on": ["verify_deployment"],
            },
        ],
        "incident_response": [
            {
                "name": "detect_anomaly",
                "type": TaskType.MONITORING,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.2,
            },
            {
                "name": "classify_severity",
                "type": TaskType.DECISION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.5,
                "depends_on": ["detect_anomaly"],
            },
            {
                "name": "gather_diagnostics",
                "type": TaskType.ANALYSIS,
                "automation": AutomationLevel.FULLY_AUTOMATED,
                "risk": 0.2,
                "depends_on": ["classify_severity"],
            },
            {
                "name": "identify_root_cause",
                "type": TaskType.ANALYSIS,
                "automation": AutomationLevel.SEMI_AUTOMATED,
                "risk": 0.6,
                "depends_on": ["gather_diagnostics"],
            },
            {
                "name": "propose_remediation",
                "type": TaskType.DECISION,
                "automation": AutomationLevel.SEMI_AUTOMATED,
                "risk": 0.7,
                "depends_on": ["identify_root_cause"],
            },
            {
                "name": "execute_remediation",
                "type": TaskType.EXECUTION,
                "automation": AutomationLevel.HUMAN_ASSISTED,
                "risk": 0.8,
                "depends_on": ["propose_remediation"],
            },
            {
                "name": "verify_resolution",
                "type": TaskType.VALIDATION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.3,
                "depends_on": ["execute_remediation"],
            },
            {
                "name": "document_incident",
                "type": TaskType.TRANSFORMATION,
                "automation": AutomationLevel.MOSTLY_AUTOMATED,
                "risk": 0.2,
                "depends_on": ["verify_resolution"],
            },
        ],
    }
    
    def __init__(self):
        """Initialize task decomposer."""
        self.custom_patterns: Dict[str, List[Dict]] = {}
    
    def register_pattern(
        self,
        pattern_name: str,
        tasks: List[Dict[str, Any]],
    ) -> None:
        """Register a custom workflow pattern."""
        self.custom_patterns[pattern_name] = tasks
    
    def decompose(
        self,
        workflow_name: str,
        pattern: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskGraph:
        """
        Decompose a workflow into a task graph.
        
        Args:
            workflow_name: Name for the workflow
            pattern: Pattern to use (from PATTERNS or custom)
            context: Additional context for customization
            
        Returns:
            TaskGraph with all tasks and dependencies
        """
        context = context or {}
        
        # Get pattern definition
        if pattern:
            if pattern in self.custom_patterns:
                task_defs = self.custom_patterns[pattern]
            elif pattern in self.PATTERNS:
                task_defs = self.PATTERNS[pattern]
            else:
                raise ValueError(f"Unknown pattern: {pattern}")
        else:
            task_defs = self._infer_pattern(workflow_name, context)
        
        # Create task graph
        graph = TaskGraph(name=workflow_name, description=context.get("description", ""))
        
        # Create tasks
        task_id_map: Dict[str, str] = {}  # name -> id
        
        for task_def in task_defs:
            task = Task(
                name=task_def["name"],
                description=task_def.get("description", ""),
                task_type=TaskType(task_def.get("type", TaskType.EXECUTION)),
                automation_level=AutomationLevel(
                    task_def.get("automation", AutomationLevel.SEMI_AUTOMATED)
                ),
                risk_score=task_def.get("risk", 0.5),
                estimated_duration_seconds=task_def.get("duration", 60),
                tags=task_def.get("tags", []),
            )
            
            # Apply context overrides
            if task.name in context.get("risk_overrides", {}):
                task.risk_score = context["risk_overrides"][task.name]
            
            graph.add_task(task)
            task_id_map[task.name] = task.id
        
        # Add dependencies
        for task_def in task_defs:
            task_name = task_def["name"]
            task_id = task_id_map[task_name]
            
            for dep_name in task_def.get("depends_on", []):
                if dep_name in task_id_map:
                    graph.add_dependency(task_id, task_id_map[dep_name])
        
        return graph
    
    def _infer_pattern(
        self,
        workflow_name: str,
        context: Dict[str, Any],
    ) -> List[Dict]:
        """Infer pattern from workflow name and context."""
        # Simple heuristic matching
        name_lower = workflow_name.lower()
        
        if any(k in name_lower for k in ["review", "pr", "code"]):
            return self.PATTERNS["code_review"]
        elif any(k in name_lower for k in ["deploy", "release", "sdlc"]):
            return self.PATTERNS["sdlc_deployment"]
        elif any(k in name_lower for k in ["incident", "alert", "response"]):
            return self.PATTERNS["incident_response"]
        else:
            # Default generic pattern
            return [
                {
                    "name": "analyze_request",
                    "type": TaskType.ANALYSIS,
                    "automation": AutomationLevel.SEMI_AUTOMATED,
                    "risk": 0.5,
                },
                {
                    "name": "execute_action",
                    "type": TaskType.EXECUTION,
                    "automation": AutomationLevel.SEMI_AUTOMATED,
                    "risk": 0.5,
                    "depends_on": ["analyze_request"],
                },
                {
                    "name": "validate_result",
                    "type": TaskType.VALIDATION,
                    "automation": AutomationLevel.MOSTLY_AUTOMATED,
                    "risk": 0.3,
                    "depends_on": ["execute_action"],
                },
            ]
    
    def decompose_custom(
        self,
        workflow_name: str,
        steps: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> TaskGraph:
        """
        Decompose a workflow from free-form step descriptions.
        
        Uses LLM-like heuristics to understand and structure steps.
        
        Args:
            workflow_name: Name for the workflow
            steps: List of step descriptions
            context: Additional context
            
        Returns:
            TaskGraph with inferred structure
        """
        context = context or {}
        graph = TaskGraph(name=workflow_name)
        
        previous_task_id: Optional[str] = None
        
        for i, step in enumerate(steps):
            # Analyze step to determine properties
            task_type = self._infer_task_type(step)
            automation = self._infer_automation_level(step)
            risk = self._infer_risk(step, context)
            
            task = Task(
                name=f"step_{i+1}",
                description=step,
                task_type=task_type,
                automation_level=automation,
                risk_score=risk,
            )
            
            graph.add_task(task)
            
            # Simple sequential dependency
            if previous_task_id:
                graph.add_dependency(task.id, previous_task_id)
            
            previous_task_id = task.id
        
        return graph
    
    def _infer_task_type(self, description: str) -> TaskType:
        """Infer task type from description."""
        desc_lower = description.lower()
        
        keywords = {
            TaskType.DECISION: ["decide", "choose", "select", "determine"],
            TaskType.VALIDATION: ["check", "verify", "validate", "ensure", "confirm"],
            TaskType.TRANSFORMATION: ["convert", "transform", "modify", "update", "change"],
            TaskType.ANALYSIS: ["analyze", "review", "examine", "assess", "evaluate"],
            TaskType.NOTIFICATION: ["notify", "alert", "inform", "send", "email"],
            TaskType.APPROVAL: ["approve", "sign off", "authorize"],
            TaskType.MONITORING: ["monitor", "watch", "track", "observe"],
        }
        
        for task_type, words in keywords.items():
            if any(word in desc_lower for word in words):
                return task_type
        
        return TaskType.EXECUTION
    
    def _infer_automation_level(self, description: str) -> AutomationLevel:
        """Infer automation level from description."""
        desc_lower = description.lower()
        
        # High automation indicators
        if any(word in desc_lower for word in ["automatic", "automated", "script"]):
            return AutomationLevel.FULLY_AUTOMATED
        
        # Low automation indicators
        if any(word in desc_lower for word in ["manual", "human", "person"]):
            return AutomationLevel.HUMAN_ONLY
        
        # Approval/decision indicators
        if any(word in desc_lower for word in ["approve", "decide", "judgment"]):
            return AutomationLevel.SEMI_AUTOMATED
        
        return AutomationLevel.MOSTLY_AUTOMATED
    
    def _infer_risk(
        self,
        description: str,
        context: Dict[str, Any],
    ) -> float:
        """Infer risk score from description and context."""
        desc_lower = description.lower()
        risk = 0.5  # Default medium risk
        
        # High risk indicators
        high_risk = ["production", "deploy", "delete", "security", "payment", "user data"]
        if any(word in desc_lower for word in high_risk):
            risk += 0.3
        
        # Low risk indicators
        low_risk = ["test", "staging", "review", "check", "notify"]
        if any(word in desc_lower for word in low_risk):
            risk -= 0.2
        
        # Context adjustments
        if context.get("environment") == "production":
            risk += 0.2
        
        return max(0.0, min(1.0, risk))
    
    def analyze_parallelization(self, graph: TaskGraph) -> Dict[str, Any]:
        """
        Analyze parallelization opportunities in a graph.
        
        Returns optimization suggestions.
        """
        execution_order = graph.get_execution_order()
        critical_path = graph.get_critical_path()
        
        # Calculate metrics
        total_duration = sum(
            graph.tasks[tid].estimated_duration_seconds
            for tid in graph.tasks
        )
        
        critical_duration = sum(
            graph.tasks[tid].estimated_duration_seconds
            for tid in critical_path
        )
        
        # Find parallelizable groups
        parallel_groups = [level for level in execution_order if len(level) > 1]
        
        return {
            "total_tasks": len(graph.tasks),
            "parallelizable_levels": len(parallel_groups),
            "max_parallelism": max(len(level) for level in execution_order),
            "critical_path_length": len(critical_path),
            "critical_path_tasks": critical_path,
            "total_duration_sequential": total_duration,
            "total_duration_parallel": critical_duration,
            "speedup_factor": round(total_duration / critical_duration, 2) if critical_duration > 0 else 1.0,
            "execution_order": execution_order,
        }
