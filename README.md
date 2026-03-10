# Aurix - Autonomous Human-in-the-Loop Removal Platform

> **Zero-infrastructure automation that removes humans from agentic workflows with confidence**

[![GitHub Actions](https://img.shields.io/badge/runs%20on-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Vision

Aurix is a generic platform that systematically removes human intervention from any agentic workflow by:

1. **Decomposing** human steps into smaller, measurable tasks
2. **Assessing** risk associated with automation of each task
3. **Deploying** AI-powered micro-agents to handle tasks
4. **Monitoring** success rates with statistical confidence
5. **Graduating** to full automation when performance thresholds are met

## 🚀 Zero-Cost PoC Architecture

**No servers, no databases, no infrastructure costs!**

| Component | Solution | Cost |
|-----------|----------|------|
| Compute | GitHub Actions | **Free** |
| Storage | JSON files in `.aurix/` | **Free** |
| AI Review | OpenAI GPT-4o-mini | **~$0.01/review** |
| Triggers | GitHub webhooks | **Free** |
| State | GitHub Actions cache | **Free** |

## ✨ Key Features

### 🤖 AI-Enhanced Code Review
- **GPT-4o-mini** powered analysis (~$0.01 per review)
- Security vulnerability detection
- Logic error identification  
- Code style and best practices
- Graceful fallback to rule-based when no API key

### 📊 Confidence-Based Automation Graduation

| Level | Mode | Description |
|-------|------|-------------|
| 1 | **Shadow** | AI runs silently, human decides |
| 2 | **Suggestion** | AI suggests, human approves |
| 3 | **Auto + Review** | AI decides, human spot-checks (10%) |
| 4 | **Full Auto** | Complete automation with monitoring |

Uses **Wilson score intervals** for statistically rigorous confidence scoring.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AURIX PLATFORM                               │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  Task Decomposer │  │  Risk Assessor  │  │  Confidence Engine  │  │
│  │                  │  │                 │  │                     │  │
│  │  - Intent Parser │  │  - Impact Score │  │  - Success Tracker  │  │
│  │  - Step Splitter │  │  - Blast Radius │  │  - Error Analyzer   │  │
│  │  - Dependency    │  │  - Reversibility│  │  - Threshold Match  │  │
│  │    Mapper        │  │  - Compliance   │  │  - Graduation Logic │  │
│  └────────┬─────────┘  └────────┬────────┘  └──────────┬──────────┘  │
│           │                     │                      │             │
│           └─────────────────────┼──────────────────────┘             │
│                                 ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    GENERIC MODULE SYSTEM                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │   │
│  │  │ Code Review │  │    SDLC     │  │  Your Custom Module │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    FILE-BASED STORAGE                         │   │
│  │   .aurix/data/outcomes/*.json  - Execution history            │   │
│  │   .aurix/data/tasks/*.json     - Task states & modes          │   │
│  │   .aurix/data/confidence/*.json - Graduation tracking         │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
## 📋 PoC Use Cases

### 1. Autonomous Code Review
When you open a PR, Aurix automatically:
- Detects the intent (feature, bugfix, hotfix, etc.)
- Assesses risk based on files changed, complexity, security implications
- Runs checks (style, security, complexity, documentation)
- Posts a review comment with decision and confidence score
- Tracks outcomes to improve automation over time

### 2. Autonomous SDLC Pipeline
When you push to main/develop, Aurix:
- Runs your pipeline stages (lint, test, build, deploy)
- Assesses deployment risk per environment
- In shadow mode: reports what it would do
- In full auto mode: deploys with automatic rollback on failure

## � Quick Start (5 minutes)

### Option 1: Add to Your GitHub Repo

1. Copy the workflow file to your repo:

```bash
# In your project directory
mkdir -p .github/workflows
curl -o .github/workflows/aurix.yml \
  https://raw.githubusercontent.com/palashroy/aurix/main/examples/github-workflow.yml
```

2. Commit and push:

```bash
git add .github/workflows/aurix.yml
git commit -m "Add Aurix automation"
git push
```

3. Open a PR and watch Aurix analyze it! 🎉

### Option 2: Local Development

```bash
# Clone the repository
git clone https://github.com/palashroy/aurix.git
cd aurix

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install (minimal dependencies)
pip install -e .

# Run a review locally
aurix review --repo owner/repo --pr 123
```

## 🚀 Quick Start

### Run the API Server

```bash
# Start the API server
aurix serve

# Or with custom port
aurix serve --port 8080
```

### Run a Code Review

```bash
# Review a pull request
aurix review --repo owner/repo --pr 123

# Review with verbose output
aurix review --repo owner/repo --pr 123 --verbose
```

### Run an SDLC Pipeline

```bash
# Execute a full pipeline
aurix pipeline --repo owner/repo --branch main

# Execute specific stages
aurix pipeline --repo owner/repo --branch main --stages build,test,deploy
```

### Check Graduation Status

```bash
# View graduation status for all tasks
aurix status

# View status for a specific task
aurix status --task code-review-style
```

## ⚙️ Configuration

Aurix uses a YAML configuration file (`aurix.yaml`) for all settings:

```yaml
# Core Settings
core:
  log_level: INFO
  metrics_enabled: true

# Risk Assessment
risk:
  thresholds:
    minimal: 0.1
    low: 0.3
    medium: 0.5
    high: 0.7
    critical: 0.9
  weights:
    impact: 0.20
    blast_radius: 0.15
    reversibility: 0.15
    security: 0.15
    compliance: 0.10
    data_sensitivity: 0.10
    complexity: 0.10
    frequency: 0.05

# Confidence Engine
confidence:
  min_outcomes_for_graduation: 20
  min_confidence_for_graduation: 0.85
  max_error_rate_for_full_auto: 0.02

# Automation Modes
automation:
  default_mode: shadow
  modes:
    shadow:
      requires_human_approval: true
    suggestion:
      min_confidence_to_enter: 0.7
    auto_with_review:
      min_confidence_to_enter: 0.85
      spot_check_rate: 0.1
    full_auto:
      min_confidence_to_enter: 0.95
```

### Environment Variables

Create a `.env` file from the template:

```bash
# GitHub Integration
GITHUB_TOKEN=ghp_your_personal_access_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# API Authentication
AURIX_API_SECRET=your_api_secret

# Database (optional)
DATABASE_URL=postgresql://user:pass@localhost:5432/aurix
```

## 🔌 API Reference

### Review Endpoint

```bash
POST /api/v1/review
Content-Type: application/json

{
  "repo": "owner/repo",
  "pr_number": 123
}
```

### Pipeline Endpoint

```bash
POST /api/v1/pipeline
Content-Type: application/json

{
  "repo": "owner/repo",
  "branch": "main",
  "environment": "staging"
}
```

### Graduation Status

```bash
GET /api/v1/graduation/{task_id}
```

### Record Outcome

```bash
POST /api/v1/outcome
Content-Type: application/json

{
  "task_id": "code-review-style",
  "success": true,
  "human_correction": false
}
```

### Dashboard

```bash
GET /api/v1/dashboard
```

## 🔑 Key Concepts

### Risk Profiling
- **Impact Score**: What's the potential damage if automation fails?
- **Blast Radius**: How many systems/users are affected?
- **Reversibility**: Can we undo the automated action?
- **Compliance**: Are there regulatory requirements?

### Confidence Scoring
- **Success Rate**: Percentage of correct automated decisions
- **Error Rate**: Types and severity of failures
- **Human Override Rate**: How often humans correct the automation
- **Statistical Significance**: Confidence interval of measurements

### Graduation Levels
1. **Shadow Mode**: AI runs but human still decides
2. **Suggestion Mode**: AI suggests, human approves
3. **Auto with Review**: AI decides, human spot-checks
4. **Full Auto**: Complete automation with monitoring

## � GitHub Actions Integration

Aurix integrates with GitHub Actions for automated triggering. Add these workflows to your repository:

### Code Review Workflow

```yaml
# .github/workflows/aurix-review.yml
name: Aurix Code Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  aurix-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Aurix Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          AURIX_API_URL: ${{ secrets.AURIX_API_URL }}
        run: |
          curl -X POST "$AURIX_API_URL/api/v1/review" \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"repo": "${{ github.repository }}", "pr_number": ${{ github.event.pull_request.number }}}'
```

### SDLC Pipeline Workflow

```yaml
# .github/workflows/aurix-pipeline.yml
name: Aurix SDLC Pipeline
on:
  push:
    branches: [main, develop]

jobs:
  aurix-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Aurix Pipeline
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          AURIX_API_URL: ${{ secrets.AURIX_API_URL }}
        run: |
          curl -X POST "$AURIX_API_URL/api/v1/pipeline" \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"repo": "${{ github.repository }}", "branch": "${{ github.ref_name }}"}'
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aurix --cov-report=html

# Run specific test module
pytest tests/test_risk_assessor.py -v
```

## 📁 Project Structure

```
aurix/
├── aurix/
│   ├── __init__.py
│   ├── main.py                 # Main entry point
│   ├── config.py               # Configuration management
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py             # FastAPI server
│   ├── core/
│   │   ├── __init__.py
│   │   ├── risk_assessor.py    # Risk assessment engine
│   │   ├── confidence_engine.py # Confidence scoring
│   │   ├── task_decomposer.py  # Task breakdown
│   │   └── micro_agent.py      # Agent orchestration
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── code_review.py      # Code review automation
│   │   └── sdlc.py             # SDLC automation
│   ├── integrations/
│   │   ├── __init__.py
│   │   └── github.py           # GitHub integration
│   └── cli/
│       ├── __init__.py
│       └── commands.py         # CLI commands
├── tests/
│   ├── __init__.py
│   ├── test_risk_assessor.py
│   ├── test_confidence_engine.py
│   └── test_code_review.py
├── .github/
│   └── workflows/
│       ├── aurix-review.yml
│       └── aurix-pipeline.yml
├── aurix.yaml                  # Configuration file
├── pyproject.toml              # Project metadata
└── README.md
```

## �📄 License

MIT License - See LICENSE file for details
