#!/usr/bin/env python3
"""
Test the AI-enhanced code review pipeline.

This tests that:
1. AI intent detection works (or falls back to heuristics)
2. AI semantic risk detection works (or falls back to heuristics)
3. The enhanced summary includes new AI sections
"""

import asyncio
from aurix.modules.code_review import CodeReviewModule, PullRequestInfo


async def test_ai_enhanced_review():
    """Test the AI-enhanced review pipeline."""
    print("=" * 60)
    print("Testing AI-Enhanced Code Review Pipeline")
    print("=" * 60)
    print()
    
    module = CodeReviewModule()
    
    # Test PR with authentication code
    pr = PullRequestInfo(
        pr_id='test-auth-123',
        repo='test/repo',
        title='Add user authentication',
        description='This PR adds login/logout functionality with JWT tokens.',
        author='developer',
        base_branch='main',
        head_branch='feature/auth',
        changed_files_count=2,
        additions=150,
        deletions=20,
        files=[
            {
                'filename': 'src/auth/login.py',
                'content': '''import jwt
from datetime import datetime, timedelta

SECRET_KEY = "my-secret-key"  # Should be env var

def login(username, password):
    """Authenticate user and return JWT token."""
    # Hash password and check database
    user = db.users.find_one({"username": username})
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    
    # Generate JWT token
    token = jwt.encode({
        "sub": user["id"],
        "exp": datetime.utcnow() + timedelta(hours=24)
    }, SECRET_KEY, algorithm="HS256")
    
    return {"token": token, "user_id": user["id"]}

def logout(user_id):
    """Invalidate user session."""
    # Delete from session store
    session_store.delete(user_id)
    return True
'''
            },
            {
                'filename': 'src/auth/middleware.py',
                'content': '''import jwt

def authenticate(request):
    """Middleware to verify JWT token."""
    token = request.headers.get("Authorization")
    if not token:
        raise UnauthorizedError("No token provided")
    
    # Remove "Bearer " prefix
    if token.startswith("Bearer "):
        token = token[7:]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        request.user_id = payload["sub"]
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")
'''
            }
        ],
        labels=['feature', 'security']
    )
    
    print("PR: Add user authentication")
    print("-" * 40)
    
    result = await module.review_pull_request(pr)
    
    print(f"Decision: {result.decision.value}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Risk Level: {result.risk_profile.risk_level.value}")
    print(f"Risk Score: {result.risk_profile.overall_risk_score:.2f}")
    print(f"Intent: {pr.detected_intent.value if pr.detected_intent else 'Unknown'}")
    print()
    
    # Check for AI enhancement markers
    if "🤖" in result.summary:
        print("✅ AI-Enhanced review detected!")
    else:
        print("⚠️  Fallback to heuristic review (AI not available)")
    
    if "AI Intent Analysis" in result.summary:
        print("✅ AI Intent Analysis section present")
    else:
        print("ℹ️  AI Intent Analysis not available (using heuristics)")
    
    if "AI Semantic Risk Analysis" in result.summary:
        print("✅ AI Semantic Risk Analysis section present")
    else:
        print("ℹ️  AI Semantic Risk not available (using heuristics)")
    
    # Check risk factors
    print()
    print("Risk Factors Detected:")
    for factor in result.risk_profile.factors:
        if hasattr(factor, 'factor_name'):
            print(f"  - {factor.factor_name}: {factor.description[:60]}...")
        else:
            print(f"  - {factor}")
    
    print()
    print("=" * 60)
    print("FULL SUMMARY")
    print("=" * 60)
    print(result.summary)
    
    return result


async def test_simple_pr():
    """Test a simple low-risk PR."""
    print()
    print("=" * 60)
    print("Testing Simple Documentation PR")
    print("=" * 60)
    print()
    
    module = CodeReviewModule()
    
    pr = PullRequestInfo(
        pr_id='test-docs-456',
        repo='test/repo',
        title='Update README with installation instructions',
        description='Adds clearer installation steps for new users.',
        author='developer',
        base_branch='main',
        head_branch='docs/readme',
        changed_files_count=1,
        additions=30,
        deletions=5,
        files=[
            {
                'filename': 'README.md',
                'content': '''# My Project

## Installation

To install this project:

1. Clone the repository
2. Run `pip install -r requirements.txt`
3. Configure your environment
4. Run `python main.py`

## Usage

See the documentation for more details.
'''
            }
        ],
        labels=['documentation']
    )
    
    print("PR: Update README")
    print("-" * 40)
    
    result = await module.review_pull_request(pr)
    
    print(f"Decision: {result.decision.value}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Risk Level: {result.risk_profile.risk_level.value}")
    print(f"Risk Score: {result.risk_profile.overall_risk_score:.2f}")
    print(f"Intent: {pr.detected_intent.value if pr.detected_intent else 'Unknown'}")
    
    return result


async def main():
    """Run all tests."""
    try:
        await test_ai_enhanced_review()
        await test_simple_pr()
        print()
        print("=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
