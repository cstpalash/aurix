"""
GitHub Integration Layer for Aurix Platform

Provides integration with GitHub API and GitHub Actions
for code review, auto-merge, and SDLC automation.
"""

from __future__ import annotations

import asyncio
import hmac
import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from aurix.modules.code_review import (
    CodeReviewModule,
    PullRequestInfo,
    ReviewResult,
    ReviewDecision,
    ReviewCheckType,
    ReviewCheck,
)
from aurix.modules.sdlc import SDLCModule, PipelineConfig
from aurix.models.review_action import (
    ReviewAction,
    ReviewActionResult,
    HumanReviewRequest,
)
from aurix.config.team_config import TeamConfig, load_team_config


class GitHubEventType(str, Enum):
    """GitHub webhook event types."""
    
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_REVIEW = "pull_request_review"
    PUSH = "push"
    CHECK_RUN = "check_run"
    CHECK_SUITE = "check_suite"
    WORKFLOW_RUN = "workflow_run"
    ISSUE_COMMENT = "issue_comment"
    STATUS = "status"
    CREATE = "create"
    DELETE = "delete"


class GitHubPRAction(str, Enum):
    """Pull request actions."""
    
    OPENED = "opened"
    CLOSED = "closed"
    REOPENED = "reopened"
    SYNCHRONIZE = "synchronize"
    EDITED = "edited"
    READY_FOR_REVIEW = "ready_for_review"
    CONVERTED_TO_DRAFT = "converted_to_draft"


@dataclass
class GitHubAuth:
    """GitHub authentication configuration."""
    
    token: Optional[str] = None
    app_id: Optional[str] = None
    installation_id: Optional[str] = None
    private_key: Optional[str] = None
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        if self.token:
            return {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
            }
        return {"Accept": "application/vnd.github.v3+json"}


class GitHubClient:
    """
    Async GitHub API client.
    
    Handles all GitHub API interactions for Aurix.
    """
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, auth: GitHubAuth):
        """Initialize GitHub client."""
        self.auth = auth
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=self.auth.headers,
                timeout=30.0,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # Repository Operations
    
    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information."""
        client = await self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}")
        response.raise_for_status()
        return response.json()
    
    async def get_branches(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get repository branches."""
        client = await self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}/branches")
        response.raise_for_status()
        return response.json()
    
    # Pull Request Operations
    
    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        """Get pull request details."""
        client = await self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        response.raise_for_status()
        return response.json()
    
    async def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> List[Dict[str, Any]]:
        """Get files changed in a pull request."""
        client = await self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
        response.raise_for_status()
        return response.json()
    
    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main",
    ) -> str:
        """Get file content from repository."""
        client = await self._get_client()
        response = await client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            params={"ref": ref},
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get("encoding") == "base64":
            import base64
            return base64.b64decode(data["content"]).decode("utf-8")
        
        return data.get("content", "")
    
    async def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        event: str,  # APPROVE, REQUEST_CHANGES, COMMENT
        body: str,
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a review on a pull request."""
        client = await self._get_client()
        
        data = {
            "event": event,
            "body": body,
        }
        
        if comments:
            data["comments"] = comments
        
        response = await client.post(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    async def create_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """Create a comment on an issue or PR."""
        client = await self._get_client()
        response = await client.post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        response.raise_for_status()
        return response.json()
    
    async def add_labels(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        labels: List[str],
    ) -> List[Dict[str, Any]]:
        """Add labels to an issue or PR."""
        client = await self._get_client()
        response = await client.post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/labels",
            json={"labels": labels},
        )
        response.raise_for_status()
        return response.json()
    
    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        merge_method: str = "squash",  # merge, squash, rebase
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Merge a pull request."""
        client = await self._get_client()
        
        data = {"merge_method": merge_method}
        if commit_title:
            data["commit_title"] = commit_title
        if commit_message:
            data["commit_message"] = commit_message
        
        response = await client.put(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    # Check Runs & Status
    
    async def create_check_run(
        self,
        owner: str,
        repo: str,
        name: str,
        head_sha: str,
        status: str = "in_progress",
        conclusion: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a check run."""
        client = await self._get_client()
        
        data = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
        }
        
        if conclusion:
            data["conclusion"] = conclusion
        if output:
            data["output"] = output
        
        response = await client.post(
            f"/repos/{owner}/{repo}/check-runs",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    async def update_check_run(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
        status: Optional[str] = None,
        conclusion: Optional[str] = None,
        output: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update a check run."""
        client = await self._get_client()
        
        data = {}
        if status:
            data["status"] = status
        if conclusion:
            data["conclusion"] = conclusion
        if output:
            data["output"] = output
        
        response = await client.patch(
            f"/repos/{owner}/{repo}/check-runs/{check_run_id}",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    async def create_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,  # error, failure, pending, success
        context: str,
        description: Optional[str] = None,
        target_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a commit status."""
        client = await self._get_client()
        
        data = {
            "state": state,
            "context": context,
        }
        if description:
            data["description"] = description
        if target_url:
            data["target_url"] = target_url
        
        response = await client.post(
            f"/repos/{owner}/{repo}/statuses/{sha}",
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    # Workflow Operations
    
    async def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Trigger a workflow dispatch event."""
        client = await self._get_client()
        
        data = {"ref": ref}
        if inputs:
            data["inputs"] = inputs
        
        response = await client.post(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
            json=data,
        )
        response.raise_for_status()
        return {"triggered": True}
    
    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: Optional[str] = None,
        branch: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get workflow runs."""
        client = await self._get_client()
        
        params = {}
        if branch:
            params["branch"] = branch
        if status:
            params["status"] = status
        
        if workflow_id:
            url = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        else:
            url = f"/repos/{owner}/{repo}/actions/runs"
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json().get("workflow_runs", [])


class GitHubWebhookHandler:
    """
    Handles GitHub webhook events.
    
    Routes events to appropriate handlers in Aurix.
    """
    
    def __init__(
        self,
        client: GitHubClient,
        code_review_module: CodeReviewModule,
        sdlc_module: SDLCModule,
        webhook_secret: Optional[str] = None,
    ):
        """Initialize webhook handler."""
        self.client = client
        self.code_review = code_review_module
        self.sdlc = sdlc_module
        self.webhook_secret = webhook_secret
        
        # Event handlers
        self._handlers: Dict[str, Callable] = {
            GitHubEventType.PULL_REQUEST.value: self._handle_pull_request,
            GitHubEventType.PUSH.value: self._handle_push,
            GitHubEventType.WORKFLOW_RUN.value: self._handle_workflow_run,
            GitHubEventType.CHECK_RUN.value: self._handle_check_run,
        }
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify webhook signature."""
        if not self.webhook_secret:
            return True  # No secret configured
        
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    async def handle_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle a webhook event.
        
        Args:
            event_type: GitHub event type
            payload: Event payload
            
        Returns:
            Handler result
        """
        handler = self._handlers.get(event_type)
        
        if handler:
            return await handler(payload)
        
        return {"handled": False, "reason": f"Unknown event type: {event_type}"}
    
    async def _handle_pull_request(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle pull request events."""
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        repo_data = payload.get("repository", {})
        
        # Only handle relevant actions
        if action not in [
            GitHubPRAction.OPENED.value,
            GitHubPRAction.SYNCHRONIZE.value,
            GitHubPRAction.READY_FOR_REVIEW.value,
        ]:
            return {"handled": False, "reason": f"Ignoring action: {action}"}
        
        # Skip draft PRs
        if pr_data.get("draft", False):
            return {"handled": False, "reason": "Draft PR"}
        
        # Extract repository info
        owner = repo_data.get("owner", {}).get("login", "")
        repo = repo_data.get("name", "")
        pr_number = pr_data.get("number")
        
        # Get full PR details
        pr_files = await self.client.get_pull_request_files(owner, repo, pr_number)
        
        # Fetch file contents for changed files
        files_with_content = []
        head_sha = pr_data.get("head", {}).get("sha", "")
        
        for file_info in pr_files[:20]:  # Limit to 20 files
            filename = file_info.get("filename", "")
            if file_info.get("status") != "removed":
                try:
                    content = await self.client.get_file_content(
                        owner, repo, filename, ref=head_sha
                    )
                except:
                    content = ""
                
                files_with_content.append({
                    **file_info,
                    "content": content,
                })
            else:
                files_with_content.append(file_info)
        
        # Build PR info for review
        pr_info = PullRequestInfo(
            pr_id=str(pr_number),
            repo=f"{owner}/{repo}",
            title=pr_data.get("title", ""),
            description=pr_data.get("body", "") or "",
            author=pr_data.get("user", {}).get("login", ""),
            files=files_with_content,
            additions=pr_data.get("additions", 0),
            deletions=pr_data.get("deletions", 0),
            changed_files_count=pr_data.get("changed_files", 0),
            labels=[l.get("name", "") for l in pr_data.get("labels", [])],
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            head_branch=pr_data.get("head", {}).get("ref", ""),
        )
        
        # Perform automated review
        review_result = await self.code_review.review_pull_request(
            pr_info,
            context={"head_sha": head_sha},
        )
        
        # Post review to GitHub
        await self._post_review(owner, repo, pr_number, head_sha, review_result)
        
        return {
            "handled": True,
            "action": action,
            "pr_number": pr_number,
            "decision": review_result.decision.value,
            "confidence": review_result.confidence,
            "human_review_required": review_result.human_review_required,
        }
    
    async def _post_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        review_result: ReviewResult,
    ) -> None:
        """Post review results to GitHub."""
        # Create check run
        check_output = {
            "title": f"Aurix Code Review - {review_result.decision.value.title()}",
            "summary": review_result.summary,
            "text": f"""
## Risk Assessment
- **Risk Level**: {review_result.risk_profile.risk_level.value}
- **Risk Score**: {review_result.risk_profile.overall_risk_score:.2f}

## Automation Status
- **Mode**: {review_result.automation_mode.value}
- **Human Review Required**: {'Yes' if review_result.human_review_required else 'No'}
- **Confidence**: {review_result.confidence:.0%}
""",
        }
        
        # Map decision to check conclusion
        conclusion_map = {
            ReviewDecision.APPROVE: "success",
            ReviewDecision.REQUEST_CHANGES: "failure",
            ReviewDecision.NEEDS_DISCUSSION: "neutral",
            ReviewDecision.BLOCK: "failure",
        }
        
        await self.client.create_check_run(
            owner=owner,
            repo=repo,
            name="Aurix Code Review",
            head_sha=head_sha,
            status="completed",
            conclusion=conclusion_map.get(review_result.decision, "neutral"),
            output=check_output,
        )
        
        # If human review not required and automation mode allows, submit review
        if not review_result.human_review_required:
            event_map = {
                ReviewDecision.APPROVE: "APPROVE",
                ReviewDecision.REQUEST_CHANGES: "REQUEST_CHANGES",
                ReviewDecision.NEEDS_DISCUSSION: "COMMENT",
                ReviewDecision.BLOCK: "REQUEST_CHANGES",
            }
            
            # Build review comments
            review_comments = []
            for comment in review_result.comments:
                if comment.get("file") and comment.get("line"):
                    review_comments.append({
                        "path": comment["file"],
                        "line": comment["line"],
                        "body": comment["body"],
                    })
            
            await self.client.create_pull_request_review(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                event=event_map.get(review_result.decision, "COMMENT"),
                body=review_result.summary,
                comments=review_comments[:20],  # GitHub limits comments
            )
        else:
            # Just post a comment
            await self.client.create_comment(
                owner=owner,
                repo=repo,
                issue_number=pr_number,
                body=review_result.summary + f"\n\n⚠️ *{review_result.escalation_reason}*",
            )
        
        # Add labels
        labels = [f"aurix:{review_result.decision.value}"]
        if review_result.risk_profile.risk_level.value in ["high", "critical"]:
            labels.append("high-risk")
        
        try:
            await self.client.add_labels(owner, repo, pr_number, labels)
        except:
            pass  # Labels may not exist
    
    async def _handle_push(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle push events - trigger SDLC pipeline."""
        ref = payload.get("ref", "")
        repo_data = payload.get("repository", {})
        
        # Only handle main branch pushes
        if not ref.endswith("/main") and not ref.endswith("/master"):
            return {"handled": False, "reason": "Not main branch"}
        
        owner = repo_data.get("owner", {}).get("login", "")
        repo = repo_data.get("name", "")
        head_commit = payload.get("head_commit", {})
        
        # Create and execute pipeline
        config = self.sdlc.create_pipeline(
            repo=f"{owner}/{repo}",
            name=f"push_{head_commit.get('id', '')[:7]}",
        )
        
        execution = await self.sdlc.execute_pipeline(
            config=config,
            trigger_type="push",
            trigger_ref=head_commit.get("id", ""),
            triggered_by=head_commit.get("author", {}).get("username", ""),
        )
        
        return {
            "handled": True,
            "execution_id": execution.execution_id,
            "status": execution.status.value,
        }
    
    async def _handle_workflow_run(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle workflow run events."""
        action = payload.get("action")
        workflow_run = payload.get("workflow_run", {})
        
        return {
            "handled": True,
            "action": action,
            "workflow_id": workflow_run.get("id"),
            "status": workflow_run.get("status"),
            "conclusion": workflow_run.get("conclusion"),
        }
    
    async def _handle_check_run(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle check run events."""
        action = payload.get("action")
        check_run = payload.get("check_run", {})
        
        # Could be used to track external CI status
        return {
            "handled": True,
            "action": action,
            "check_run_id": check_run.get("id"),
            "name": check_run.get("name"),
            "status": check_run.get("status"),
        }


class GitHubIntegration:
    """
    Main GitHub integration class.
    
    Provides a unified interface for GitHub operations.
    """
    
    def __init__(
        self,
        token: str,
        webhook_secret: Optional[str] = None,
        code_review_module: Optional[CodeReviewModule] = None,
        sdlc_module: Optional[SDLCModule] = None,
    ):
        """Initialize GitHub integration."""
        self.auth = GitHubAuth(token=token)
        self.client = GitHubClient(self.auth)
        
        self.code_review = code_review_module or CodeReviewModule()
        self.sdlc = sdlc_module or SDLCModule()
        
        self.webhook_handler = GitHubWebhookHandler(
            client=self.client,
            code_review_module=self.code_review,
            sdlc_module=self.sdlc,
            webhook_secret=webhook_secret,
        )
    
    async def close(self) -> None:
        """Close connections."""
        await self.client.close()
    
    async def review_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> ReviewResult:
        """
        Trigger review of a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            ReviewResult
        """
        # Get PR data
        pr_data = await self.client.get_pull_request(owner, repo, pr_number)
        pr_files = await self.client.get_pull_request_files(owner, repo, pr_number)
        
        # Fetch file contents
        head_sha = pr_data.get("head", {}).get("sha", "")
        files_with_content = []
        
        for file_info in pr_files[:20]:
            filename = file_info.get("filename", "")
            if file_info.get("status") != "removed":
                try:
                    content = await self.client.get_file_content(
                        owner, repo, filename, ref=head_sha
                    )
                except:
                    content = ""
                
                files_with_content.append({
                    **file_info,
                    "content": content,
                })
            else:
                files_with_content.append(file_info)
        
        # Build PR info
        pr_info = PullRequestInfo(
            pr_id=str(pr_number),
            repo=f"{owner}/{repo}",
            title=pr_data.get("title", ""),
            description=pr_data.get("body", "") or "",
            author=pr_data.get("user", {}).get("login", ""),
            files=files_with_content,
            additions=pr_data.get("additions", 0),
            deletions=pr_data.get("deletions", 0),
            changed_files_count=pr_data.get("changed_files", 0),
            labels=[l.get("name", "") for l in pr_data.get("labels", [])],
            base_branch=pr_data.get("base", {}).get("ref", "main"),
            head_branch=pr_data.get("head", {}).get("ref", ""),
        )
        
        # Perform review
        return await self.code_review.review_pull_request(pr_info)
    
    async def trigger_pipeline(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        stages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Trigger SDLC pipeline for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch to deploy
            stages: Optional custom stages
            
        Returns:
            Pipeline execution info
        """
        config = self.sdlc.create_pipeline(
            repo=f"{owner}/{repo}",
            branch=branch,
            stages=stages,
        )
        
        execution = await self.sdlc.execute_pipeline(
            config=config,
            trigger_type="manual",
            triggered_by="api",
        )
        
        return {
            "execution_id": execution.execution_id,
            "status": execution.status.value,
            "stages": list(execution.stages.keys()),
        }
    
    def get_graduation_status(
        self,
        owner: str,
        repo: str,
    ) -> Dict[str, Any]:
        """Get graduation status for code review automation."""
        return self.code_review.get_graduation_status(f"{owner}/{repo}")

    async def review_and_act(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        team_config: Optional[TeamConfig] = None,
        dry_run: bool = False,
    ) -> ReviewActionResult:
        """
        Review a pull request and take appropriate action.
        
        This is the main entry point for autonomous PR handling.
        Based on review results and team config, it will:
        - AUTO_MERGE if all criteria are met
        - Request HUMAN_REVIEW with specific annotations
        - BLOCK if critical issues found
        - REQUEST_CHANGES for fixable issues
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            team_config: Optional team-specific configuration
            dry_run: If True, don't actually merge
            
        Returns:
            ReviewActionResult with action taken
        """
        # First, perform the review
        review_result = await self.review_pull_request(owner, repo, pr_number)
        
        # Load team config if not provided
        if team_config is None:
            team_config = load_team_config(repo=f"{owner}/{repo}")
        
        # Determine the action
        action_result = self.code_review.determine_action(
            review_result=review_result,
            team_config=team_config,
        )
        
        # Get PR data for SHA
        pr_data = await self.client.get_pull_request(owner, repo, pr_number)
        head_sha = pr_data.get("head", {}).get("sha", "")
        
        # Execute the action
        if action_result.action == ReviewAction.AUTO_MERGE:
            await self._execute_auto_merge(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                pr_data=pr_data,
                action_result=action_result,
                dry_run=dry_run,
            )
        
        elif action_result.action == ReviewAction.HUMAN_REVIEW:
            await self._request_human_review(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                head_sha=head_sha,
                action_result=action_result,
            )
        
        elif action_result.action == ReviewAction.BLOCK:
            await self._block_pr(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                head_sha=head_sha,
                action_result=action_result,
            )
        
        elif action_result.action == ReviewAction.REQUEST_CHANGES:
            await self._request_changes(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                head_sha=head_sha,
                action_result=action_result,
            )
        
        return action_result
    
    async def _execute_auto_merge(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        pr_data: Dict[str, Any],
        action_result: ReviewActionResult,
        dry_run: bool = False,
    ) -> None:
        """Execute auto-merge for a PR."""
        head_sha = pr_data.get("head", {}).get("sha", "")
        
        # Create check run showing auto-merge decision
        await self.client.create_check_run(
            owner=owner,
            repo=repo,
            name="Aurix Auto-Review",
            head_sha=head_sha,
            status="completed",
            conclusion="success",
            output={
                "title": "✅ Auto-Merge Approved",
                "summary": f"All quality and risk thresholds met for automatic merge.\n\n"
                          f"**Confidence:** {action_result.confidence_score:.0%}\n"
                          f"**Risk Level:** {action_result.risk_level}\n"
                          f"**Quality Score:** {action_result.quality_score:.0%}",
            },
        )
        
        # Submit approving review
        await self.client.create_pull_request_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            event="APPROVE",
            body=f"## ✅ Aurix Auto-Approved\n\n"
                 f"This PR has been automatically approved based on:\n"
                 f"- **Quality Score:** {action_result.quality_score:.0%}\n"
                 f"- **Risk Level:** {action_result.risk_level}\n"
                 f"- **Confidence:** {action_result.confidence_score:.0%}\n\n"
                 f"*{action_result.reason}*",
        )
        
        if not dry_run:
            # Actually merge the PR
            try:
                merge_result = await self.client.merge_pull_request(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    merge_method="squash",
                    commit_title=f"{pr_data.get('title', 'Merge')} (#{pr_number})",
                    commit_message=f"Auto-merged by Aurix\n\n"
                                  f"Quality: {action_result.quality_score:.0%} | "
                                  f"Risk: {action_result.risk_level} | "
                                  f"Confidence: {action_result.confidence_score:.0%}",
                )
                
                # Add success label
                await self.client.add_labels(
                    owner, repo, pr_number, ["aurix:auto-merged"]
                )
                
            except Exception as e:
                # If merge fails, post a comment
                await self.client.create_comment(
                    owner=owner,
                    repo=repo,
                    issue_number=pr_number,
                    body=f"## ⚠️ Auto-Merge Failed\n\n"
                         f"Aurix approved this PR for auto-merge, but the merge failed:\n"
                         f"```\n{str(e)}\n```\n\n"
                         f"Please merge manually or resolve any conflicts.",
                )
        else:
            # Add label indicating it would have been merged
            await self.client.add_labels(
                owner, repo, pr_number, ["aurix:auto-merge-eligible"]
            )
    
    async def _request_human_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        action_result: ReviewActionResult,
    ) -> None:
        """Request human review with specific annotations."""
        human_review = action_result.human_review
        
        # Create check run showing review needed
        await self.client.create_check_run(
            owner=owner,
            repo=repo,
            name="Aurix Auto-Review",
            head_sha=head_sha,
            status="completed",
            conclusion="neutral",
            output={
                "title": "👤 Human Review Required",
                "summary": f"{action_result.reason}\n\n"
                          f"**Confidence:** {action_result.confidence_score:.0%}\n"
                          f"**Risk Level:** {action_result.risk_level}",
            },
        )
        
        # Post detailed review request as comment
        if human_review:
            body = human_review.to_github_body()
        else:
            body = f"## 👤 Human Review Required\n\n{action_result.reason}"
        
        await self.client.create_comment(
            owner=owner,
            repo=repo,
            issue_number=pr_number,
            body=body,
        )
        
        # Add inline comments for specific annotations
        if human_review and human_review.annotations:
            review_comments = []
            for ann in human_review.annotations[:20]:  # GitHub limits
                if ann.line_ranges:
                    for lr in ann.line_ranges[:1]:  # Use first line range
                        review_comments.append({
                            "path": ann.file_path,
                            "line": lr.end,  # Use end line for comment
                            "body": ann.to_github_comment(),
                        })
            
            if review_comments:
                await self.client.create_pull_request_review(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    event="COMMENT",
                    body="Aurix has identified specific areas that need human review. "
                         "See inline comments below.",
                    comments=review_comments,
                )
        
        # Add labels
        labels = ["aurix:needs-review"]
        if human_review and human_review.priority.value in ("high", "critical"):
            labels.append("priority:high")
        
        await self.client.add_labels(owner, repo, pr_number, labels)
    
    async def _block_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        action_result: ReviewActionResult,
    ) -> None:
        """Block a PR due to critical issues."""
        # Create failing check run
        await self.client.create_check_run(
            owner=owner,
            repo=repo,
            name="Aurix Auto-Review",
            head_sha=head_sha,
            status="completed",
            conclusion="failure",
            output={
                "title": "🚫 PR Blocked - Critical Issues",
                "summary": f"This PR has been blocked due to critical issues.\n\n"
                          f"**Issues:**\n" + 
                          "\n".join(f"- {issue}" for issue in action_result.blocking_issues[:10]),
            },
        )
        
        # Request changes
        await self.client.create_pull_request_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            event="REQUEST_CHANGES",
            body=f"## 🚫 PR Blocked\n\n"
                 f"Critical issues must be resolved before this can be merged:\n\n" +
                 "\n".join(f"- {issue}" for issue in action_result.blocking_issues) +
                 f"\n\n*Confidence: {action_result.confidence_score:.0%}*",
        )
        
        # Add labels
        await self.client.add_labels(
            owner, repo, pr_number, ["aurix:blocked", "critical"]
        )
    
    async def _request_changes(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        head_sha: str,
        action_result: ReviewActionResult,
    ) -> None:
        """Request changes from the PR author."""
        # Create check run
        await self.client.create_check_run(
            owner=owner,
            repo=repo,
            name="Aurix Auto-Review",
            head_sha=head_sha,
            status="completed",
            conclusion="action_required",
            output={
                "title": "📝 Changes Requested",
                "summary": f"Please address the following before this can be merged:\n\n" +
                          "\n".join(f"- {change}" for change in action_result.changes_requested[:10]),
            },
        )
        
        # Request changes review
        await self.client.create_pull_request_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            event="REQUEST_CHANGES",
            body=f"## 📝 Changes Requested\n\n"
                 f"Please address the following:\n\n" +
                 "\n".join(f"- {change}" for change in action_result.changes_requested) +
                 f"\n\n*Quality Score: {action_result.quality_score:.0%} | "
                 f"Confidence: {action_result.confidence_score:.0%}*",
        )
        
        # Add label
        await self.client.add_labels(
            owner, repo, pr_number, ["aurix:changes-requested"]
        )
