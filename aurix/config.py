"""
Configuration management for Aurix.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class RiskThresholds(BaseModel):
    """Risk level thresholds."""
    
    minimal: float = 0.1
    low: float = 0.3
    medium: float = 0.5
    high: float = 0.7
    critical: float = 0.9


class RiskWeights(BaseModel):
    """Risk dimension weights."""
    
    impact: float = 0.20
    blast_radius: float = 0.15
    reversibility: float = 0.15
    compliance: float = 0.10
    security: float = 0.15
    data_sensitivity: float = 0.10
    frequency: float = 0.05
    complexity: float = 0.10


class RiskConfig(BaseModel):
    """Risk assessment configuration."""
    
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    weights: RiskWeights = Field(default_factory=RiskWeights)


class DegradationConfig(BaseModel):
    """Degradation detection configuration."""
    
    threshold: float = 0.1
    window: int = 10


class ConfidenceConfig(BaseModel):
    """Confidence engine configuration."""
    
    wilson_confidence_level: float = 0.95
    min_outcomes_for_graduation: int = 20
    min_confidence_for_graduation: float = 0.85
    moving_average_window: int = 50
    max_error_rate_for_full_auto: float = 0.02
    degradation: DegradationConfig = Field(default_factory=DegradationConfig)


class ModeConfig(BaseModel):
    """Automation mode configuration."""
    
    description: str = ""
    requires_human_approval: bool = True
    spot_check_rate: float = 0.0
    min_confidence_to_enter: float = 0.0
    min_success_rate: float = 0.0
    max_risk_level: str = "high"


class AutomationConfig(BaseModel):
    """Automation settings."""
    
    default_mode: str = "shadow"
    modes: dict[str, ModeConfig] = Field(default_factory=dict)


class StyleCheckConfig(BaseModel):
    """Style check configuration."""
    
    enabled: bool = True
    max_line_length: int = 120
    check_trailing_whitespace: bool = True


class SecurityCheckConfig(BaseModel):
    """Security check configuration."""
    
    enabled: bool = True
    fail_on_high_severity: bool = True


class ComplexityCheckConfig(BaseModel):
    """Complexity check configuration."""
    
    enabled: bool = True
    max_cyclomatic_complexity: int = 15


class DocumentationCheckConfig(BaseModel):
    """Documentation check configuration."""
    
    enabled: bool = True
    require_docstrings: bool = True


class LogicCheckConfig(BaseModel):
    """Logic check configuration."""
    
    enabled: bool = True


class CodeReviewChecks(BaseModel):
    """Code review checks configuration."""
    
    style: StyleCheckConfig = Field(default_factory=StyleCheckConfig)
    security: SecurityCheckConfig = Field(default_factory=SecurityCheckConfig)
    complexity: ComplexityCheckConfig = Field(default_factory=ComplexityCheckConfig)
    documentation: DocumentationCheckConfig = Field(default_factory=DocumentationCheckConfig)
    logic: LogicCheckConfig = Field(default_factory=LogicCheckConfig)


class IntentKeywords(BaseModel):
    """Keywords for intent detection."""
    
    feature: list[str] = Field(default_factory=lambda: ["feat", "feature", "add", "implement", "new"])
    bugfix: list[str] = Field(default_factory=lambda: ["fix", "bug", "issue", "resolve", "patch"])
    hotfix: list[str] = Field(default_factory=lambda: ["hotfix", "critical", "urgent", "emergency"])
    refactor: list[str] = Field(default_factory=lambda: ["refactor", "cleanup", "improve", "optimize"])
    docs: list[str] = Field(default_factory=lambda: ["docs", "documentation", "readme", "comment"])
    security: list[str] = Field(default_factory=lambda: ["security", "vulnerability", "cve", "auth"])


class CodeReviewConfig(BaseModel):
    """Code review module configuration."""
    
    enabled: bool = True
    include_patterns: list[str] = Field(
        default_factory=lambda: ["*.py", "*.js", "*.ts", "*.go", "*.java", "*.rb", "*.rs"]
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: ["*.min.js", "*.generated.*", "**/vendor/**", "**/node_modules/**"]
    )
    security_patterns: list[str] = Field(
        default_factory=lambda: [
            r"password\s*=",
            r"api_key\s*=",
            r"secret\s*=",
            r"\beval\(",
            r"\bexec\(",
        ]
    )
    intent_keywords: IntentKeywords = Field(default_factory=IntentKeywords)
    checks: CodeReviewChecks = Field(default_factory=CodeReviewChecks)


class PipelineStage(BaseModel):
    """Pipeline stage configuration."""
    
    name: str
    timeout: int = 300
    required: bool = True
    continue_on_fail: bool = False
    requires_approval_in_mode: list[str] = Field(default_factory=list)


class EnvironmentConfig(BaseModel):
    """Environment-specific configuration."""
    
    auto_deploy: bool = False
    approval_required: bool = True
    min_staging_success_duration: int = 0


class RollbackConfig(BaseModel):
    """Rollback configuration."""
    
    enabled: bool = True
    automatic: bool = True
    health_check_retries: int = 3
    health_check_interval: int = 30


class SDLCConfig(BaseModel):
    """SDLC module configuration."""
    
    enabled: bool = True
    stages: list[PipelineStage] = Field(default_factory=list)
    environments: dict[str, EnvironmentConfig] = Field(default_factory=dict)
    rollback: RollbackConfig = Field(default_factory=RollbackConfig)


class WebhookConfig(BaseModel):
    """GitHub webhook configuration."""
    
    enabled: bool = True
    secret_env_var: str = "GITHUB_WEBHOOK_SECRET"


class CheckRunConfig(BaseModel):
    """GitHub check run configuration."""
    
    enabled: bool = True
    name: str = "Aurix Analysis"


class GitHubConfig(BaseModel):
    """GitHub integration configuration."""
    
    api_base_url: str = "https://api.github.com"
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    events: dict[str, list[str]] = Field(default_factory=dict)
    check_runs: CheckRunConfig = Field(default_factory=CheckRunConfig)


class CORSConfig(BaseModel):
    """CORS configuration."""
    
    enabled: bool = True
    allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    allow_methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    allow_headers: list[str] = Field(default_factory=lambda: ["Authorization", "Content-Type"])


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    
    enabled: bool = True
    requests_per_minute: int = 60
    burst: int = 10


class AuthConfig(BaseModel):
    """Authentication configuration."""
    
    enabled: bool = True
    type: str = "bearer"
    secret_env_var: str = "AURIX_API_SECRET"


class APIConfig(BaseModel):
    """API server configuration."""
    
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors: CORSConfig = Field(default_factory=CORSConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)


class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    type: str = "sqlite"
    connection_string_env_var: str = "DATABASE_URL"
    sqlite_path: str = "./data/aurix.db"


class CacheConfig(BaseModel):
    """Cache configuration."""
    
    enabled: bool = True
    type: str = "memory"
    ttl: int = 3600


class StorageConfig(BaseModel):
    """Storage configuration."""
    
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)


class CoreConfig(BaseModel):
    """Core settings."""
    
    log_level: str = "INFO"
    metrics_enabled: bool = True
    metrics_port: int = 9090


class AurixConfig(BaseModel):
    """Main Aurix configuration."""
    
    core: CoreConfig = Field(default_factory=CoreConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    automation: AutomationConfig = Field(default_factory=AutomationConfig)
    code_review: CodeReviewConfig = Field(default_factory=CodeReviewConfig)
    sdlc: SDLCConfig = Field(default_factory=SDLCConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


class Settings(BaseSettings):
    """Environment-based settings."""
    
    # GitHub
    github_token: str = ""
    github_webhook_secret: str = ""
    
    # API
    aurix_api_secret: str = ""
    
    # Database
    database_url: str = ""
    
    # Notifications
    slack_webhook_url: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def load_config(config_path: Path | str | None = None) -> AurixConfig:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file. If None, looks for aurix.yaml
                    in current directory and parent directories.
    
    Returns:
        Loaded configuration.
    """
    if config_path is None:
        # Search for config file
        search_paths = [
            Path.cwd() / "aurix.yaml",
            Path.cwd() / "aurix.local.yaml",
            Path.cwd() / "config" / "aurix.yaml",
            Path.home() / ".aurix" / "config.yaml",
        ]
        
        for path in search_paths:
            if path.exists():
                config_path = path
                break
    
    if config_path is None:
        # Return default config
        return AurixConfig()
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        return AurixConfig()
    
    with open(config_path) as f:
        data = yaml.safe_load(f)
    
    if data is None:
        return AurixConfig()
    
    return AurixConfig(**data)


def load_settings() -> Settings:
    """Load environment settings."""
    return Settings()


# Global config instance
_config: AurixConfig | None = None
_settings: Settings | None = None


def get_config() -> AurixConfig:
    """Get the global configuration."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_settings() -> Settings:
    """Get the global settings."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
