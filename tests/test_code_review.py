"""
Tests for code review module.
"""

import pytest
from datetime import datetime

from aurix.modules.code_review import (
    CodeReviewModule,
    PullRequestInfo,
    ReviewDecision,
    CodeIntent,
)


class TestCodeReviewModule:
    """Tests for CodeReviewModule."""
    
    @pytest.fixture
    def module(self):
        """Create a code review module instance."""
        return CodeReviewModule()
    
    @pytest.fixture
    def simple_pr(self):
        """Create a simple pull request."""
        return PullRequestInfo(
            pr_id="123",
            repo="test/repo",
            title="Add helper function",
            description="This PR adds a simple helper function",
            author="testuser",
            files=[
                {
                    "filename": "src/utils.py",
                    "content": """
def helper_function(x, y):
    '''Add two numbers.'''
    return x + y
""",
                    "status": "added",
                },
            ],
            additions=5,
            deletions=0,
            changed_files_count=1,
            labels=["feature"],
        )
    
    @pytest.fixture
    def security_pr(self):
        """Create a PR with security issues."""
        return PullRequestInfo(
            pr_id="456",
            repo="test/repo",
            title="Update configuration",
            description="Update the config file",
            author="testuser",
            files=[
                {
                    "filename": "config.py",
                    "content": """
password = "super_secret_password"
api_key = "sk-1234567890"
eval(user_input)
""",
                    "status": "modified",
                },
            ],
            additions=3,
            deletions=0,
            changed_files_count=1,
            labels=[],
        )
    
    @pytest.mark.asyncio
    async def test_review_simple_pr(self, module, simple_pr):
        """Test reviewing a simple pull request."""
        result = await module.review_pull_request(simple_pr)
        
        assert result.pr_info.pr_id == "123"
        assert result.decision in [
            ReviewDecision.APPROVE,
            ReviewDecision.REQUEST_CHANGES,
            ReviewDecision.NEEDS_DISCUSSION,
        ]
        assert 0 <= result.confidence <= 1
        assert result.summary != ""
    
    @pytest.mark.asyncio
    async def test_review_security_pr(self, module, security_pr):
        """Test reviewing a PR with security issues."""
        result = await module.review_pull_request(security_pr)
        
        # Should detect security issues
        security_check = result.checks.get("security", {})
        assert security_check.get("passed") is False or len(security_check.get("issues", [])) > 0
        
        # Should not auto-approve
        assert result.decision != ReviewDecision.APPROVE or result.human_review_required
    
    @pytest.mark.asyncio
    async def test_detect_intent_feature(self, module):
        """Test intent detection for feature PR."""
        pr = PullRequestInfo(
            pr_id="1",
            repo="test/repo",
            title="feat: Add new feature",
            description="Implements the new feature",
            author="user",
            files=[],
            labels=["feature"],
        )
        
        intent = module._detect_intent(pr)
        assert intent == CodeIntent.FEATURE
    
    @pytest.mark.asyncio
    async def test_detect_intent_bugfix(self, module):
        """Test intent detection for bugfix PR."""
        pr = PullRequestInfo(
            pr_id="2",
            repo="test/repo",
            title="fix: Resolve issue #123",
            description="Fixes the bug in the module",
            author="user",
            files=[],
            labels=["bug"],
        )
        
        intent = module._detect_intent(pr)
        assert intent == CodeIntent.BUGFIX
    
    @pytest.mark.asyncio
    async def test_detect_intent_hotfix(self, module):
        """Test intent detection for hotfix PR."""
        pr = PullRequestInfo(
            pr_id="3",
            repo="test/repo",
            title="HOTFIX: Critical fix for production",
            description="Emergency fix",
            author="user",
            files=[],
            labels=["hotfix"],
        )
        
        intent = module._detect_intent(pr)
        assert intent == CodeIntent.HOTFIX
    
    @pytest.mark.asyncio
    async def test_style_check(self, module):
        """Test style checking."""
        pr = PullRequestInfo(
            pr_id="4",
            repo="test/repo",
            title="Add code",
            description="",
            author="user",
            files=[
                {
                    "filename": "test.py",
                    "content": "x=1  \n" + "a" * 150 + "\n",  # trailing whitespace, long line
                },
            ],
        )
        
        result = await module._check_style(pr)
        
        assert len(result.issues) > 0
    
    def test_record_human_feedback(self, module):
        """Test recording human feedback."""
        # This would normally require a prior review
        module.record_human_feedback(
            pr_id="test-pr",
            human_decision=ReviewDecision.APPROVE,
            feedback="Looks good",
        )
        
        # Should not raise
        assert True
