#!/usr/bin/env python3
"""
Test script for AI-enhanced code review.

Usage:
    export OPENAI_API_KEY=your_key_here
    python examples/test_ai_review.py
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aurix.modules.code_review import (
    CodeReviewModule,
    PullRequestInfo,
    FileChange,
)


async def main():
    """Test AI-enhanced code review."""
    
    # Create review module
    review_module = CodeReviewModule()
    
    # Sample PR with potential issues
    pr_info = PullRequestInfo(
        pr_id="test-123",
        repo="example/test-repo",
        title="Add user authentication",
        description="Implements basic user login with password hashing",
        author="developer",
        base_branch="main",
        head_branch="feature/auth",
        changed_files_count=2,
        additions=50,
        deletions=10,
        labels=["feature", "security"],
        files=[
            {
                "filename": "auth/login.py",
                "status": "added",
                "additions": 45,
                "deletions": 0,
                "content": '''
import hashlib
import os
from typing import Optional

def hash_password(password: str) -> str:
    """Hash a password using SHA256."""
    # WARNING: This is intentionally insecure for testing
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == hashed

def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Authenticate a user."""
    # Simulate database lookup
    users = {
        "admin": hash_password("admin123"),  # Hardcoded credential
    }
    
    if username in users and verify_password(password, users[username]):
        return {"username": username, "role": "admin"}
    return None

def create_session(user: dict) -> str:
    """Create a session token."""
    import secrets
    return secrets.token_hex(32)
''',
            },
            {
                "filename": "tests/test_auth.py",
                "status": "added",
                "additions": 25,
                "deletions": 0,
                "content": '''
import pytest
from auth.login import hash_password, verify_password, authenticate_user

def test_hash_password():
    """Test password hashing."""
    hashed = hash_password("test123")
    assert len(hashed) == 64  # SHA256 hex length
    
def test_verify_password():
    """Test password verification."""
    hashed = hash_password("test123")
    assert verify_password("test123", hashed)
    assert not verify_password("wrong", hashed)
    
def test_authenticate_user():
    """Test user authentication."""
    user = authenticate_user("admin", "admin123")
    assert user is not None
    assert user["username"] == "admin"
''',
            },
        ],
    )
    
    print("=" * 60)
    print("🔍 Running AI-Enhanced Code Review")
    print("=" * 60)
    print(f"\nPR: {pr_info.title}")
    print(f"Files: {pr_info.changed_files_count}")
    print(f"Changes: +{pr_info.additions}/-{pr_info.deletions}")
    
    # Check if OpenAI API key is set
    if os.getenv("OPENAI_API_KEY"):
        print("\n✅ OPENAI_API_KEY detected - AI review enabled")
    else:
        print("\n⚠️  OPENAI_API_KEY not set - using rule-based review only")
    
    print("\nReviewing...\n")
    
    # Run review
    result = await review_module.review_pull_request(pr_info)
    
    # Print summary
    print(result.summary)
    print("\n" + "=" * 60)
    print(f"\n📊 Review Decision: {result.decision.value}")
    print(f"🎯 Confidence: {result.confidence:.0%}")
    print(f"⚠️  Human Review Required: {result.human_review_required}")
    if result.escalation_reason:
        print(f"📝 Reason: {result.escalation_reason}")
    
    # Print issue count by category
    print("\n📋 Issues by Category:")
    for check_name, check_data in result.checks.items():
        issue_count = len(check_data.get("issues", []))
        passed = "✅" if check_data.get("passed", False) else "❌"
        print(f"  {passed} {check_name}: {issue_count} issues")


if __name__ == "__main__":
    asyncio.run(main())
