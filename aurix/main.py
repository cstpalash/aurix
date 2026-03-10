"""
Main entry point for Aurix platform.

For GitHub Actions, use: python -m aurix.actions.run
"""

import asyncio
from aurix.core.engine import Aurix


async def demo():
    """Demo entry point for testing."""
    aurix = Aurix()
    await aurix.initialize()
    
    # Demo: run a code review
    result = await aurix.execute(
        module="code_review",
        input_data={
            "pr_id": "demo-1",
            "repo": "demo/repo",
            "title": "Demo PR",
            "description": "A demo pull request",
            "author": "demo-user",
        }
    )
    
    print(f"Decision: {result.result.decision.value}")
    print(f"Confidence: {result.confidence_score:.1%}")
    print(f"Human Review Required: {result.result.human_review_required}")
    
    await aurix.shutdown()


def main():
    """Main entry point."""
    print("Aurix - Confidence-Driven Autonomy Platform")
    print()
    print("Usage:")
    print("  GitHub Actions: python -m aurix.actions.run [code_review|sdlc]")
    print("  Demo: python -c 'import asyncio; from aurix.main import demo; asyncio.run(demo())'")
    print()


if __name__ == "__main__":
    main()
