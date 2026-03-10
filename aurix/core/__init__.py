"""
Core module initialization for Aurix platform.
"""

from aurix.core.risk_assessor import RiskAssessor, RiskLevel, RiskProfile
from aurix.core.confidence_engine import ConfidenceEngine, ConfidenceScore, AutomationMode
from aurix.core.task_decomposer import TaskDecomposer, Task, TaskGraph
from aurix.core.micro_agent import MicroAgent, AgentState, AgentOrchestrator
from aurix.core.module import BaseModule, ModuleContext, ModuleResult, ModuleRegistry
from aurix.core.engine import Aurix, get_aurix

__all__ = [
    # Risk Assessment
    "RiskAssessor",
    "RiskLevel",
    "RiskProfile",
    # Confidence
    "ConfidenceEngine",
    "ConfidenceScore",
    "AutomationMode",
    # Task Management
    "TaskDecomposer",
    "Task",
    "TaskGraph",
    # Agents
    "MicroAgent",
    "AgentState",
    "AgentOrchestrator",
    # Module System
    "BaseModule",
    "ModuleContext",
    "ModuleResult",
    "ModuleRegistry",
    # Engine
    "Aurix",
    "get_aurix",
]
