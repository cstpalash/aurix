"""
GitHub Action runner for Aurix.

This module is invoked by the GitHub Action to run Aurix modules
in the context of a GitHub workflow.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

from aurix.core.engine import Aurix
from aurix.core.module import ModuleContext, ModuleRegistry
from aurix.core.confidence_engine import AutomationMode
from aurix.storage.file_storage import FileStorage

# Import modules to register them
from aurix.modules import code_review, sdlc


def get_github_event() -> dict:
    """Load the GitHub event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).exists():
        with open(event_path) as f:
            return json.load(f)
    return {}


def build_code_review_input(event: dict) -> dict:
    """Build input for code review module from PR event."""
    pr = event.get("pull_request", {})
    
    return {
        "pr_id": str(pr.get("number", "")),
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "title": pr.get("title", ""),
        "description": pr.get("body", ""),
        "author": pr.get("user", {}).get("login", ""),
        "base_branch": pr.get("base", {}).get("ref", "main"),
        "head_branch": pr.get("head", {}).get("ref", ""),
        "additions": pr.get("additions", 0),
        "deletions": pr.get("deletions", 0),
        "changed_files_count": pr.get("changed_files", 0),
        "labels": [l.get("name", "") for l in pr.get("labels", [])],
        "draft": pr.get("draft", False),
    }


def build_sdlc_input(event: dict) -> dict:
    """Build input for SDLC module from push event."""
    return {
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "branch": os.environ.get("GITHUB_REF", "").replace("refs/heads/", ""),
        "commit_sha": os.environ.get("GITHUB_SHA", ""),
        "commit_message": event.get("head_commit", {}).get("message", ""),
        "pusher": event.get("pusher", {}).get("name", ""),
    }


def set_output(name: str, value: str) -> None:
    """Set a GitHub Action output."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}")


def write_summary(content: str) -> None:
    """Write to GitHub step summary."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(content)


async def run_code_review(aurix: Aurix, event: dict) -> None:
    """Run code review analysis."""
    input_data = build_code_review_input(event)
    
    print(f"🔍 Analyzing PR #{input_data['pr_id']}: {input_data['title']}")
    
    result = await aurix.execute(
        module="code_review",
        input_data=input_data,
        context={
            "repo": input_data["repo"],
            "branch": input_data["head_branch"],
            "triggered_by": "github_action",
        },
    )
    
    # Set outputs
    set_output("decision", result.result.decision.value)
    set_output("confidence", str(round(result.confidence_score, 3)))
    set_output("automation_mode", result.automation_mode.value)
    set_output("human_review_required", str(result.result.human_review_required).lower())
    set_output("summary", result.result.summary[:500] if result.result.summary else "")
    
    # Generate summary
    summary = generate_review_summary(result)
    write_summary(summary)
    
    # Save for PR comment
    data_dir = Path(".aurix/data")
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "last_summary.md", "w") as f:
        f.write(summary)
    
    print(f"✅ Decision: {result.result.decision.value}")
    print(f"📊 Confidence: {result.confidence_score:.1%}")
    print(f"🤖 Mode: {result.automation_mode.value}")


def generate_review_summary(result) -> str:
    """Generate a Markdown summary for the review."""
    mode_emoji = {
        "shadow": "👁️",
        "suggestion": "💡",
        "auto_with_review": "🔄",
        "full_auto": "🚀",
    }
    
    decision_emoji = {
        "approve": "✅",
        "reject": "❌",
        "needs_review": "👀",
        "defer": "⏸️",
        "escalate": "⚠️",
    }
    
    dec = result.result.decision.value
    mode = result.automation_mode.value
    
    summary = f"""## 🤖 Aurix Code Review

{decision_emoji.get(dec, '❓')} **Decision**: {dec.upper()}
{mode_emoji.get(mode, '🤖')} **Automation Mode**: {mode.replace('_', ' ').title()}
📊 **Confidence**: {result.confidence_score:.1%}

### Summary
{result.result.summary or 'No summary available.'}

"""
    
    # Add risk profile if available
    if result.result.risk_profile:
        rp = result.result.risk_profile
        summary += f"""### Risk Assessment
| Dimension | Score |
|-----------|-------|
| Overall Level | {rp.overall_level.value.upper()} |
| Impact | {rp.impact:.2f} |
| Blast Radius | {rp.blast_radius:.2f} |
| Security | {rp.security:.2f} |

"""
    
    # Add checks if available
    details = result.result.details
    if "checks" in details:
        summary += "### Checks\n"
        for check_name, check_result in details["checks"].items():
            passed = check_result.get("passed", False)
            emoji = "✅" if passed else "❌"
            summary += f"- {emoji} **{check_name.title()}**"
            if check_result.get("issues"):
                summary += f" ({len(check_result['issues'])} issues)"
            summary += "\n"
        summary += "\n"
    
    # Add graduation info
    if result.can_graduate:
        summary += f"""### 🎓 Graduation Status
This task is ready to graduate to **{result.graduation_info.get('next_mode', 'next mode')}**!

"""
    
    # Human review notice
    if result.result.human_review_required:
        summary += """---
⚠️ **Human review required** for this decision.
"""
    else:
        summary += """---
🚀 **Automated decision** - no human review required.
"""
    
    summary += f"\n<sub>Aurix v0.1.0 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</sub>\n"
    
    return summary


async def run_sdlc(aurix: Aurix, event: dict) -> None:
    """Run SDLC pipeline."""
    input_data = build_sdlc_input(event)
    
    print(f"🚀 Running SDLC pipeline for {input_data['branch']}")
    
    result = await aurix.execute(
        module="sdlc",
        input_data=input_data,
        context={
            "repo": input_data["repo"],
            "branch": input_data["branch"],
            "triggered_by": "github_action",
        },
    )
    
    # Set outputs
    set_output("decision", result.result.decision.value)
    set_output("confidence", str(round(result.confidence_score, 3)))
    set_output("automation_mode", result.automation_mode.value)
    set_output("human_review_required", str(result.result.human_review_required).lower())
    
    # Generate summary
    summary = generate_sdlc_summary(result)
    write_summary(summary)
    
    print(f"✅ Pipeline: {result.result.decision.value}")
    print(f"📊 Confidence: {result.confidence_score:.1%}")


def generate_sdlc_summary(result) -> str:
    """Generate a Markdown summary for the SDLC pipeline."""
    dec = result.result.decision.value
    
    summary = f"""## 🚀 Aurix SDLC Pipeline

**Status**: {dec.upper()}
**Confidence**: {result.confidence_score:.1%}
**Automation Mode**: {result.automation_mode.value.replace('_', ' ').title()}

### Summary
{result.result.summary or 'No summary available.'}

"""
    
    # Add stage results if available
    details = result.result.details
    if "stages" in details:
        summary += "### Stage Results\n"
        for stage in details["stages"]:
            status = stage.get("status", "unknown")
            emoji = {"success": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "❓")
            summary += f"- {emoji} **{stage.get('name', 'Unknown')}**"
            if stage.get("duration"):
                summary += f" ({stage['duration']:.1f}s)"
            summary += "\n"
        summary += "\n"
    
    summary += f"\n<sub>Aurix v0.1.0 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</sub>\n"
    
    return summary


async def main():
    """Main entry point for the GitHub Action."""
    module = os.environ.get("AURIX_MODULE", "code_review")
    event = get_github_event()
    
    print(f"🤖 Aurix v0.1.0 - {module.replace('_', ' ').title()}")
    print(f"📦 Repository: {os.environ.get('GITHUB_REPOSITORY', 'unknown')}")
    print()
    
    # Initialize Aurix with file storage
    storage = FileStorage(Path(".aurix/data"))
    aurix = Aurix(storage=storage)
    await aurix.initialize()
    
    try:
        if module == "code_review":
            await run_code_review(aurix, event)
        elif module == "sdlc":
            await run_sdlc(aurix, event)
        else:
            print(f"❌ Unknown module: {module}")
            sys.exit(1)
    finally:
        await aurix.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
