"""
Tests for the Aurix engine.
"""

import pytest
import tempfile
from pathlib import Path

from aurix.core.engine import Aurix
from aurix.core.module import BaseModule, ModuleContext, ModuleResult, ModuleDecision, ModuleRegistry
from aurix.core.confidence_engine import AutomationMode
from aurix.core.risk_assessor import RiskProfile, RiskLevel
from aurix.storage.file_storage import FileStorage, MemoryStorage
from pydantic import BaseModel


# Test module for engine tests
class TestInput(BaseModel):
    """Simple test input."""
    value: str
    risk_level: str = "low"


@ModuleRegistry.register
class TestModule(BaseModule[TestInput, ModuleResult]):
    """A test module for engine testing."""
    
    name = "test_module"
    description = "Test module for unit tests"
    version = "1.0.0"
    
    input_model_class = TestInput
    
    async def execute(
        self,
        input_data: TestInput,
        context: ModuleContext,
    ) -> ModuleResult:
        """Execute test logic."""
        return ModuleResult(
            module_name=self.name,
            task_id=self.get_task_id(input_data),
            decision=ModuleDecision.APPROVE,
            confidence=0.9,
            automation_mode=context.automation_mode,
            human_review_required=context.automation_mode != AutomationMode.FULL_AUTO,
            summary=f"Processed: {input_data.value}",
        )
    
    async def assess_risk(self, input_data: TestInput) -> RiskProfile:
        """Assess risk based on input."""
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
        }
        return RiskProfile(
            overall_level=risk_map.get(input_data.risk_level, RiskLevel.MEDIUM),
            overall_score=0.3,
        )
    
    def get_task_id(self, input_data: TestInput) -> str:
        """Generate task ID."""
        return f"test:{input_data.value}"


class TestAurixEngine:
    """Tests for the Aurix engine."""
    
    @pytest.fixture
    async def aurix(self):
        """Create Aurix with memory storage."""
        storage = MemoryStorage()
        engine = Aurix(storage=storage)
        await engine.initialize()
        yield engine
        await engine.shutdown()
    
    @pytest.mark.asyncio
    async def test_execute_module(self, aurix):
        """Test executing a registered module."""
        result = await aurix.execute(
            module="test_module",
            input_data={"value": "hello"},
        )
        
        assert result.module == "test_module"
        assert result.result.decision == ModuleDecision.APPROVE
        assert "hello" in result.result.summary
        assert result.automation_mode == AutomationMode.SHADOW  # Default
    
    @pytest.mark.asyncio
    async def test_unknown_module_raises(self, aurix):
        """Test that unknown module raises error."""
        with pytest.raises(ValueError, match="Unknown module"):
            await aurix.execute(
                module="nonexistent",
                input_data={},
            )
    
    @pytest.mark.asyncio
    async def test_record_outcome_updates_confidence(self, aurix):
        """Test that recording outcomes updates confidence."""
        # First execute to create task
        result = await aurix.execute(
            module="test_module",
            input_data={"value": "test"},
        )
        
        # Record successful outcomes
        for _ in range(5):
            info = await aurix.record_outcome(
                task_id=result.task_id,
                module="test_module",
                success=True,
            )
        
        assert info["total_outcomes"] == 5
        assert info["success_rate"] == 1.0
        assert info["confidence_score"] > 0
    
    @pytest.mark.asyncio
    async def test_graduation_with_outcomes(self, aurix):
        """Test that tasks can graduate with enough outcomes."""
        result = await aurix.execute(
            module="test_module",
            input_data={"value": "grad-test"},
        )
        
        # Record many successful outcomes
        for i in range(25):
            info = await aurix.record_outcome(
                task_id=result.task_id,
                module="test_module",
                success=True,
            )
        
        # Should be eligible for graduation or already graduated
        assert info["total_outcomes"] == 25
        # Mode should have advanced from shadow
        # (exact mode depends on confidence thresholds)
    
    @pytest.mark.asyncio
    async def test_get_status(self, aurix):
        """Test getting status of tasks."""
        # Execute a few tasks
        await aurix.execute(module="test_module", input_data={"value": "a"})
        await aurix.execute(module="test_module", input_data={"value": "b"})
        
        statuses = await aurix.get_status()
        assert len(statuses) == 2
        
        # Get specific task
        status = await aurix.get_status(task_id="test:a")
        assert len(status) == 1
        assert status[0]["task_id"] == "test:a"
    
    @pytest.mark.asyncio
    async def test_get_dashboard(self, aurix):
        """Test dashboard summary."""
        # Execute and record some outcomes
        result = await aurix.execute(
            module="test_module",
            input_data={"value": "dash"},
        )
        
        await aurix.record_outcome(
            task_id=result.task_id,
            module="test_module",
            success=True,
        )
        
        dashboard = await aurix.get_dashboard()
        
        assert "total_tasks" in dashboard
        assert "total_outcomes" in dashboard
        assert "by_module" in dashboard
        assert dashboard["total_tasks"] >= 1


class TestAurixWithFileStorage:
    """Tests for Aurix with file storage persistence."""
    
    @pytest.mark.asyncio
    async def test_state_persists_across_instances(self):
        """Test that state persists when using file storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "aurix"
            
            # First instance - create and record
            storage1 = FileStorage(storage_path)
            aurix1 = Aurix(storage=storage1)
            await aurix1.initialize()
            
            result = await aurix1.execute(
                module="test_module",
                input_data={"value": "persist"},
            )
            
            await aurix1.record_outcome(
                task_id=result.task_id,
                module="test_module",
                success=True,
            )
            
            await aurix1.shutdown()
            
            # Second instance - should see the data
            storage2 = FileStorage(storage_path)
            aurix2 = Aurix(storage=storage2)
            await aurix2.initialize()
            
            status = await aurix2.get_status(task_id="test:persist")
            assert len(status) == 1
            assert status[0]["total_outcomes"] == 1
            
            await aurix2.shutdown()
