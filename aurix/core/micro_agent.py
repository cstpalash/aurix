"""
Micro-Agent Orchestration for Aurix Platform

Manages a fleet of specialized micro-agents that handle
individual tasks in an automated workflow.
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field

from aurix.core.task_decomposer import Task, TaskGraph, TaskStatus, AutomationLevel
from aurix.core.confidence_engine import AutomationMode, Outcome, OutcomeType


class AgentState(str, Enum):
    """State of a micro-agent."""
    
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"


class AgentCapability(str, Enum):
    """Capabilities that agents can have."""
    
    CODE_ANALYSIS = "code_analysis"
    SECURITY_SCAN = "security_scan"
    STYLE_CHECK = "style_check"
    TEST_EXECUTION = "test_execution"
    DEPLOYMENT = "deployment"
    NOTIFICATION = "notification"
    DECISION_MAKING = "decision_making"
    DATA_TRANSFORMATION = "data_transformation"
    HUMAN_INTERACTION = "human_interaction"


class AgentResult(BaseModel):
    """Result from an agent execution."""
    
    agent_id: str
    task_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    duration_ms: int = 0
    requires_human_review: bool = False
    review_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class MicroAgent(ABC):
    """
    Base class for micro-agents.
    
    Each micro-agent specializes in a specific type of task
    and can operate at different automation levels.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "BaseAgent",
        capabilities: Optional[List[AgentCapability]] = None,
    ):
        """Initialize micro-agent."""
        self.agent_id = agent_id or str(uuid.uuid4())[:8]
        self.name = name
        self.capabilities = capabilities or []
        self.state = AgentState.IDLE
        self.current_task: Optional[Task] = None
        self.automation_mode = AutomationMode.SHADOW
        
        # Execution history
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
        
    @abstractmethod
    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
    ) -> AgentResult:
        """
        Execute the assigned task.
        
        Args:
            task: Task to execute
            context: Execution context with inputs
            
        Returns:
            AgentResult with outcome
        """
        pass
    
    def can_handle(self, task: Task) -> bool:
        """Check if agent can handle a task type."""
        # Default implementation - override for specific logic
        return True
    
    async def validate_input(
        self,
        task: Task,
        context: Dict[str, Any],
    ) -> bool:
        """Validate task inputs before execution."""
        # Check required input schema
        if task.input_schema:
            for key, spec in task.input_schema.items():
                if spec.get("required", False) and key not in context:
                    return False
        return True
    
    async def pre_execute(
        self,
        task: Task,
        context: Dict[str, Any],
    ) -> None:
        """Hook called before execution."""
        self.state = AgentState.RUNNING
        self.current_task = task
    
    async def post_execute(
        self,
        task: Task,
        result: AgentResult,
    ) -> None:
        """Hook called after execution."""
        self.state = AgentState.IDLE
        self.current_task = None
        self.execution_count += 1
        
        if result.success:
            self.success_count += 1
        else:
            self.failure_count += 1
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent state."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": [c.value for c in self.capabilities],
            "state": self.state.value,
            "automation_mode": self.automation_mode.value,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
        }


class CodeAnalysisAgent(MicroAgent):
    """Agent specialized in code analysis tasks."""
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(
            agent_id=agent_id,
            name="CodeAnalysisAgent",
            capabilities=[
                AgentCapability.CODE_ANALYSIS,
                AgentCapability.STYLE_CHECK,
            ],
        )
    
    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
    ) -> AgentResult:
        """Execute code analysis."""
        await self.pre_execute(task, context)
        
        try:
            # Get code to analyze
            code = context.get("code", "")
            file_path = context.get("file_path", "")
            
            # Perform analysis (simplified)
            analysis_result = await self._analyze_code(code, file_path)
            
            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                success=True,
                result=analysis_result,
                confidence=analysis_result.get("confidence", 0.9),
                metadata={
                    "file_path": file_path,
                    "lines_analyzed": len(code.split("\n")),
                },
            )
            
        except Exception as e:
            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                success=False,
                error=str(e),
                confidence=0.0,
            )
        
        await self.post_execute(task, result)
        return result
    
    async def _analyze_code(
        self,
        code: str,
        file_path: str,
    ) -> Dict[str, Any]:
        """Perform code analysis."""
        # Simplified analysis - in production, use actual tools
        lines = code.split("\n")
        
        issues = []
        
        # Check for common issues
        for i, line in enumerate(lines):
            if len(line) > 120:
                issues.append({
                    "line": i + 1,
                    "type": "style",
                    "severity": "low",
                    "message": "Line too long",
                })
            
            if "TODO" in line or "FIXME" in line:
                issues.append({
                    "line": i + 1,
                    "type": "maintenance",
                    "severity": "info",
                    "message": "TODO/FIXME found",
                })
            
            if "password" in line.lower() or "secret" in line.lower():
                issues.append({
                    "line": i + 1,
                    "type": "security",
                    "severity": "high",
                    "message": "Potential sensitive data",
                })
        
        # Calculate confidence based on analysis depth
        confidence = 0.85 if len(lines) < 500 else 0.7
        
        return {
            "file_path": file_path,
            "total_lines": len(lines),
            "issues": issues,
            "issue_count": len(issues),
            "confidence": confidence,
            "summary": f"Found {len(issues)} issues in {len(lines)} lines",
        }


class SecurityScanAgent(MicroAgent):
    """Agent specialized in security scanning."""
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(
            agent_id=agent_id,
            name="SecurityScanAgent",
            capabilities=[AgentCapability.SECURITY_SCAN],
        )
    
    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
    ) -> AgentResult:
        """Execute security scan."""
        await self.pre_execute(task, context)
        
        try:
            files = context.get("files", [])
            scan_result = await self._scan_security(files)
            
            # Determine if human review needed
            high_severity = any(
                v.get("severity") == "critical"
                for v in scan_result.get("vulnerabilities", [])
            )
            
            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                success=True,
                result=scan_result,
                confidence=0.9,
                requires_human_review=high_severity,
                review_reason="Critical vulnerability detected" if high_severity else None,
            )
            
        except Exception as e:
            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                success=False,
                error=str(e),
            )
        
        await self.post_execute(task, result)
        return result
    
    async def _scan_security(
        self,
        files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Perform security scanning."""
        vulnerabilities = []
        
        # Patterns to check
        patterns = [
            (r"eval\(", "code_injection", "high"),
            (r"exec\(", "code_injection", "high"),
            (r"password\s*=\s*['\"]", "hardcoded_secret", "critical"),
            (r"api_key\s*=\s*['\"]", "hardcoded_secret", "critical"),
            (r"http://", "insecure_protocol", "medium"),
            (r"pickle\.load", "unsafe_deserialization", "high"),
        ]
        
        import re
        
        for file_info in files:
            content = file_info.get("content", "")
            filename = file_info.get("filename", "")
            
            for pattern, vuln_type, severity in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    vulnerabilities.append({
                        "file": filename,
                        "type": vuln_type,
                        "severity": severity,
                        "matches": len(matches),
                    })
        
        return {
            "files_scanned": len(files),
            "vulnerabilities": vulnerabilities,
            "vulnerability_count": len(vulnerabilities),
            "critical_count": sum(1 for v in vulnerabilities if v["severity"] == "critical"),
            "high_count": sum(1 for v in vulnerabilities if v["severity"] == "high"),
            "passed": len(vulnerabilities) == 0,
        }


class DecisionAgent(MicroAgent):
    """Agent specialized in making decisions based on aggregated data."""
    
    def __init__(self, agent_id: Optional[str] = None):
        super().__init__(
            agent_id=agent_id,
            name="DecisionAgent",
            capabilities=[AgentCapability.DECISION_MAKING],
        )
        
        # Decision thresholds
        self.approve_threshold = 0.8
        self.reject_threshold = 0.3
    
    async def execute(
        self,
        task: Task,
        context: Dict[str, Any],
    ) -> AgentResult:
        """Make a decision based on inputs."""
        await self.pre_execute(task, context)
        
        try:
            inputs = context.get("decision_inputs", {})
            decision_result = await self._make_decision(inputs)
            
            # Uncertain decisions need human review
            requires_review = decision_result["confidence"] < self.approve_threshold
            
            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                success=True,
                result=decision_result,
                confidence=decision_result["confidence"],
                requires_human_review=requires_review,
                review_reason="Decision confidence below threshold" if requires_review else None,
            )
            
        except Exception as e:
            result = AgentResult(
                agent_id=self.agent_id,
                task_id=task.id,
                success=False,
                error=str(e),
            )
        
        await self.post_execute(task, result)
        return result
    
    async def _make_decision(
        self,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Make decision based on inputs."""
        # Aggregate scores from various checks
        scores = []
        factors = []
        
        if "security_score" in inputs:
            scores.append(inputs["security_score"])
            factors.append(("security", inputs["security_score"]))
        
        if "style_score" in inputs:
            scores.append(inputs["style_score"])
            factors.append(("style", inputs["style_score"]))
        
        if "test_coverage" in inputs:
            scores.append(inputs["test_coverage"])
            factors.append(("test_coverage", inputs["test_coverage"]))
        
        if "complexity_score" in inputs:
            scores.append(inputs["complexity_score"])
            factors.append(("complexity", inputs["complexity_score"]))
        
        # Calculate overall confidence
        if scores:
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            # Weight minimum heavily to catch any major issues
            confidence = (avg_score * 0.4 + min_score * 0.6)
        else:
            confidence = 0.5  # No data, uncertain
        
        # Make decision
        if confidence >= self.approve_threshold:
            decision = "approve"
            reasoning = "All checks passed with high confidence"
        elif confidence <= self.reject_threshold:
            decision = "reject"
            reasoning = "Multiple checks failed or showed significant issues"
        else:
            decision = "needs_review"
            reasoning = "Mixed results require human judgment"
        
        return {
            "decision": decision,
            "confidence": round(confidence, 3),
            "factors": factors,
            "reasoning": reasoning,
            "threshold_used": {
                "approve": self.approve_threshold,
                "reject": self.reject_threshold,
            },
        }


class AgentOrchestrator:
    """
    Orchestrates multiple micro-agents to execute workflows.
    
    Responsibilities:
    - Route tasks to appropriate agents
    - Manage parallel execution
    - Handle human escalation
    - Track outcomes for confidence scoring
    """
    
    def __init__(self):
        """Initialize orchestrator."""
        self.agents: Dict[str, MicroAgent] = {}
        self.agent_types: Dict[str, Type[MicroAgent]] = {}
        self.task_outcomes: List[Outcome] = []
        
        # Register default agents
        self._register_default_agents()
    
    def _register_default_agents(self) -> None:
        """Register default agent types."""
        self.agent_types = {
            "code_analysis": CodeAnalysisAgent,
            "security_scan": SecurityScanAgent,
            "decision": DecisionAgent,
        }
    
    def register_agent(
        self,
        agent: MicroAgent,
    ) -> None:
        """Register an agent instance."""
        self.agents[agent.agent_id] = agent
    
    def register_agent_type(
        self,
        type_name: str,
        agent_class: Type[MicroAgent],
    ) -> None:
        """Register a new agent type."""
        self.agent_types[type_name] = agent_class
    
    def get_agent_for_task(
        self,
        task: Task,
    ) -> Optional[MicroAgent]:
        """Get an appropriate agent for a task."""
        # First check existing agents
        for agent in self.agents.values():
            if agent.state == AgentState.IDLE and agent.can_handle(task):
                return agent
        
        # Create new agent if needed
        agent_type = self._infer_agent_type(task)
        if agent_type in self.agent_types:
            agent = self.agent_types[agent_type]()
            self.register_agent(agent)
            return agent
        
        return None
    
    def _infer_agent_type(self, task: Task) -> str:
        """Infer agent type from task."""
        name_lower = task.name.lower()
        
        if any(k in name_lower for k in ["security", "scan", "vulnerability"]):
            return "security_scan"
        elif any(k in name_lower for k in ["code", "analysis", "style", "lint"]):
            return "code_analysis"
        elif any(k in name_lower for k in ["decision", "approve", "reject"]):
            return "decision"
        else:
            return "code_analysis"  # Default
    
    async def execute_task(
        self,
        task: Task,
        context: Dict[str, Any],
        automation_mode: AutomationMode = AutomationMode.SHADOW,
    ) -> AgentResult:
        """
        Execute a single task.
        
        Args:
            task: Task to execute
            context: Execution context
            automation_mode: Current automation mode
            
        Returns:
            AgentResult from execution
        """
        agent = self.get_agent_for_task(task)
        
        if not agent:
            return AgentResult(
                agent_id="none",
                task_id=task.id,
                success=False,
                error="No suitable agent found",
            )
        
        agent.automation_mode = automation_mode
        
        # Execute
        result = await agent.execute(task, context)
        
        # Record outcome for confidence tracking
        outcome = Outcome(
            task_id=task.id,
            decision_id=str(uuid.uuid4())[:8],
            outcome_type=OutcomeType.CORRECT if result.success else OutcomeType.INCORRECT,
            timestamp=datetime.utcnow(),
            ai_decision=result.result,
            risk_level=task.risk_score,
            automation_mode=automation_mode.value,
        )
        self.task_outcomes.append(outcome)
        
        return result
    
    async def execute_graph(
        self,
        graph: TaskGraph,
        context: Dict[str, Any],
        automation_mode: AutomationMode = AutomationMode.SHADOW,
        parallel: bool = True,
    ) -> Dict[str, AgentResult]:
        """
        Execute all tasks in a graph.
        
        Args:
            graph: TaskGraph to execute
            context: Shared execution context
            automation_mode: Automation mode for all tasks
            parallel: Whether to parallelize independent tasks
            
        Returns:
            Dict mapping task IDs to results
        """
        results: Dict[str, AgentResult] = {}
        execution_order = graph.get_execution_order()
        
        for level in execution_order:
            if parallel and len(level) > 1:
                # Execute level in parallel
                tasks_to_run = [graph.tasks[tid] for tid in level]
                level_results = await asyncio.gather(*[
                    self.execute_task(task, context, automation_mode)
                    for task in tasks_to_run
                ])
                
                for task_id, result in zip(level, level_results):
                    results[task_id] = result
                    
                    # Update context with result for downstream tasks
                    context[f"result_{task_id}"] = result.result
                    
                    # Mark task status
                    if result.success:
                        graph.tasks[task_id].mark_completed(result.result)
                    else:
                        graph.tasks[task_id].mark_failed(result.error or "Unknown error")
            else:
                # Execute sequentially
                for task_id in level:
                    task = graph.tasks[task_id]
                    result = await self.execute_task(task, context, automation_mode)
                    results[task_id] = result
                    
                    context[f"result_{task_id}"] = result.result
                    
                    if result.success:
                        task.mark_completed(result.result)
                    else:
                        task.mark_failed(result.error or "Unknown error")
        
        return results
    
    async def execute_with_human_review(
        self,
        task: Task,
        context: Dict[str, Any],
        human_callback: Callable[[AgentResult], bool],
    ) -> AgentResult:
        """
        Execute task with optional human review.
        
        Args:
            task: Task to execute
            context: Execution context
            human_callback: Callback for human review (returns approval)
            
        Returns:
            Final result after any human intervention
        """
        # First run AI
        result = await self.execute_task(task, context, AutomationMode.SUGGESTION)
        
        if result.requires_human_review:
            # Wait for human approval
            approved = human_callback(result)
            
            if not approved:
                # Human overrode
                outcome = Outcome(
                    task_id=task.id,
                    decision_id=str(uuid.uuid4())[:8],
                    outcome_type=OutcomeType.OVERRIDDEN,
                    timestamp=datetime.utcnow(),
                    ai_decision=result.result,
                    automation_mode=AutomationMode.SUGGESTION.value,
                )
                self.task_outcomes.append(outcome)
                
                result.metadata["human_overridden"] = True
        
        return result
    
    def get_orchestration_stats(self) -> Dict[str, Any]:
        """Get orchestration statistics."""
        total_outcomes = len(self.task_outcomes)
        successful = sum(1 for o in self.task_outcomes if o.is_success)
        failed = sum(1 for o in self.task_outcomes if o.is_failure)
        overridden = sum(
            1 for o in self.task_outcomes
            if o.outcome_type == OutcomeType.OVERRIDDEN
        )
        
        return {
            "total_agents": len(self.agents),
            "agent_types": list(self.agent_types.keys()),
            "total_executions": total_outcomes,
            "successful": successful,
            "failed": failed,
            "overridden": overridden,
            "success_rate": successful / total_outcomes if total_outcomes > 0 else 0.0,
            "agents": [agent.to_dict() for agent in self.agents.values()],
        }
