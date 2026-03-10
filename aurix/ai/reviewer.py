"""
AI-powered code reviewer using OpenAI.

Uses GPT-4o-mini for cost-effective reviews (~$0.02 per review).
Falls back to rule-based review if no API key is configured.

Enhanced with:
- AI-powered intent detection (understands what the code does)
- AI-powered semantic risk assessment (identifies auth, data, security changes)
- AI-powered code review (security, logic, style analysis)
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


class IntentAnalysis(BaseModel):
    """AI analysis of code change intent."""
    
    # Primary intent
    primary_intent: str = "unknown"  # feature, bugfix, refactor, hotfix, docs, test, config, dependency, security_patch
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # What the code actually does
    summary: str = ""  # Human-readable summary of what the changes do
    
    # Intent alignment
    title_matches_changes: bool = True  # Does the PR title match what the code does?
    description_matches_changes: bool = True
    
    # Secondary intents (PR might do multiple things)
    secondary_intents: list[str] = Field(default_factory=list)
    
    # Red flags
    hidden_changes: list[str] = Field(default_factory=list)  # Changes not mentioned in title/description
    scope_creep: bool = False  # Does more than stated
    
    # Token usage
    tokens_used: int = 0


class SemanticRiskAnalysis(BaseModel):
    """AI analysis of semantic risk in code changes."""
    
    # Overall risk
    risk_level: str = "medium"  # minimal, low, medium, high, critical
    risk_score: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    # Semantic risk factors (what the code DOES, not just patterns)
    risk_factors: list[str] = Field(default_factory=list)
    
    # Critical area detection
    touches_authentication: bool = False
    touches_authorization: bool = False
    touches_payment: bool = False
    touches_pii: bool = False  # Personally Identifiable Information
    touches_database: bool = False
    touches_api_endpoints: bool = False
    touches_security_config: bool = False
    touches_infrastructure: bool = False
    
    # Impact assessment
    blast_radius: str = "low"  # low, medium, high (how many systems affected)
    reversibility: str = "easy"  # easy, moderate, hard
    
    # Recommendations
    requires_security_review: bool = False
    requires_dba_review: bool = False
    requires_infra_review: bool = False
    recommended_reviewers: list[str] = Field(default_factory=list)
    
    # Token usage
    tokens_used: int = 0


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
    # Teams using different models should update these values
    DEFAULT_INPUT_COST_PER_1M = 0.15
    DEFAULT_OUTPUT_COST_PER_1M = 0.60
    
    # Default model (can be overridden via constructor or env var)
    DEFAULT_MODEL = "gpt-4o-mini"
    
    # Maximum tokens for context (leave room for response)
    MAX_INPUT_TOKENS = 12000
    MAX_OUTPUT_TOKENS = 2000
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        input_cost_per_1m: float | None = None,
        output_cost_per_1m: float | None = None,
    ):
        """
        Initialize the AI reviewer.
        
        Args:
            api_key: OpenAI API key. If not provided, reads from OPENAI_API_KEY env var.
            model: OpenAI model to use. Defaults to AURIX_AI_MODEL env var or 'gpt-4o-mini'.
                   Teams can override with 'gpt-4o', 'gpt-4-turbo', etc.
            input_cost_per_1m: Cost per 1M input tokens (for cost tracking).
            output_cost_per_1m: Cost per 1M output tokens (for cost tracking).
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("AURIX_AI_MODEL", self.DEFAULT_MODEL)
        self.input_cost_per_1m = input_cost_per_1m or self.DEFAULT_INPUT_COST_PER_1M
        self.output_cost_per_1m = output_cost_per_1m or self.DEFAULT_OUTPUT_COST_PER_1M
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
    
    async def analyze_intent(
        self,
        title: str,
        description: str,
        files: list[dict[str, Any]],
        labels: list[str] | None = None,
    ) -> IntentAnalysis:
        """
        Analyze the true intent of code changes using AI.
        
        This goes beyond pattern matching - it reads and understands the code
        to determine what the changes actually do.
        
        Args:
            title: PR title
            description: PR description
            files: List of files with 'filename', 'content', 'patch'
            labels: PR labels
        
        Returns:
            IntentAnalysis with AI-detected intent
        """
        if not self.is_available():
            return self._fallback_intent(title, description, files)
        
        prompt = self._build_intent_prompt(title, description, files, labels)
        prompt = self._truncate_prompt(prompt)
        
        try:
            client = self._get_client()
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_intent_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
                temperature=0.2,
            )
            
            content = response.choices[0].message.content
            analysis = self._parse_intent_response(content)
            
            if response.usage:
                analysis.tokens_used = response.usage.total_tokens
            
            return analysis
            
        except Exception as e:
            analysis = self._fallback_intent(title, description, files)
            analysis.summary = f"AI intent analysis failed: {str(e)[:50]}"
            return analysis
    
    async def analyze_semantic_risk(
        self,
        title: str,
        description: str,
        files: list[dict[str, Any]],
        labels: list[str] | None = None,
    ) -> SemanticRiskAnalysis:
        """
        Analyze semantic risk of code changes using AI.
        
        This understands WHAT the code does to assess risk:
        - Does it touch authentication/authorization?
        - Does it modify database schemas or queries?
        - Does it handle sensitive data (PII, payments)?
        - Does it change security configurations?
        
        Args:
            title: PR title
            description: PR description
            files: List of files with content
            labels: PR labels
        
        Returns:
            SemanticRiskAnalysis with AI-assessed risk
        """
        if not self.is_available():
            return self._fallback_semantic_risk(title, description, files)
        
        prompt = self._build_risk_prompt(title, description, files, labels)
        prompt = self._truncate_prompt(prompt)
        
        try:
            client = self._get_client()
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_risk_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=1000,
                temperature=0.2,
            )
            
            content = response.choices[0].message.content
            analysis = self._parse_risk_response(content)
            
            if response.usage:
                analysis.tokens_used = response.usage.total_tokens
            
            return analysis
            
        except Exception as e:
            analysis = self._fallback_semantic_risk(title, description, files)
            return analysis
    
    def _get_intent_system_prompt(self) -> str:
        """System prompt for intent analysis."""
        return """You are an expert code analyst. Analyze the code changes to understand their TRUE intent.

Return JSON:
{
  "primary_intent": "feature" | "bugfix" | "refactor" | "hotfix" | "docs" | "test" | "config" | "dependency" | "security_patch",
  "confidence": 0.0-1.0,
  "summary": "1-2 sentence description of what the code changes actually DO",
  "title_matches_changes": true/false (does PR title accurately describe the changes?),
  "description_matches_changes": true/false,
  "secondary_intents": ["list", "of", "other", "intents"],
  "hidden_changes": ["changes not mentioned in title/description"],
  "scope_creep": true/false (does PR do more than stated?)
}

Intent definitions:
- feature: Adds new functionality or capabilities
- bugfix: Fixes an existing bug or issue
- refactor: Restructures code without changing behavior
- hotfix: Urgent production fix
- docs: Documentation only changes
- test: Test additions or modifications
- config: Configuration changes
- dependency: Package/dependency updates
- security_patch: Security vulnerability fix

IMPORTANT: Read the actual code, not just the title. The title might be misleading."""

    def _get_risk_system_prompt(self) -> str:
        """System prompt for semantic risk analysis."""
        return """You are a security-aware code analyst. Analyze code changes to assess SEMANTIC RISK.

Return JSON:
{
  "risk_level": "minimal" | "low" | "medium" | "high" | "critical",
  "risk_score": 0.0-1.0,
  "confidence": 0.0-1.0,
  "risk_factors": ["specific risk factors based on what the code DOES"],
  "touches_authentication": true/false (login, logout, tokens, sessions),
  "touches_authorization": true/false (permissions, roles, access control),
  "touches_payment": true/false (billing, payments, subscriptions),
  "touches_pii": true/false (names, emails, addresses, SSN, health data),
  "touches_database": true/false (schema changes, migrations, queries),
  "touches_api_endpoints": true/false (new/modified routes, controllers),
  "touches_security_config": true/false (CORS, CSP, secrets, encryption),
  "touches_infrastructure": true/false (deployment, scaling, networking),
  "blast_radius": "low" | "medium" | "high",
  "reversibility": "easy" | "moderate" | "hard",
  "requires_security_review": true/false,
  "requires_dba_review": true/false,
  "requires_infra_review": true/false,
  "recommended_reviewers": ["security", "dba", "infra", "senior-dev"]
}

Risk assessment criteria:
- CRITICAL: Auth bypass, payment bugs, data exposure, security misconfig
- HIGH: Auth changes, PII handling, database migrations, API changes
- MEDIUM: Business logic changes, new features, external integrations
- LOW: Internal refactoring, test changes, documentation
- MINIMAL: Comments, formatting, dependency bumps (non-security)

IMPORTANT: Analyze the actual code behavior, not just file names or patterns."""

    def _build_intent_prompt(
        self,
        title: str,
        description: str,
        files: list[dict],
        labels: list[str] | None,
    ) -> str:
        """Build prompt for intent analysis."""
        parts = [
            "# Analyze Code Change Intent",
            "",
            f"**PR Title:** {title}",
        ]
        
        if labels:
            parts.append(f"**Labels:** {', '.join(labels)}")
        
        if description:
            parts.append(f"**Description:** {description[:500]}")
        
        parts.append("")
        parts.append("## Code Changes")
        parts.append("")
        
        for file_info in files[:10]:  # Limit files for token efficiency
            filename = file_info.get("filename", "unknown")
            patch = file_info.get("patch", file_info.get("content", ""))
            
            parts.append(f"### {filename}")
            parts.append("```")
            parts.append(patch[:2000] if patch else "(no content)")
            parts.append("```")
            parts.append("")
        
        parts.append("Analyze what this code ACTUALLY does and determine the true intent.")
        
        return "\n".join(parts)

    def _build_risk_prompt(
        self,
        title: str,
        description: str,
        files: list[dict],
        labels: list[str] | None,
    ) -> str:
        """Build prompt for semantic risk analysis."""
        parts = [
            "# Analyze Semantic Risk of Code Changes",
            "",
            f"**PR Title:** {title}",
        ]
        
        if labels:
            parts.append(f"**Labels:** {', '.join(labels)}")
        
        if description:
            parts.append(f"**Description:** {description[:500]}")
        
        parts.append("")
        parts.append("## Code Changes to Analyze for Risk")
        parts.append("")
        
        for file_info in files[:10]:
            filename = file_info.get("filename", "unknown")
            patch = file_info.get("patch", file_info.get("content", ""))
            
            parts.append(f"### {filename}")
            parts.append("```")
            parts.append(patch[:2000] if patch else "(no content)")
            parts.append("```")
            parts.append("")
        
        parts.append("Analyze the semantic risk: What sensitive systems/data does this code touch?")
        
        return "\n".join(parts)

    def _parse_intent_response(self, content: str) -> IntentAnalysis:
        """Parse AI intent response."""
        try:
            data = json.loads(content)
            return IntentAnalysis(
                primary_intent=data.get("primary_intent", "unknown"),
                confidence=float(data.get("confidence", 0.5)),
                summary=data.get("summary", ""),
                title_matches_changes=data.get("title_matches_changes", True),
                description_matches_changes=data.get("description_matches_changes", True),
                secondary_intents=data.get("secondary_intents", []),
                hidden_changes=data.get("hidden_changes", []),
                scope_creep=data.get("scope_creep", False),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return IntentAnalysis(summary="Failed to parse AI response")

    def _parse_risk_response(self, content: str) -> SemanticRiskAnalysis:
        """Parse AI risk response."""
        try:
            data = json.loads(content)
            return SemanticRiskAnalysis(
                risk_level=data.get("risk_level", "medium"),
                risk_score=float(data.get("risk_score", 0.5)),
                confidence=float(data.get("confidence", 0.5)),
                risk_factors=data.get("risk_factors", []),
                touches_authentication=data.get("touches_authentication", False),
                touches_authorization=data.get("touches_authorization", False),
                touches_payment=data.get("touches_payment", False),
                touches_pii=data.get("touches_pii", False),
                touches_database=data.get("touches_database", False),
                touches_api_endpoints=data.get("touches_api_endpoints", False),
                touches_security_config=data.get("touches_security_config", False),
                touches_infrastructure=data.get("touches_infrastructure", False),
                blast_radius=data.get("blast_radius", "low"),
                reversibility=data.get("reversibility", "easy"),
                requires_security_review=data.get("requires_security_review", False),
                requires_dba_review=data.get("requires_dba_review", False),
                requires_infra_review=data.get("requires_infra_review", False),
                recommended_reviewers=data.get("recommended_reviewers", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return SemanticRiskAnalysis()

    def _fallback_intent(
        self,
        title: str,
        description: str,
        files: list[dict],
    ) -> IntentAnalysis:
        """Fallback intent detection using patterns."""
        title_lower = title.lower()
        
        # Pattern-based detection
        if any(k in title_lower for k in ["hotfix", "urgent", "critical"]):
            intent = "hotfix"
        elif any(k in title_lower for k in ["fix", "bug", "issue"]):
            intent = "bugfix"
        elif any(k in title_lower for k in ["feat", "add", "implement", "new"]):
            intent = "feature"
        elif any(k in title_lower for k in ["refactor", "clean", "improve"]):
            intent = "refactor"
        elif any(k in title_lower for k in ["doc", "readme"]):
            intent = "docs"
        elif any(k in title_lower for k in ["test"]):
            intent = "test"
        elif any(k in title_lower for k in ["security", "cve", "vuln"]):
            intent = "security_patch"
        elif any(k in title_lower for k in ["bump", "upgrade", "dependency"]):
            intent = "dependency"
        else:
            intent = "feature"
        
        return IntentAnalysis(
            primary_intent=intent,
            confidence=0.4,  # Low confidence for pattern-based
            summary=f"Pattern-based detection: {intent} (AI unavailable for semantic analysis)",
            title_matches_changes=True,  # Can't verify without AI
        )

    def _fallback_semantic_risk(
        self,
        title: str,
        description: str,
        files: list[dict],
    ) -> SemanticRiskAnalysis:
        """Fallback risk assessment using file patterns."""
        risk_score = 0.3
        risk_factors = []
        
        touches_auth = False
        touches_db = False
        touches_api = False
        touches_infra = False
        
        for file_info in files:
            filename = file_info.get("filename", "").lower()
            
            if any(k in filename for k in ["auth", "login", "session", "token", "password"]):
                touches_auth = True
                risk_score = max(risk_score, 0.7)
                risk_factors.append(f"Touches authentication: {filename}")
            
            if any(k in filename for k in ["migration", "schema", "model", "database"]):
                touches_db = True
                risk_score = max(risk_score, 0.6)
                risk_factors.append(f"Touches database: {filename}")
            
            if any(k in filename for k in ["route", "controller", "api", "endpoint"]):
                touches_api = True
                risk_score = max(risk_score, 0.5)
                risk_factors.append(f"Touches API: {filename}")
            
            if any(k in filename for k in ["docker", "kubernetes", "deploy", "infra", "terraform"]):
                touches_infra = True
                risk_score = max(risk_score, 0.6)
                risk_factors.append(f"Touches infrastructure: {filename}")
        
        # Determine risk level
        if risk_score >= 0.7:
            risk_level = "high"
        elif risk_score >= 0.5:
            risk_level = "medium"
        elif risk_score >= 0.3:
            risk_level = "low"
        else:
            risk_level = "minimal"
        
        return SemanticRiskAnalysis(
            risk_level=risk_level,
            risk_score=risk_score,
            confidence=0.4,  # Low confidence for pattern-based
            risk_factors=risk_factors if risk_factors else ["Pattern-based analysis (AI unavailable)"],
            touches_authentication=touches_auth,
            touches_database=touches_db,
            touches_api_endpoints=touches_api,
            touches_infrastructure=touches_infra,
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
                model=self.model,
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
                    (usage.prompt_tokens / 1_000_000) * self.input_cost_per_1m +
                    (usage.completion_tokens / 1_000_000) * self.output_cost_per_1m
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
    model: str | None = None,
) -> ReviewAnalysis:
    """
    Convenience function to review a PR.
    
    Args:
        title: PR title
        description: PR description  
        files: List of files with content
        labels: Optional PR labels
        api_key: Optional OpenAI API key
        model: Optional model override (default: gpt-4o-mini or AURIX_AI_MODEL env var)
    
    Returns:
        ReviewAnalysis with findings
    """
    reviewer = AIReviewer(api_key=api_key, model=model)
    return await reviewer.review_code(
        title=title,
        description=description,
        files=files,
        labels=labels,
    )
