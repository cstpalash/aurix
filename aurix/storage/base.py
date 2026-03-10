"""
Abstract storage interface for Aurix.

This module defines the storage interface that all backends must implement.
The design allows swapping between file-based storage (PoC) and database
storage (production) without changing application code.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field


T = TypeVar("T", bound=BaseModel)


class StorageBackend(str, Enum):
    """Available storage backends."""
    
    FILE = "file"
    MEMORY = "memory"
    # Future: SQLITE = "sqlite", POSTGRESQL = "postgresql"


class OutcomeRecord(BaseModel):
    """Record of a task execution outcome."""
    
    id: str
    task_id: str
    module: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool
    human_correction: bool = False
    error_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConfidenceSnapshot(BaseModel):
    """Point-in-time confidence snapshot for a task."""
    
    task_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float
    success_rate: float
    total_outcomes: int
    current_mode: str
    can_graduate: bool


class TaskState(BaseModel):
    """Current state of a tracked task."""
    
    task_id: str
    module: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    current_mode: str = "shadow"
    total_outcomes: int = 0
    successful_outcomes: int = 0
    human_corrections: int = 0
    last_confidence_score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Storage(ABC):
    """
    Abstract storage interface.
    
    All storage backends must implement this interface to ensure
    consistent behavior across file-based and database storage.
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the storage backend."""
        pass
    
    # Outcome operations
    @abstractmethod
    async def record_outcome(self, outcome: OutcomeRecord) -> None:
        """Record a task execution outcome."""
        pass
    
    @abstractmethod
    async def get_outcomes(
        self,
        task_id: str,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> list[OutcomeRecord]:
        """Get outcomes for a task."""
        pass
    
    @abstractmethod
    async def get_recent_outcomes(
        self,
        task_id: str,
        count: int,
    ) -> list[OutcomeRecord]:
        """Get the N most recent outcomes for a task."""
        pass
    
    # Task state operations
    @abstractmethod
    async def get_task_state(self, task_id: str) -> TaskState | None:
        """Get the current state of a task."""
        pass
    
    @abstractmethod
    async def update_task_state(self, state: TaskState) -> None:
        """Update a task's state."""
        pass
    
    @abstractmethod
    async def list_tasks(self, module: str | None = None) -> list[TaskState]:
        """List all tracked tasks, optionally filtered by module."""
        pass
    
    # Confidence snapshots
    @abstractmethod
    async def save_confidence_snapshot(self, snapshot: ConfidenceSnapshot) -> None:
        """Save a confidence snapshot for historical tracking."""
        pass
    
    @abstractmethod
    async def get_confidence_history(
        self,
        task_id: str,
        limit: int | None = None,
    ) -> list[ConfidenceSnapshot]:
        """Get confidence history for a task."""
        pass
    
    # Generic key-value operations (for module-specific data)
    @abstractmethod
    async def set(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        """Store a value in a namespace."""
        pass
    
    @abstractmethod
    async def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        """Retrieve a value from a namespace."""
        pass
    
    @abstractmethod
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a value from a namespace."""
        pass
    
    @abstractmethod
    async def list_keys(self, namespace: str) -> list[str]:
        """List all keys in a namespace."""
        pass
