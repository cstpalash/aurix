"""
Aurix API Server

FastAPI application providing REST endpoints for the Aurix platform.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from aurix.core.risk_assessor import RiskLevel
from aurix.core.confidence_engine import AutomationMode
from aurix.modules.code_review import CodeReviewModule, ReviewDecision
from aurix.modules.sdlc import SDLCModule, PipelineStatus
from aurix.integrations.github import GitHubIntegration


class Settings(BaseSettings):
    """Application settings."""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # GitHub
    github_token: str = ""
    github_webhook_secret: str = ""
    
    # AI Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    
    # Database
    database_url: str = "sqlite:///./aurix.db"
    
    # Security
    secret_key: str = "change-me-in-production"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global instances
settings = Settings()
code_review_module: Optional[CodeReviewModule] = None
sdlc_module: Optional[SDLCModule] = None
github_integration: Optional[GitHubIntegration] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global code_review_module, sdlc_module, github_integration
    
    # Initialize modules
    code_review_module = CodeReviewModule()
    sdlc_module = SDLCModule()
    
    # Initialize GitHub integration if token is available
    if settings.github_token:
        github_integration = GitHubIntegration(
            token=settings.github_token,
            webhook_secret=settings.github_webhook_secret,
            code_review_module=code_review_module,
            sdlc_module=sdlc_module,
        )
    
    yield
    
    # Cleanup
    if github_integration:
        await github_integration.close()


# Create FastAPI app
app = FastAPI(
    title="Aurix API",
    description="Autonomous Human-in-the-Loop Removal Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= Request/Response Models =============

class ReviewRequest(BaseModel):
    """Request to review a pull request."""
    owner: str
    repo: str
    pr_number: int


class ReviewResponse(BaseModel):
    """Response from code review."""
    pr_id: str
    decision: str
    confidence: float
    risk_level: str
    human_review_required: bool
    summary: str
    automation_mode: str


class PipelineRequest(BaseModel):
    """Request to trigger a pipeline."""
    repo: str
    branch: str = "main"
    stages: Optional[List[str]] = None
    environment: str = "staging"


class PipelineResponse(BaseModel):
    """Response from pipeline trigger."""
    execution_id: str
    status: str
    stages: List[str]


class GraduationStatusResponse(BaseModel):
    """Response for graduation status."""
    eligible: bool
    current_mode: str
    next_mode: Optional[str]
    requirements: Dict[str, Any]


class RiskAssessmentRequest(BaseModel):
    """Request for risk assessment."""
    repo: str
    commit: str
    environment: str


class RiskAssessmentResponse(BaseModel):
    """Response for risk assessment."""
    risk_level: str
    risk_score: float
    confidence: float
    mitigation_strategies: List[str]


class StageUpdateRequest(BaseModel):
    """Request to update pipeline stage."""
    stage: str
    status: str
    commit: str
    outputs: Optional[Dict[str, Any]] = None


class FeedbackRequest(BaseModel):
    """Request to provide feedback on a review."""
    pr_id: str
    human_decision: str
    feedback: Optional[str] = None


# ============= Health Endpoints =============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    return {
        "ready": True,
        "modules": {
            "code_review": code_review_module is not None,
            "sdlc": sdlc_module is not None,
            "github": github_integration is not None,
        },
    }


# ============= Code Review Endpoints =============

@app.post("/api/v1/review", response_model=ReviewResponse)
async def review_pull_request(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger automated code review for a pull request.
    """
    if not github_integration:
        raise HTTPException(
            status_code=503,
            detail="GitHub integration not configured",
        )
    
    try:
        result = await github_integration.review_pull_request(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
        )
        
        return ReviewResponse(
            pr_id=result.pr_info.pr_id,
            decision=result.decision.value,
            confidence=result.confidence,
            risk_level=result.risk_profile.risk_level.value,
            human_review_required=result.human_review_required,
            summary=result.summary,
            automation_mode=result.automation_mode.value,
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Review failed: {str(e)}",
        )


@app.post("/api/v1/review/feedback")
async def submit_review_feedback(request: FeedbackRequest):
    """
    Submit human feedback on a review decision.
    """
    if not code_review_module:
        raise HTTPException(
            status_code=503,
            detail="Code review module not initialized",
        )
    
    try:
        human_decision = ReviewDecision(request.human_decision)
        code_review_module.record_human_feedback(
            pr_id=request.pr_id,
            human_decision=human_decision,
            feedback=request.feedback,
        )
        
        return {"status": "recorded", "pr_id": request.pr_id}
    
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision: {str(e)}",
        )


@app.get("/api/v1/review/graduation/{owner}/{repo}")
async def get_review_graduation_status(owner: str, repo: str):
    """
    Get graduation status for code review automation.
    """
    if not code_review_module:
        raise HTTPException(
            status_code=503,
            detail="Code review module not initialized",
        )
    
    return code_review_module.get_graduation_status(f"{owner}/{repo}")


@app.post("/api/v1/review/graduate/{owner}/{repo}")
async def graduate_review_automation(
    owner: str,
    repo: str,
    target_mode: str,
):
    """
    Graduate review automation to a new mode.
    """
    if not code_review_module:
        raise HTTPException(
            status_code=503,
            detail="Code review module not initialized",
        )
    
    try:
        mode = AutomationMode(target_mode)
        success = code_review_module.graduate_repo(f"{owner}/{repo}", mode)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Repository not eligible for graduation",
            )
        
        return {"status": "graduated", "new_mode": target_mode}
    
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid automation mode: {target_mode}",
        )


# ============= Pipeline Endpoints =============

@app.post("/api/v1/pipeline", response_model=PipelineResponse)
async def trigger_pipeline(request: PipelineRequest):
    """
    Trigger an SDLC pipeline.
    """
    if not sdlc_module:
        raise HTTPException(
            status_code=503,
            detail="SDLC module not initialized",
        )
    
    try:
        config = sdlc_module.create_pipeline(
            repo=request.repo,
            stages=request.stages,
        )
        config.branch = request.branch
        
        execution = await sdlc_module.execute_pipeline(
            config=config,
            trigger_type="api",
        )
        
        return PipelineResponse(
            execution_id=execution.execution_id,
            status=execution.status.value,
            stages=list(execution.stages.keys()),
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed: {str(e)}",
        )


@app.get("/api/v1/pipeline/{execution_id}")
async def get_pipeline_status(execution_id: str):
    """
    Get status of a pipeline execution.
    """
    if not sdlc_module:
        raise HTTPException(
            status_code=503,
            detail="SDLC module not initialized",
        )
    
    execution = sdlc_module.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(
            status_code=404,
            detail="Execution not found",
        )
    
    return {
        "execution_id": execution.execution_id,
        "status": execution.status.value,
        "stages": execution.stages,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
    }


@app.post("/api/v1/pipeline/stage")
async def update_pipeline_stage(request: StageUpdateRequest):
    """
    Update pipeline stage status (from GitHub Actions).
    """
    # In production, would update execution state
    return {
        "status": "recorded",
        "stage": request.stage,
    }


@app.post("/api/v1/pipeline/risk", response_model=RiskAssessmentResponse)
async def assess_pipeline_risk(request: RiskAssessmentRequest):
    """
    Assess risk for a pipeline deployment.
    """
    if not sdlc_module:
        raise HTTPException(
            status_code=503,
            detail="SDLC module not initialized",
        )
    
    # Assess risk
    risk_profile = sdlc_module.risk_assessor.assess_sdlc_task(
        task_id=request.commit,
        phase="production_deploy" if request.environment == "production" else "staging_deploy",
        environment=request.environment,
        has_rollback=True,
        has_tests=True,
    )
    
    return RiskAssessmentResponse(
        risk_level=risk_profile.risk_level.value,
        risk_score=risk_profile.overall_risk_score,
        confidence=risk_profile.required_confidence,
        mitigation_strategies=risk_profile.mitigation_strategies,
    )


@app.post("/api/v1/pipeline/deployed")
async def notify_deployment(request: RiskAssessmentRequest):
    """
    Notify of completed deployment.
    """
    return {
        "status": "recorded",
        "repo": request.repo,
        "commit": request.commit,
        "environment": request.environment,
    }


@app.post("/api/v1/pipeline/{execution_id}/rollback")
async def rollback_pipeline(execution_id: str, target_stage: Optional[str] = None):
    """
    Rollback a pipeline execution.
    """
    if not sdlc_module:
        raise HTTPException(
            status_code=503,
            detail="SDLC module not initialized",
        )
    
    result = await sdlc_module.rollback(execution_id, target_stage)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Rollback failed"),
        )
    
    return result


@app.get("/api/v1/pipeline/metrics/{repo:path}")
async def get_pipeline_metrics(repo: str):
    """
    Get pipeline metrics for a repository.
    """
    if not sdlc_module:
        raise HTTPException(
            status_code=503,
            detail="SDLC module not initialized",
        )
    
    return sdlc_module.get_pipeline_metrics(repo)


# ============= Webhook Endpoint =============

@app.post("/api/v1/webhook/github")
async def github_webhook(
    payload: Dict[str, Any],
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    """
    Handle GitHub webhook events.
    """
    if not github_integration:
        raise HTTPException(
            status_code=503,
            detail="GitHub integration not configured",
        )
    
    # Verify signature (in production)
    # if not github_integration.webhook_handler.verify_signature(payload_bytes, x_hub_signature_256):
    #     raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        result = await github_integration.webhook_handler.handle_event(
            event_type=x_github_event or "",
            payload=payload,
        )
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Webhook handling failed: {str(e)}",
        )


# ============= Dashboard Data Endpoints =============

@app.get("/api/v1/dashboard/overview")
async def get_dashboard_overview():
    """
    Get overview data for the dashboard.
    """
    overview = {
        "code_review": {
            "total_reviews": len(code_review_module._review_history) if code_review_module else 0,
            "automation_modes": {},
        },
        "sdlc": {
            "total_executions": len(sdlc_module._executions) if sdlc_module else 0,
            "success_rate": 0.0,
        },
    }
    
    if sdlc_module:
        executions = list(sdlc_module._executions.values())
        if executions:
            successful = sum(
                1 for e in executions
                if e.status == PipelineStatus.SUCCESS
            )
            overview["sdlc"]["success_rate"] = successful / len(executions)
    
    return overview


@app.get("/api/v1/dashboard/confidence")
async def get_confidence_metrics():
    """
    Get confidence metrics across all tasks.
    """
    if not code_review_module:
        return {"message": "No data available"}
    
    # Aggregate confidence data
    return {
        "code_review": {
            "outcomes": len(code_review_module.confidence_tracker._outcomes),
            "history_available": len(code_review_module.confidence_tracker._history) > 0,
        },
    }


# ============= Main Entry Point =============

def main():
    """Run the API server."""
    import uvicorn
    
    uvicorn.run(
        "aurix.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
