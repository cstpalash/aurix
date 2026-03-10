"""
Aurix Configuration Module

Provides team and repository-specific configuration loading.
"""

from aurix.config.team_config import (
    TeamConfig,
    ConfigLoader,
    AutoMergeConfig,
    HumanReviewConfig,
    RiskConfig,
    ReviewChecksConfig,
    CheckConfig,
    load_team_config,
    get_config_loader,
)

__all__ = [
    "TeamConfig",
    "ConfigLoader",
    "AutoMergeConfig",
    "HumanReviewConfig",
    "RiskConfig",
    "ReviewChecksConfig",
    "CheckConfig",
    "load_team_config",
    "get_config_loader",
]
