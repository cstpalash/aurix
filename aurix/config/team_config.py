"""
Team/Repository Configuration Loader for Aurix Platform

Supports per-repository configuration overrides via .aurix/config.yaml
allowing teams to customize thresholds, weights, and automation rules.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class AutoMergeConfig(BaseModel):
    """Configuration for auto-merge behavior."""
    
    enabled: bool = Field(default=True, description="Enable auto-merge capability")
    min_score: float = Field(default=0.85, ge=0.0, le=1.0, description="Minimum score for auto-merge")
    max_risk_level: str = Field(default="low", description="Maximum risk level for auto-merge")
    require_all_checks_pass: bool = Field(default=True, description="All checks must pass")
    require_ci_pass: bool = Field(default=True, description="CI must pass before auto-merge")
    excluded_paths: List[str] = Field(default_factory=list, description="Paths that cannot be auto-merged")
    protected_branches: List[str] = Field(default_factory=lambda: ["main", "master", "production"])


class HumanReviewConfig(BaseModel):
    """Configuration for human review requirements."""
    
    always_review_paths: List[str] = Field(
        default_factory=lambda: [
            "**/security/**",
            "**/auth/**",
            "**/payment/**",
            "**/*secret*",
            "**/*credential*",
        ],
        description="Paths that always require human review"
    )
    always_review_labels: List[str] = Field(
        default_factory=lambda: ["security", "breaking-change", "needs-review"],
        description="PR labels that trigger human review"
    )
    min_reviewers: int = Field(default=1, description="Minimum human reviewers required")
    

class RiskConfig(BaseModel):
    """Risk assessment configuration."""
    
    # Thresholds for risk levels
    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "minimal": 0.1,
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
            "critical": 0.9,
        }
    )
    
    # Weights for risk dimensions (should sum to ~1.0)
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "impact": 0.20,
            "blast_radius": 0.15,
            "reversibility": 0.15,
            "compliance": 0.10,
            "security": 0.15,
            "data_sensitivity": 0.10,
            "frequency": 0.05,
            "complexity": 0.10,
        }
    )


class CheckConfig(BaseModel):
    """Configuration for individual review checks."""
    
    enabled: bool = Field(default=True)
    weight: float = Field(default=1.0, ge=0.0)
    block_on_failure: bool = Field(default=False)
    min_score: float = Field(default=0.6, ge=0.0, le=1.0)


class ReviewChecksConfig(BaseModel):
    """Configuration for all review checks."""
    
    security: CheckConfig = Field(default_factory=lambda: CheckConfig(weight=1.5, block_on_failure=True))
    logic: CheckConfig = Field(default_factory=lambda: CheckConfig(weight=1.2))
    style: CheckConfig = Field(default_factory=lambda: CheckConfig(weight=0.8))
    complexity: CheckConfig = Field(default_factory=lambda: CheckConfig(weight=1.0))
    documentation: CheckConfig = Field(default_factory=lambda: CheckConfig(weight=0.7))
    performance: CheckConfig = Field(default_factory=lambda: CheckConfig(weight=0.9))


class TeamConfig(BaseModel):
    """
    Complete team/repository configuration.
    
    This can be placed in .aurix/config.yaml in any repository
    to override default Aurix behavior for that specific repo/team.
    """
    
    # Team identification
    team_name: Optional[str] = Field(default=None, description="Team name for tracking")
    team_id: Optional[str] = Field(default=None, description="Team identifier")
    
    # Auto-merge settings
    auto_merge: AutoMergeConfig = Field(default_factory=AutoMergeConfig)
    
    # Human review requirements
    human_review: HumanReviewConfig = Field(default_factory=HumanReviewConfig)
    
    # Risk assessment
    risk: RiskConfig = Field(default_factory=RiskConfig)
    
    # Review checks
    checks: ReviewChecksConfig = Field(default_factory=ReviewChecksConfig)
    
    # Graduation settings (for confidence-based automation)
    graduation: Dict[str, Any] = Field(
        default_factory=lambda: {
            "min_outcomes": 20,
            "min_confidence": 0.85,
            "observation_days": 14,
        }
    )
    
    # Custom rules (advanced)
    custom_rules: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Custom rules for specific scenarios"
    )
    
    class Config:
        extra = "allow"  # Allow additional fields for extensibility


class ConfigLoader:
    """
    Loads and merges configuration from multiple sources.
    
    Priority (highest to lowest):
    1. Environment variables (AURIX_*)
    2. Repository config (.aurix/config.yaml)
    3. Organization config (if available)
    4. Global defaults (aurix.yaml)
    """
    
    DEFAULT_CONFIG_PATHS = [
        ".aurix/config.yaml",
        ".aurix/config.yml",
        "aurix.yaml",
        "aurix.yml",
    ]
    
    def __init__(self, repo_path: Optional[str] = None):
        """Initialize config loader."""
        self.repo_path = Path(repo_path) if repo_path else Path.cwd()
        self._config_cache: Dict[str, TeamConfig] = {}
    
    def load_config(self, repo: Optional[str] = None) -> TeamConfig:
        """
        Load configuration for a repository.
        
        Args:
            repo: Repository identifier (e.g., "owner/repo")
            
        Returns:
            TeamConfig with merged settings
        """
        cache_key = repo or str(self.repo_path)
        
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        # Start with defaults
        config_dict: Dict[str, Any] = {}
        
        # Load from file
        for config_path in self.DEFAULT_CONFIG_PATHS:
            full_path = self.repo_path / config_path
            if full_path.exists():
                try:
                    with open(full_path, 'r') as f:
                        file_config = yaml.safe_load(f) or {}
                        config_dict = self._deep_merge(config_dict, file_config)
                        break  # Use first found config
                except Exception:
                    pass
        
        # Apply environment overrides
        config_dict = self._apply_env_overrides(config_dict)
        
        # Create TeamConfig
        config = TeamConfig(**config_dict)
        self._config_cache[cache_key] = config
        
        return config
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self, config: Dict) -> Dict:
        """Apply environment variable overrides."""
        env_mappings = {
            "AURIX_AUTO_MERGE_ENABLED": ("auto_merge", "enabled", lambda x: x.lower() == "true"),
            "AURIX_AUTO_MERGE_MIN_SCORE": ("auto_merge", "min_score", float),
            "AURIX_AUTO_MERGE_MAX_RISK": ("auto_merge", "max_risk_level", str),
            "AURIX_MIN_REVIEWERS": ("human_review", "min_reviewers", int),
            "AURIX_TEAM_NAME": ("team_name", None, str),
        }
        
        for env_var, (section, key, converter) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    converted = converter(value)
                    if key is None:
                        config[section] = converted
                    else:
                        if section not in config:
                            config[section] = {}
                        config[section][key] = converted
                except (ValueError, TypeError):
                    pass
        
        return config
    
    def get_auto_merge_eligible(
        self,
        config: TeamConfig,
        score: float,
        risk_level: str,
        changed_paths: List[str],
        labels: List[str],
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a PR is eligible for auto-merge based on team config.
        
        Returns:
            (eligible, reason) - If not eligible, reason explains why
        """
        am = config.auto_merge
        hr = config.human_review
        
        # Check if auto-merge is enabled
        if not am.enabled:
            return False, "Auto-merge is disabled for this repository"
        
        # Check score threshold
        if score < am.min_score:
            return False, f"Score {score:.0%} below threshold {am.min_score:.0%}"
        
        # Check risk level
        risk_order = ["minimal", "low", "medium", "high", "critical"]
        max_risk_idx = risk_order.index(am.max_risk_level) if am.max_risk_level in risk_order else 1
        current_risk_idx = risk_order.index(risk_level) if risk_level in risk_order else 2
        
        if current_risk_idx > max_risk_idx:
            return False, f"Risk level '{risk_level}' exceeds maximum '{am.max_risk_level}'"
        
        # Check excluded paths
        import fnmatch
        for path in changed_paths:
            for pattern in am.excluded_paths:
                if fnmatch.fnmatch(path, pattern):
                    return False, f"Path '{path}' matches excluded pattern '{pattern}'"
        
        # Check always-review paths
        for path in changed_paths:
            for pattern in hr.always_review_paths:
                if fnmatch.fnmatch(path, pattern):
                    return False, f"Path '{path}' requires human review (pattern: '{pattern}')"
        
        # Check always-review labels
        for label in labels:
            if label.lower() in [l.lower() for l in hr.always_review_labels]:
                return False, f"Label '{label}' requires human review"
        
        return True, None


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(repo_path: Optional[str] = None) -> ConfigLoader:
    """Get or create the global config loader."""
    global _config_loader
    if _config_loader is None or repo_path:
        _config_loader = ConfigLoader(repo_path)
    return _config_loader


def load_team_config(repo: Optional[str] = None, repo_path: Optional[str] = None) -> TeamConfig:
    """Convenience function to load team configuration."""
    loader = get_config_loader(repo_path)
    return loader.load_config(repo)
