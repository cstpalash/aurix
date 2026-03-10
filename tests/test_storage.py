"""
Tests for file-based storage backend.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from aurix.storage.file_storage import FileStorage, MemoryStorage
from aurix.storage.base import OutcomeRecord, TaskState, ConfidenceSnapshot


class TestFileStorage:
    """Tests for FileStorage backend."""
    
    @pytest.fixture
    async def storage(self):
        """Create a temporary file storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(Path(tmpdir) / "aurix")
            await storage.initialize()
            yield storage
            await storage.close()
    
    @pytest.mark.asyncio
    async def test_initialize_creates_directories(self, storage):
        """Test that initialization creates directory structure."""
        assert storage.base_path.exists()
        assert storage.outcomes_path.exists()
        assert storage.tasks_path.exists()
        assert storage.confidence_path.exists()
    
    @pytest.mark.asyncio
    async def test_record_and_get_outcome(self, storage):
        """Test recording and retrieving outcomes."""
        outcome = OutcomeRecord(
            id="test-1",
            task_id="code_review:test/repo",
            module="code_review",
            success=True,
            human_correction=False,
        )
        
        await storage.record_outcome(outcome)
        
        outcomes = await storage.get_outcomes("code_review:test/repo")
        assert len(outcomes) == 1
        assert outcomes[0].id == "test-1"
        assert outcomes[0].success is True
    
    @pytest.mark.asyncio
    async def test_get_recent_outcomes(self, storage):
        """Test getting recent outcomes with limit."""
        for i in range(10):
            await storage.record_outcome(OutcomeRecord(
                id=f"test-{i}",
                task_id="task-1",
                module="test",
                success=i % 2 == 0,
            ))
        
        recent = await storage.get_recent_outcomes("task-1", count=3)
        assert len(recent) == 3
        # Should be the last 3
        assert recent[0].id == "test-7"
        assert recent[2].id == "test-9"
    
    @pytest.mark.asyncio
    async def test_task_state_lifecycle(self, storage):
        """Test task state create/update/get."""
        # Initially no state
        state = await storage.get_task_state("new-task")
        assert state is None
        
        # Record outcome creates state
        await storage.record_outcome(OutcomeRecord(
            id="o-1",
            task_id="new-task",
            module="test",
            success=True,
        ))
        
        state = await storage.get_task_state("new-task")
        assert state is not None
        assert state.task_id == "new-task"
        assert state.total_outcomes == 1
        assert state.successful_outcomes == 1
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, storage):
        """Test listing all tasks."""
        # Create tasks in different modules
        for module in ["code_review", "sdlc"]:
            await storage.record_outcome(OutcomeRecord(
                id=f"o-{module}",
                task_id=f"{module}:task",
                module=module,
                success=True,
            ))
        
        all_tasks = await storage.list_tasks()
        assert len(all_tasks) == 2
        
        cr_tasks = await storage.list_tasks(module="code_review")
        assert len(cr_tasks) == 1
        assert cr_tasks[0].module == "code_review"
    
    @pytest.mark.asyncio
    async def test_confidence_snapshots(self, storage):
        """Test saving and retrieving confidence snapshots."""
        for i in range(5):
            await storage.save_confidence_snapshot(ConfidenceSnapshot(
                task_id="task-1",
                confidence_score=0.5 + i * 0.1,
                success_rate=0.8,
                total_outcomes=10 + i,
                current_mode="shadow",
                can_graduate=i > 3,
            ))
        
        history = await storage.get_confidence_history("task-1")
        assert len(history) == 5
        assert history[-1].confidence_score == pytest.approx(0.9, 0.01)
        
        # Test with limit
        recent = await storage.get_confidence_history("task-1", limit=2)
        assert len(recent) == 2
    
    @pytest.mark.asyncio
    async def test_key_value_operations(self, storage):
        """Test generic key-value storage."""
        await storage.set("reviews", "pr-123", {"status": "approved", "score": 0.95})
        
        value = await storage.get("reviews", "pr-123")
        assert value is not None
        assert value["status"] == "approved"
        
        # List keys
        keys = await storage.list_keys("reviews")
        assert "pr-123" in keys
        
        # Delete
        deleted = await storage.delete("reviews", "pr-123")
        assert deleted is True
        
        value = await storage.get("reviews", "pr-123")
        assert value is None


class TestMemoryStorage:
    """Tests for MemoryStorage backend."""
    
    @pytest.fixture
    async def storage(self):
        """Create a memory storage."""
        storage = MemoryStorage()
        await storage.initialize()
        yield storage
        await storage.close()
    
    @pytest.mark.asyncio
    async def test_record_and_get_outcome(self, storage):
        """Test basic outcome recording in memory."""
        outcome = OutcomeRecord(
            id="mem-1",
            task_id="task-1",
            module="test",
            success=True,
        )
        
        await storage.record_outcome(outcome)
        
        outcomes = await storage.get_outcomes("task-1")
        assert len(outcomes) == 1
        assert outcomes[0].success is True
    
    @pytest.mark.asyncio
    async def test_memory_isolated(self):
        """Test that memory storage is isolated per instance."""
        storage1 = MemoryStorage()
        storage2 = MemoryStorage()
        
        await storage1.record_outcome(OutcomeRecord(
            id="1",
            task_id="task",
            module="test",
            success=True,
        ))
        
        outcomes1 = await storage1.get_outcomes("task")
        outcomes2 = await storage2.get_outcomes("task")
        
        assert len(outcomes1) == 1
        assert len(outcomes2) == 0
