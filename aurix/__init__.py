"""
Aurix - Autonomous Human-in-the-Loop Removal Platform

A framework for systematically removing human intervention from
agentic workflows with statistical confidence.
"""

__version__ = "0.1.0"
__author__ = "Aurix Team"

from aurix.core.risk_assessor import RiskAssessor, RiskLevel, RiskProfile
from aurix.core.confidence_engine import ConfidenceEngine, ConfidenceScore
from aurix.core.task_decomposer import TaskDecomposer, Task, TaskGraph
from aurix.core.micro_agent import MicroAgent, AgentState, AgentOrchestrator

__all__ = [
    "RiskAssessor",
    "RiskLevel", 
    "RiskProfile",
    "ConfidenceEngine",
    "ConfidenceScore",
    "TaskDecomposer",
    "Task",
    "TaskGraph",
    "MicroAgent",
    "AgentState",
    "AgentOrchestrator",
]
