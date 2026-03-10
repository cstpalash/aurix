"""
Modules package for Aurix domain-specific implementations.

Each module implements a specific workflow automation domain.
Modules are registered with ModuleRegistry for discovery.
"""

from aurix.modules.code_review import CodeReviewModule, PullRequestInfo
from aurix.modules.sdlc import SDLCModule

# Register adapters with the module registry (imports trigger registration)
from aurix.modules.code_review_adapter import CodeReviewModuleAdapter
from aurix.modules.sdlc_adapter import SDLCModuleAdapter

__all__ = [
    "CodeReviewModule",
    "PullRequestInfo",
    "SDLCModule",
    "CodeReviewModuleAdapter",
    "SDLCModuleAdapter",
]
