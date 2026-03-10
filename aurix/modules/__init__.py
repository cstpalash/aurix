"""
Modules package for Aurix domain-specific implementations.

Each module implements a specific workflow automation domain.
Modules are registered with ModuleRegistry for discovery.
"""

from aurix.modules.code_review import CodeReviewModule, PullRequestInfo
from aurix.modules.sdlc import SDLCModule

__all__ = [
    "CodeReviewModule",
    "PullRequestInfo",
    "SDLCModule",
]
