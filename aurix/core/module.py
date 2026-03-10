"""
Generic module interface for Aurix.

This module defines the abstract base class that all Aurix modules
must implement. The design is generic enough to support any workflow
type while code_review and sdlc are just specific implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

from aurix.core.risk_assessor import RiskProfile, RiskLevel
from aurix.core.confidence_engine import AutomationMode


# Generic input/output types for modules
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ModuleDecision(str, Enum):
    """Standard decision types for any module."""
    
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"
    DEFER = "defer"
    ESCALATE = "escalate"


class ModuleResult(BaseModel):
    """
    Standard result from any module execution.
    
    All modules return this structure to ensure consistent
    handling by the framework.
    """
    
    module_name: str
    task_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Decision and confidence
    decision: ModuleDecision
    confidence: float = Field(ge=0.0, le=1.0)
    
    # Risk assessment
    risk_profile: RiskProfile | None = None
    
    # Automation mode used
    automation_mode: AutomationMode = AutomationMode.SHADOW
    
    # Whether human review is required
    human_review_required: bool = True
    
    # Module-specific output
    details: dict[str, Any] = Field(default_factory=dict)
    
    # Summary for humans
    summary: str = ""
    
    # Actionable items
    actions: list[dict[str, Any]] = Field(default_factory=list)
    
    # Errors/warnings encountered
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ModuleContext(BaseModel):
    """
    Context passed to module execution.
    
    Contains information about the environment, configuration,
    and current automation state.
    """
    
    # Repository/project context
    repo: str | None = None
    branch: str | None = None
    
    # Current automation mode for this module
    automation_mode: AutomationMode = AutomationMode.SHADOW
    
    # Risk tolerance
    max_risk_level: RiskLevel = RiskLevel.MEDIUM
    
    # Configuration overrides
    config: dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    triggered_by: str = "manual"
    correlation_id: str | None = None


class BaseModule(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for all Aurix modules.
    
    Modules are the primary extension point for Aurix. Each module
    handles a specific type of workflow (code review, SDLC, etc.)
    but follows a consistent interface.
    
    Type Parameters:
        InputT: The input model for this module (e.g., PullRequestInfo)
        OutputT: The output model for this module (e.g., ReviewResult)
    """
    
    # Module metadata - override in subclasses
    name: str = "base"
    description: str = "Base module"
    version: str = "1.0.0"
    
    # Supported automation modes
    supported_modes: list[AutomationMode] = [
        AutomationMode.SHADOW,
        AutomationMode.SUGGESTION,
        AutomationMode.AUTO_WITH_REVIEW,
        AutomationMode.FULL_AUTO,
    ]
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self) -> None:
        """
        Initialize the module.
        
        Called once when the module is loaded. Override to set up
        connections, load models, etc.
        """
        self._initialized = True
    
    async def shutdown(self) -> None:
        """
        Shutdown the module.
        
        Called when the module is unloaded. Override to clean up
        resources.
        """
        self._initialized = False
    
    @abstractmethod
    async def execute(
        self,
        input_data: InputT,
        context: ModuleContext,
    ) -> ModuleResult:
        """
        Execute the module's main logic.
        
        This is the core method that each module must implement.
        It receives typed input data and returns a standardized result.
        
        Args:
            input_data: The module-specific input data
            context: Execution context with mode, config, etc.
        
        Returns:
            ModuleResult with decision, confidence, and details
        """
        pass
    
    @abstractmethod
    async def assess_risk(self, input_data: InputT) -> RiskProfile:
        """
        Assess the risk of automating this input.
        
        Each module must implement risk assessment based on its
        domain knowledge.
        
        Args:
            input_data: The input to assess
        
        Returns:
            RiskProfile with scored dimensions
        """
        pass
    
    @abstractmethod
    def get_task_id(self, input_data: InputT) -> str:
        """
        Generate a unique task ID for tracking.
        
        This ID is used to track outcomes and confidence for
        similar inputs over time.
        
        Args:
            input_data: The input to generate ID for
        
        Returns:
            Unique task identifier string
        """
        pass
    
    async def validate_input(self, input_data: InputT) -> list[str]:
        """
        Validate input data before execution.
        
        Override to add module-specific validation.
        
        Args:
            input_data: The input to validate
        
        Returns:
            List of validation errors (empty if valid)
        """
        return []
    
    async def pre_execute(
        self,
        input_data: InputT,
        context: ModuleContext,
    ) -> None:
        """
        Hook called before execute().
        
        Override for pre-processing, logging, etc.
        """
        pass
    
    async def post_execute(
        self,
        input_data: InputT,
        result: ModuleResult,
        context: ModuleContext,
    ) -> ModuleResult:
        """
        Hook called after execute().
        
        Override for post-processing, enrichment, etc.
        Can modify the result before it's returned.
        """
        return result
    
    async def run(
        self,
        input_data: InputT,
        context: ModuleContext | None = None,
    ) -> ModuleResult:
        """
        Run the module with full lifecycle.
        
        This is the main entry point that orchestrates validation,
        execution, and hooks.
        
        Args:
            input_data: The module-specific input
            context: Execution context (optional)
        
        Returns:
            ModuleResult with decision and details
        """
        if context is None:
            context = ModuleContext()
        
        # Validate input
        errors = await self.validate_input(input_data)
        if errors:
            return ModuleResult(
                module_name=self.name,
                task_id=self.get_task_id(input_data),
                decision=ModuleDecision.DEFER,
                confidence=0.0,
                human_review_required=True,
                errors=errors,
                summary=f"Validation failed: {', '.join(errors)}",
            )
        
        # Pre-execution hook
        await self.pre_execute(input_data, context)
        
        # Assess risk
        risk_profile = await self.assess_risk(input_data)
        
        # Check if automation is allowed for this risk level
        if risk_profile.overall_level.value > context.max_risk_level.value:
            return ModuleResult(
                module_name=self.name,
                task_id=self.get_task_id(input_data),
                decision=ModuleDecision.ESCALATE,
                confidence=0.0,
                risk_profile=risk_profile,
                automation_mode=context.automation_mode,
                human_review_required=True,
                summary=f"Risk level {risk_profile.overall_level.value} exceeds threshold",
            )
        
        # Execute main logic
        result = await self.execute(input_data, context)
        
        # Enrich result with risk profile if not set
        if result.risk_profile is None:
            result.risk_profile = risk_profile
        
        # Post-execution hook
        result = await self.post_execute(input_data, result, context)
        
        return result


class ModuleRegistry:
    """
    Registry for available modules.
    
    Modules register themselves here to be discoverable by the framework.
    """
    
    _modules: dict[str, type[BaseModule]] = {}
    _instances: dict[str, BaseModule] = {}
    
    @classmethod
    def register(cls, module_class: type[BaseModule]) -> type[BaseModule]:
        """
        Register a module class.
        
        Can be used as a decorator:
        
            @ModuleRegistry.register
            class MyModule(BaseModule):
                ...
        """
        cls._modules[module_class.name] = module_class
        return module_class
    
    @classmethod
    def get(cls, name: str) -> BaseModule | None:
        """Get or create a module instance by name."""
        if name not in cls._instances:
            module_class = cls._modules.get(name)
            if module_class is None:
                return None
            cls._instances[name] = module_class()
        
        return cls._instances[name]
    
    @classmethod
    def list_modules(cls) -> list[str]:
        """List all registered module names."""
        return list(cls._modules.keys())
    
    @classmethod
    def get_info(cls, name: str) -> dict[str, Any] | None:
        """Get metadata about a module."""
        module_class = cls._modules.get(name)
        if module_class is None:
            return None
        
        return {
            "name": module_class.name,
            "description": module_class.description,
            "version": module_class.version,
            "supported_modes": [m.value for m in module_class.supported_modes],
        }
