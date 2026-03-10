"""
Aurix - Confidence-Driven Autonomy Platform

A framework for systematically removing human intervention from
agentic workflows with statistical confidence.
"""

__version__ = "0.1.0"
__author__ = "Aurix Team"

from aurix.core.risk_assessor import RiskAssessor, RiskLevel, RiskProfile
from aurix.core.confidence_engine import ConfidenceEngine, ConfidenceScore

__all__ = [
    "RiskAssessor",
    "RiskLevel", 
    "RiskProfile",
    "ConfidenceEngine",
    "ConfidenceScore",
]
