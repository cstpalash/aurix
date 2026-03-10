"""
AI-powered code reviewer using OpenAI.

Uses GPT-4o-mini for cost-effective reviews (~$0.01 per review).
Falls back to rule-based review if no API key is configured.
"""

import os
import json
from typing import Any
from enum import Enum

from pydantic import BaseModel, Field


class ReviewSeverity(str, Enum):
    """Severity levels for review issues."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewIssue(BaseModel):
    """A single issue found in code review."""
    
    file: str = ""
    line: int | None = None
    severity: ReviewSeverity = ReviewSeverity.MEDIUM
    category: str = ""  # security, logic, style, performance, etc.
    message: str = ""
    suggestion: str = ""


class ReviewAnalysis(BaseModel):
    """Complete AI analysis of a code change."""
    
    # Overall assessment
    summary: str = ""
    decision: str = "needs_review"  # approve, request_changes, needs_review
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Risk assessment
    risk_level: str = "medium"  # low, medium, high, critical
    risk_factors: list[str] = Field(default_factory=list)
    
    # Issues found
    issues: list[ReviewIssue] = Field(default_factory=list)
    
    # Positive aspects
    strengths: list[str] = Field(default_factory=list)
    
    # Intent understanding
    detected_intent: str = ""  # feature, bugfix, refactor, etc.
    intent_matches_changes: bool = True
    
    # Token usage for cost tracking
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0


class AIReviewer:
    """
    AI-powered code reviewer using OpenAI GPT-4o-mini.
    
    Cost: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
    Typical review: ~2000 input + ~500 output = ~$0.0006 per review
    
    Usage:
        reviewer = AIReviewer()
        if reviewer.is_available():
            analysis = await reviewer.review_code(
                title="Add user authentication",
                description="Implements login/logout",
                files=[{"filename": "auth.py", "content": "..."}]
            )
    """
    
    # Cost per 1M tokens (GPT-4o-mini pricing as of 2024)
    INPUT_COST_PER_1M = 0.15
    OUTPUT_COST_PER_1M = 0.60
    
    # Model to use
    MODEL = "gpt-4o-mini"
    
    # Maximum tokens for context (leave room for response)
    MAX_INPUT_TOKENS = 12000
    MAX_OUTPUT_TOKENS = 2000
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize the AI reviewer.
        
        Args:
            api_key: OpenAI API key. If not provided, reads from OPENAI_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None
    
    def is_available(self) -> bool:
        """Check if AI review is available (API key configured)."""
        return bool(self.api_key)
    
    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "OpenAI package not installed. Run: pip install openai"
                )
        return self._client
    
    async def review_code(
        self,
        title: str,
        description: str,
        files: list[dict[str, Any]],
        labels: list[str] | None = None,
        base_branch: str = "main",
    ) -> ReviewAnalysis:
        """
        Review code changes using AI.
        
        Args:
            title: PR title
            description: PR description
            files: List of files with 'filename', 'content', 'status' (added/modified/deleted)
            labels: PR labels
            base_branch: Target branch
        
        Returns:
            ReviewAnalysis with findings
        """
        if not self.is_available():
            return self._fallback_review(title, description, files)
        
        # Build the prompt
        prompt = self._build_review_prompt(title, description, files, labels, base_branch)
        
        # Truncate if too long
        prompt = self._truncate_prompt(prompt)
        
        try:
            client = self._get_client()
            
            response = await client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=self.MAX_OUTPUT_TOKENS,
                temperature=0.3,  # Lower for more consistent reviews
            )
            
            # Parse response
            content = response.choices[0].message.content
            analysis = self._parse_response(content)
            
            # Track token usage
            usage = response.usage
            if usage:
                analysis.tokens_used = usage.total_tokens
                analysis.estimated_cost_usd = (
                    (usage.prompt_tokens / 1_000_000) * self.INPUT_COST_PER_1M +
                    (usage.completion_tokens / 1_000_000) * self.OUTPUT_COST_PER_1M
                )
            
            return analysis
            
        except Exception as e:
            # Fall back to rule-based on error
            analysis = self._fallback_review(title, description, files)
            analysis.summary = f"AI review failed ({str(e)[:50]}), using rule-based analysis"
            return analysis
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for code review."""
        return """You are an expert code reviewer. Analyze the provided code changes and return a JSON response with:

{
  "summary": "Brief 1-2 sentence summary of the changes",
  "decision": "approve" | "request_changes" | "needs_review",
  "confidence": 0.0-1.0 (how confident you are in this decision),
  "risk_level": "low" | "medium" | "high" | "critical",
  "risk_factors": ["list of specific risk factors"],
  "issues": [
    {
      "file": "filename",
      "line": line_number_or_null,
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "category": "security" | "logic" | "performance" | "style" | "documentation" | "testing",
      "message": "description of the issue",
      "suggestion": "how to fix it"
    }
  ],
  "strengths": ["positive aspects of the changes"],
  "detected_intent": "feature" | "bugfix" | "refactor" | "hotfix" | "docs" | "test" | "config" | "dependency",
  "intent_matches_changes": true | false
}

Review criteria:
1. SECURITY: Check for vulnerabilities, secrets, injection risks, unsafe operations
2. LOGIC: Verify correctness, edge cases, error handling
3. PERFORMANCE: Identify potential bottlenecks, inefficient patterns
4. STYLE: Code quality, readability, naming conventions
5. DOCUMENTATION: Comments, docstrings where needed
6. TESTING: Test coverage considerations

Be concise but thorough. Focus on actionable feedback.
For small/safe changes (docs, tests, config), lean towards approval.
For security issues or logic errors, always request changes."""
    
    def _build_review_prompt(
        self,
        title: str,
        description: str,
        files: list[dict],
        labels: list[str] | None,
        base_branch: str,
    ) -> str:
        """Build the review prompt from PR data."""
        parts = [
            f"# Pull Request Review",
            f"",
            f"**Title:** {title}",
            f"**Target Branch:** {base_branch}",
        ]
        
        if labels:
            parts.append(f"**Labels:** {', '.join(labels)}")
        
        if description:
            parts.append(f"")
            parts.append(f"**Description:**")
            parts.append(description[:1000])  # Limit description length
        
        parts.append(f"")
        parts.append(f"## Changed Files ({len(files)} files)")
        parts.append(f"")
        
        for file_info in files:
            filename = file_info.get("filename", "unknown")
            status = file_info.get("status", "modified")
            content = file_info.get("content", "")
            patch = file_info.get("patch", "")
            
            parts.append(f"### {filename} ({status})")
            parts.append("```")
            
            # Prefer patch (diff) if available, otherwise full content
            if patch:
                parts.append(patch[:3000])  # Limit per file
            elif content:
                parts.append(content[:3000])
            else:
                parts.append("(content not available)")
            
            parts.append("```")
            parts.append("")
        
        return "\n".join(parts)
    
    def _truncate_prompt(self, prompt: str) -> str:
        """Truncate prompt to fit token limits (rough estimate: 4 chars = 1 token)."""
        max_chars = self.MAX_INPUT_TOKENS * 4
        if len(prompt) > max_chars:
            return prompt[:max_chars] + "\n\n(truncated due to length)"
        return prompt
    
    def _parse_response(self, content: str) -> ReviewAnalysis:
        """Parse the AI response into ReviewAnalysis."""
        try:
            data = json.loads(content)
            
            # Parse issues
            issues = []
            for issue_data in data.get("issues", []):
                issues.append(ReviewIssue(
                    file=issue_data.get("file", ""),
                    line=issue_data.get("line"),
                    severity=ReviewSeverity(issue_data.get("severity", "medium")),
                    category=issue_data.get("category", ""),
                    message=issue_data.get("message", ""),
                    suggestion=issue_data.get("suggestion", ""),
                ))
            
            return ReviewAnalysis(
                summary=data.get("summary", ""),
                decision=data.get("decision", "needs_review"),
                confidence=float(data.get("confidence", 0.5)),
                risk_level=data.get("risk_level", "medium"),
                risk_factors=data.get("risk_factors", []),
                issues=issues,
                strengths=data.get("strengths", []),
                detected_intent=data.get("detected_intent", ""),
                intent_matches_changes=data.get("intent_matches_changes", True),
            )
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return ReviewAnalysis(
                summary=f"Failed to parse AI response: {str(e)[:50]}",
                decision="needs_review",
                confidence=0.0,
            )
    
    def _fallback_review(
        self,
        title: str,
        description: str,
        files: list[dict],
    ) -> ReviewAnalysis:
        """Fallback to rule-based review when AI is unavailable."""
        issues = []
        risk_factors = []
        
        # Simple rule-based checks
        security_patterns = [
            ("password", "Hardcoded password detected"),
            ("api_key", "Hardcoded API key detected"),
            ("secret", "Potential secret in code"),
            ("eval(", "Use of eval() is dangerous"),
            ("exec(", "Use of exec() is dangerous"),
            ("subprocess.call", "subprocess.call with shell=True is risky"),
        ]
        
        for file_info in files:
            content = file_info.get("content", "") + file_info.get("patch", "")
            filename = file_info.get("filename", "")
            content_lower = content.lower()
            
            for pattern, message in security_patterns:
                if pattern in content_lower:
                    issues.append(ReviewIssue(
                        file=filename,
                        severity=ReviewSeverity.HIGH,
                        category="security",
                        message=message,
                        suggestion="Review and remove or secure this code",
                    ))
                    risk_factors.append(f"Security concern: {message}")
        
        # Determine decision based on issues
        critical_count = sum(1 for i in issues if i.severity == ReviewSeverity.CRITICAL)
        high_count = sum(1 for i in issues if i.severity == ReviewSeverity.HIGH)
        
        if critical_count > 0:
            decision = "request_changes"
            risk_level = "critical"
        elif high_count > 0:
            decision = "request_changes"
            risk_level = "high"
        elif issues:
            decision = "needs_review"
            risk_level = "medium"
        else:
            decision = "needs_review"  # Can't approve without AI analysis
            risk_level = "low"
        
        # Detect intent from title
        title_lower = title.lower()
        if any(k in title_lower for k in ["fix", "bug", "issue"]):
            intent = "bugfix"
        elif any(k in title_lower for k in ["feat", "add", "implement"]):
            intent = "feature"
        elif any(k in title_lower for k in ["refactor", "clean", "improve"]):
            intent = "refactor"
        elif any(k in title_lower for k in ["doc", "readme"]):
            intent = "docs"
        elif any(k in title_lower for k in ["test"]):
            intent = "test"
        else:
            intent = "feature"
        
        return ReviewAnalysis(
            summary=f"Rule-based analysis of {len(files)} files. "
                    f"Found {len(issues)} potential issues. "
                    f"AI review unavailable (set OPENAI_API_KEY for enhanced analysis).",
            decision=decision,
            confidence=0.3,  # Low confidence without AI
            risk_level=risk_level,
            risk_factors=risk_factors,
            issues=issues,
            strengths=[],
            detected_intent=intent,
            intent_matches_changes=True,
        )


async def review_pr(
    title: str,
    description: str,
    files: list[dict],
    labels: list[str] | None = None,
    api_key: str | None = None,
) -> ReviewAnalysis:
    """
    Convenience function to review a PR.
    
    Args:
        title: PR title
        description: PR description  
        files: List of files with content
        labels: Optional PR labels
        api_key: Optional OpenAI API key
    
    Returns:
        ReviewAnalysis with findings
    """
    reviewer = AIReviewer(api_key=api_key)
    return await reviewer.review_code(
        title=title,
        description=description,
        files=files,
        labels=labels,
    )
