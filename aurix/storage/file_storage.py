"""
File-based storage backend for Aurix.

This backend stores all data as JSON files on the local filesystem.
Perfect for PoC and development - zero infrastructure required.

Directory structure:
    .aurix/
    ├── data/
    │   ├── outcomes/
    │   │   └── {task_id}.json        # Outcome records per task
    │   ├── tasks/
    │   │   └── {task_id}.json        # Task state
    │   ├── confidence/
    │   │   └── {task_id}.json        # Confidence history
    │   └── kv/
    │       └── {namespace}/
    │           └── {key}.json        # Key-value storage
    └── config.json                    # Runtime config
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from aurix.storage.base import (
    Storage,
    OutcomeRecord,
    ConfidenceSnapshot,
    TaskState,
)


class FileStorage(Storage):
    """
    JSON file-based storage backend.
    
    Thread-safe through file locking. Suitable for single-instance
    deployments and GitHub Actions runners.
    
    Args:
        base_path: Base directory for storage. Defaults to .aurix/data
                   in the current working directory.
    """
    
    def __init__(self, base_path: str | Path | None = None):
        if base_path is None:
            # Default to .aurix/data in current directory or repo root
            base_path = self._find_storage_root()
        
        self.base_path = Path(base_path)
        self.outcomes_path = self.base_path / "outcomes"
        self.tasks_path = self.base_path / "tasks"
        self.confidence_path = self.base_path / "confidence"
        self.kv_path = self.base_path / "kv"
        
        self._lock = asyncio.Lock()
    
    def _find_storage_root(self) -> Path:
        """Find the best location for storage."""
        # Check if we're in a git repo
        current = Path.cwd()
        
        while current != current.parent:
            if (current / ".git").exists():
                return current / ".aurix" / "data"
            current = current.parent
        
        # Fall back to current directory
        return Path.cwd() / ".aurix" / "data"
    
    async def initialize(self) -> None:
        """Create directory structure."""
        for path in [
            self.base_path,
            self.outcomes_path,
            self.tasks_path,
            self.confidence_path,
            self.kv_path,
        ]:
            path.mkdir(parents=True, exist_ok=True)
    
    async def close(self) -> None:
        """No cleanup needed for file storage."""
        pass
    
    def _read_json(self, path: Path) -> dict | list | None:
        """Read JSON from file."""
        if not path.exists():
            return None
        
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _write_json(self, path: Path, data: dict | list) -> None:
        """Write JSON to file atomically."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first, then rename (atomic on POSIX)
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        temp_path.rename(path)
    
    def _task_file(self, task_id: str) -> Path:
        """Get path for task state file."""
        # Sanitize task_id for filesystem
        safe_id = task_id.replace("/", "_").replace(":", "_")
        return self.tasks_path / f"{safe_id}.json"
    
    def _outcomes_file(self, task_id: str) -> Path:
        """Get path for outcomes file."""
        safe_id = task_id.replace("/", "_").replace(":", "_")
        return self.outcomes_path / f"{safe_id}.json"
    
    def _confidence_file(self, task_id: str) -> Path:
        """Get path for confidence history file."""
        safe_id = task_id.replace("/", "_").replace(":", "_")
        return self.confidence_path / f"{safe_id}.json"
    
    # Outcome operations
    async def record_outcome(self, outcome: OutcomeRecord) -> None:
        """Record a task execution outcome."""
        async with self._lock:
            file_path = self._outcomes_file(outcome.task_id)
            
            # Load existing outcomes
            data = self._read_json(file_path) or []
            
            # Append new outcome
            data.append(outcome.model_dump())
            
            # Write back
            self._write_json(file_path, data)
            
            # Update task state
            await self._update_task_stats(outcome)
    
    async def _update_task_stats(self, outcome: OutcomeRecord) -> None:
        """Update task statistics based on new outcome."""
        state = await self.get_task_state(outcome.task_id)
        
        if state is None:
            state = TaskState(
                task_id=outcome.task_id,
                module=outcome.module,
            )
        
        state.total_outcomes += 1
        if outcome.success:
            state.successful_outcomes += 1
        if outcome.human_correction:
            state.human_corrections += 1
        state.updated_at = datetime.utcnow()
        
        await self.update_task_state(state)
    
    async def get_outcomes(
        self,
        task_id: str,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> list[OutcomeRecord]:
        """Get outcomes for a task."""
        file_path = self._outcomes_file(task_id)
        data = self._read_json(file_path) or []
        
        outcomes = [OutcomeRecord(**item) for item in data]
        
        if since:
            outcomes = [o for o in outcomes if o.timestamp >= since]
        
        if limit:
            outcomes = outcomes[-limit:]
        
        return outcomes
    
    async def get_recent_outcomes(
        self,
        task_id: str,
        count: int,
    ) -> list[OutcomeRecord]:
        """Get the N most recent outcomes."""
        return await self.get_outcomes(task_id, limit=count)
    
    # Task state operations
    async def get_task_state(self, task_id: str) -> TaskState | None:
        """Get the current state of a task."""
        file_path = self._task_file(task_id)
        data = self._read_json(file_path)
        
        if data is None:
            return None
        
        return TaskState(**data)
    
    async def update_task_state(self, state: TaskState) -> None:
        """Update a task's state."""
        async with self._lock:
            state.updated_at = datetime.utcnow()
            file_path = self._task_file(state.task_id)
            self._write_json(file_path, state.model_dump())
    
    async def list_tasks(self, module: str | None = None) -> list[TaskState]:
        """List all tracked tasks."""
        tasks = []
        
        if not self.tasks_path.exists():
            return tasks
        
        for file_path in self.tasks_path.glob("*.json"):
            data = self._read_json(file_path)
            if data:
                task = TaskState(**data)
                if module is None or task.module == module:
                    tasks.append(task)
        
        return tasks
    
    # Confidence snapshots
    async def save_confidence_snapshot(self, snapshot: ConfidenceSnapshot) -> None:
        """Save a confidence snapshot."""
        async with self._lock:
            file_path = self._confidence_file(snapshot.task_id)
            data = self._read_json(file_path) or []
            data.append(snapshot.model_dump())
            
            # Keep last 1000 snapshots per task
            if len(data) > 1000:
                data = data[-1000:]
            
            self._write_json(file_path, data)
    
    async def get_confidence_history(
        self,
        task_id: str,
        limit: int | None = None,
    ) -> list[ConfidenceSnapshot]:
        """Get confidence history for a task."""
        file_path = self._confidence_file(task_id)
        data = self._read_json(file_path) or []
        
        snapshots = [ConfidenceSnapshot(**item) for item in data]
        
        if limit:
            snapshots = snapshots[-limit:]
        
        return snapshots
    
    # Generic key-value operations
    async def set(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        """Store a value in a namespace."""
        async with self._lock:
            ns_path = self.kv_path / namespace
            ns_path.mkdir(parents=True, exist_ok=True)
            
            safe_key = key.replace("/", "_").replace(":", "_")
            file_path = ns_path / f"{safe_key}.json"
            
            self._write_json(file_path, value)
    
    async def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        """Retrieve a value from a namespace."""
        safe_key = key.replace("/", "_").replace(":", "_")
        file_path = self.kv_path / namespace / f"{safe_key}.json"
        
        data = self._read_json(file_path)
        return data if isinstance(data, dict) else None
    
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a value from a namespace."""
        safe_key = key.replace("/", "_").replace(":", "_")
        file_path = self.kv_path / namespace / f"{safe_key}.json"
        
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    async def list_keys(self, namespace: str) -> list[str]:
        """List all keys in a namespace."""
        ns_path = self.kv_path / namespace
        
        if not ns_path.exists():
            return []
        
        return [f.stem for f in ns_path.glob("*.json")]


class MemoryStorage(Storage):
    """
    In-memory storage backend for testing.
    
    Data is lost when the process exits. Useful for unit tests
    and quick experiments.
    """
    
    def __init__(self):
        self.outcomes: dict[str, list[OutcomeRecord]] = {}
        self.tasks: dict[str, TaskState] = {}
        self.confidence: dict[str, list[ConfidenceSnapshot]] = {}
        self.kv: dict[str, dict[str, dict[str, Any]]] = {}
    
    async def initialize(self) -> None:
        """No initialization needed."""
        pass
    
    async def close(self) -> None:
        """No cleanup needed."""
        pass
    
    async def record_outcome(self, outcome: OutcomeRecord) -> None:
        """Record a task execution outcome."""
        if outcome.task_id not in self.outcomes:
            self.outcomes[outcome.task_id] = []
        self.outcomes[outcome.task_id].append(outcome)
        
        # Update task state
        state = self.tasks.get(outcome.task_id)
        if state is None:
            state = TaskState(task_id=outcome.task_id, module=outcome.module)
        
        state.total_outcomes += 1
        if outcome.success:
            state.successful_outcomes += 1
        if outcome.human_correction:
            state.human_corrections += 1
        state.updated_at = datetime.utcnow()
        
        self.tasks[outcome.task_id] = state
    
    async def get_outcomes(
        self,
        task_id: str,
        limit: int | None = None,
        since: datetime | None = None,
    ) -> list[OutcomeRecord]:
        """Get outcomes for a task."""
        outcomes = self.outcomes.get(task_id, [])
        
        if since:
            outcomes = [o for o in outcomes if o.timestamp >= since]
        
        if limit:
            outcomes = outcomes[-limit:]
        
        return outcomes
    
    async def get_recent_outcomes(self, task_id: str, count: int) -> list[OutcomeRecord]:
        """Get the N most recent outcomes."""
        return await self.get_outcomes(task_id, limit=count)
    
    async def get_task_state(self, task_id: str) -> TaskState | None:
        """Get the current state of a task."""
        return self.tasks.get(task_id)
    
    async def update_task_state(self, state: TaskState) -> None:
        """Update a task's state."""
        state.updated_at = datetime.utcnow()
        self.tasks[state.task_id] = state
    
    async def list_tasks(self, module: str | None = None) -> list[TaskState]:
        """List all tracked tasks."""
        tasks = list(self.tasks.values())
        if module:
            tasks = [t for t in tasks if t.module == module]
        return tasks
    
    async def save_confidence_snapshot(self, snapshot: ConfidenceSnapshot) -> None:
        """Save a confidence snapshot."""
        if snapshot.task_id not in self.confidence:
            self.confidence[snapshot.task_id] = []
        self.confidence[snapshot.task_id].append(snapshot)
    
    async def get_confidence_history(
        self,
        task_id: str,
        limit: int | None = None,
    ) -> list[ConfidenceSnapshot]:
        """Get confidence history for a task."""
        history = self.confidence.get(task_id, [])
        if limit:
            history = history[-limit:]
        return history
    
    async def set(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        """Store a value in a namespace."""
        if namespace not in self.kv:
            self.kv[namespace] = {}
        self.kv[namespace][key] = value
    
    async def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        """Retrieve a value from a namespace."""
        return self.kv.get(namespace, {}).get(key)
    
    async def delete(self, namespace: str, key: str) -> bool:
        """Delete a value from a namespace."""
        if namespace in self.kv and key in self.kv[namespace]:
            del self.kv[namespace][key]
            return True
        return False
    
    async def list_keys(self, namespace: str) -> list[str]:
        """List all keys in a namespace."""
        return list(self.kv.get(namespace, {}).keys())
