# AURIX — Confidence Driven Autonomy Platform for Enterprise AI

> **Removing humans from workflows only when risk allows.**

[![GitHub Actions](https://img.shields.io/badge/runs%20on-GitHub%20Actions-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 What is AURIX?

**AURIX** is a governance and control platform that determines when AI systems can safely replace human approvals in enterprise workflows. 

The platform:
1. **Decomposes** workflows into discrete decision units
2. **Evaluates** intent and risk for each decision
3. **Measures** automation confidence with statistical rigor
4. **Graduates** to autonomy only when risk thresholds allow

Unlike traditional automation that blindly removes humans, AURIX ensures AI autonomy is **earned through demonstrated performance**, not assumed.

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
- 🔍 Detects intent (feature, bugfix, hotfix, refactor)
- ⚠️ Assesses risk (impact, security, complexity)
- 🤖 Runs AI analysis via GPT-4o-mini (optional)
- 📊 Calculates confidence score
- 💬 Posts review with decision and reasoning
- 📈 Tracks outcomes for graduation

### 2. Autonomous SDLC Pipeline
When you push to main, the pipeline runs:
- **Lint** → Code style checks (ruff, black)
- **Test** → Unit tests with pytest
- **Build** → Package build
- **Security** → Vulnerability scan (bandit)

## 🏃 Quick Start

### Option 1: Use in Your GitHub Repository

1. **Create workflow file** `.github/workflows/aurix-review.yml`:

```yaml
name: Aurix Code Review

on:
  pull_request:
    types: [opened, synchronize, ready_for_review]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Aurix
        run: pip install git+https://github.com/cstpalash/aurix.git

      - name: Run Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python -m aurix.actions.run \
            --repo "${{ github.repository }}" \
            --pr "${{ github.event.pull_request.number }}" \
            --action review
```

2. **Add OpenAI API key** (optional - enables AI-enhanced reviews):
   - Go to **Settings → Secrets → Actions**
   - Add `OPENAI_API_KEY`

3. **Open a PR** and watch Aurix analyze it! 🎉

### Option 2: Local Development

```bash
# Clone
git clone https://github.com/cstpalash/aurix.git
cd aurix

# Setup
python -m venv venv
source venv/bin/activate
pip install -e .

# Test AI review
python examples/test_ai_review.py
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

```bash
# Required for GitHub integration (automatically provided in Actions)
GITHUB_TOKEN=ghp_your_personal_access_token

# Optional: Enable AI-enhanced reviews (~$0.01/review)
OPENAI_API_KEY=sk-your-openai-key
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
