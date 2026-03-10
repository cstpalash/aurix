"""
CLI commands for Aurix.
"""

import asyncio
import os
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def review_pr(repo: str, pr_number: int):
    """Review a pull request."""
    from aurix.integrations.github import GitHubIntegration
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        console.print("[red]Error: GITHUB_TOKEN environment variable not set[/red]")
        return
    
    owner, repo_name = repo.split("/")
    
    console.print(f"\n[bold]Reviewing PR #{pr_number} in {repo}[/bold]\n")
    
    integration = GitHubIntegration(token=token)
    
    try:
        with console.status("Analyzing pull request..."):
            result = await integration.review_pull_request(owner, repo_name, pr_number)
        
        # Display results
        console.print(Panel(
            f"""
[bold]Decision:[/bold] {result.decision.value.replace('_', ' ').title()}
[bold]Confidence:[/bold] {result.confidence:.0%}
[bold]Risk Level:[/bold] {result.risk_profile.risk_level.value}
[bold]Automation Mode:[/bold] {result.automation_mode.value}
[bold]Human Review Required:[/bold] {'Yes' if result.human_review_required else 'No'}
            """,
            title="Review Result",
            border_style="green" if result.decision.value == "approve" else "yellow",
        ))
        
        # Display checks
        table = Table(title="Check Results")
        table.add_column("Check", style="cyan")
        table.add_column("Passed", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Issues", justify="right")
        
        for check_type, check_data in result.checks.items():
            passed = "✅" if check_data.get("passed") else "❌"
            score = f"{check_data.get('score', 0):.0%}"
            issues = str(len(check_data.get("issues", [])))
            table.add_row(check_type, passed, score, issues)
        
        console.print(table)
        
        if result.escalation_reason:
            console.print(f"\n[yellow]Escalation Reason:[/yellow] {result.escalation_reason}")
        
    finally:
        await integration.close()


async def run_pipeline(repo: str, branch: str, environment: str):
    """Run SDLC pipeline."""
    from aurix.modules.sdlc import SDLCModule
    
    console.print(f"\n[bold]Running pipeline for {repo}[/bold]\n")
    
    sdlc = SDLCModule()
    
    config = sdlc.create_pipeline(
        repo=repo,
        name=f"cli_{repo}",
    )
    config.branch = branch
    
    with console.status("Executing pipeline..."):
        execution = await sdlc.execute_pipeline(
            config=config,
            trigger_type="cli",
            triggered_by="user",
        )
    
    # Display results
    status_color = "green" if execution.status.value == "success" else "red"
    
    console.print(Panel(
        f"""
[bold]Execution ID:[/bold] {execution.execution_id}
[bold]Status:[/bold] [{status_color}]{execution.status.value}[/{status_color}]
[bold]Duration:[/bold] {(execution.completed_at - execution.started_at).total_seconds():.1f}s
        """,
        title="Pipeline Result",
        border_style=status_color,
    ))
    
    # Display stages
    table = Table(title="Stage Results")
    table.add_column("Stage", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right")
    
    for stage_name, stage_data in execution.stages.items():
        status = stage_data.get("status", "unknown")
        status_icon = "✅" if stage_data.get("success") else "❌"
        
        started = stage_data.get("started_at")
        completed = stage_data.get("completed_at")
        if started and completed:
            from datetime import datetime
            s = datetime.fromisoformat(started)
            c = datetime.fromisoformat(completed)
            duration = f"{(c - s).total_seconds():.1f}s"
        else:
            duration = "-"
        
        table.add_row(stage_name, f"{status_icon} {status}", duration)
    
    console.print(table)


def check_status(repo: str):
    """Check graduation status."""
    from aurix.modules.code_review import CodeReviewModule
    
    console.print(f"\n[bold]Graduation Status for {repo}[/bold]\n")
    
    module = CodeReviewModule()
    status = module.get_graduation_status(repo)
    
    if not status.get("eligible"):
        console.print(Panel(
            f"[yellow]Not eligible for graduation[/yellow]\n\n{status.get('reason', 'Unknown reason')}",
            title="Status",
            border_style="yellow",
        ))
    else:
        requirements = status.get("requirements", {})
        
        table = Table(title="Requirements")
        table.add_column("Requirement", style="cyan")
        table.add_column("Required", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Met", justify="center")
        
        for req_name, req_data in requirements.items():
            required = str(req_data.get("required", "-"))
            current = str(req_data.get("current", "-"))
            met = "✅" if req_data.get("met") else "❌"
            table.add_row(req_name.replace("_", " ").title(), required, current, met)
        
        console.print(table)
        
        console.print(Panel(
            f"""
[bold]Current Mode:[/bold] {status.get('current_mode', 'unknown')}
[bold]Next Mode:[/bold] {status.get('next_mode', 'N/A')}
[bold]Eligible:[/bold] {'Yes ✅' if status.get('eligible') else 'No ❌'}
            """,
            title="Graduation Status",
            border_style="green" if status.get("eligible") else "yellow",
        ))
