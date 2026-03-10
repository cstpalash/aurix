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
| AI Review | OpenAI (configurable model) | **~$0.01/review** |
| Triggers | GitHub webhooks | **Free** |
| State | GitHub Actions cache | **Free** |

## ✨ Key Features

### 🤖 AI-Enhanced Code Review (3-Level AI)
- **Level 1: Intent Detection** - AI reads code to understand what it DOES
- **Level 2: Semantic Risk** - AI identifies auth, payment, PII, security implications
- **Level 3: Code Analysis** - Security vulnerabilities, logic errors, style issues
- **Configurable model** - Default: `gpt-4o-mini`, override via `AURIX_AI_MODEL` env var
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
│  │  ┌─────────────┐  ┌─────────────────────────────────────┐    │   │
│  │  │ Code Review │  │       Your Custom Module            │    │   │
│  │  └─────────────┘  └─────────────────────────────────────┘    │   │
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
- 🔍 Detects intent (feature, bugfix, hotfix, refactor) using AI
- ⚠️ Assesses semantic risk (auth, payments, PII, database) using AI
- 🤖 Runs AI code analysis (configurable model, default: gpt-4o-mini)
- 📊 Calculates confidence score
- 💬 Posts review with decision and reasoning
- 📈 Tracks outcomes for graduation

### 2. Autonomous Merge (NEW! 🆕)
When all thresholds are met, Aurix can automatically merge PRs:
- ✅ **Auto-Merge**: All quality/risk thresholds met → merge automatically
- 👤 **Human Review**: Specific files/lines highlighted → focused review
- 🚫 **Block**: Critical issues found → PR blocked with details
- 📝 **Request Changes**: Fixable issues → author must address

---

## 🔬 How the PR Review Pipeline Works

When you create or update a PR, here's the complete flow:

### Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PR: "feat: add user auth"                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: AI-POWERED INTENT DETECTION                            │
│  ────────────────────────────────────                           │
│  🧠 Uses AI (configurable model) to READ THE ACTUAL CODE:       │
│  • What the code actually DOES (not just title pattern matching)│
│  • Whether PR title matches the changes                         │
│  • Hidden changes not mentioned in description                  │
│  • Scope creep (PR doing more than stated)                      │
│                                                                 │
│  Falls back to heuristics (title/label patterns) if no AI:     │
│  → Detected: FEATURE | BUGFIX | HOTFIX | SECURITY_PATCH | etc  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: AI-POWERED SEMANTIC RISK ASSESSMENT                    │
│  ────────────────────────────────────────────                   │
│  🧠 Uses AI (configurable model) to SEMANTICALLY ANALYZE:       │
│  • 🔐 Authentication changes (login, JWT, sessions)             │
│  • 🛡️ Authorization changes (permissions, roles, ACLs)          │
│  • 💳 Payment processing (Stripe, billing, transactions)        │
│  • 👤 PII handling (personal data, GDPR, privacy)               │
│  • 🗄️ Database changes (schemas, migrations, queries)           │
│  • 🌐 API endpoint changes (routes, controllers)                │
│  • ⚙️ Security config (CORS, headers, secrets)                  │
│  • 🏗️ Infrastructure (Terraform, k8s, Docker)                   │
│                                                                 │
│  Also calculates:                                               │
│  • Blast radius (how many systems affected)                     │
│  • Reversibility (easy/moderate/hard to rollback)               │
│  • Recommended reviewers (security team, DBA, etc.)             │
│                                                                 │
│  Falls back to heuristics (file path patterns) if no AI:       │
│  → Risk Level: MINIMAL | LOW | MEDIUM | HIGH | CRITICAL         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: EXECUTE CHECKS                                         │
│  ─────────────────────────                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 🤖 AI Review │  │ 🔒 Security  │  │ 📝 Style     │          │
│  │ (configurable│  │   Patterns   │  │   Checks     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 🧠 Logic     │  │ 📊 Complexity│  │ 📚 Docs      │          │
│  │   Analysis   │  │   Metrics    │  │   Coverage   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: CALCULATE OVERALL SCORE                                │
│  ───────────────────────────────                                │
│  Weighted combination:                                          │
│  • Security: 2.0x weight (most important)                       │
│  • Logic: 1.5x weight                                           │
│  • Complexity: 1.2x weight                                      │
│  • Coverage/Performance: 1.0x weight                            │
│  • Style/Docs: 0.5x weight                                      │
│  → Overall Score: 0.0 to 1.0                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: MAKE DECISION                                          │
│  ─────────────────────                                          │
│                                                                 │
│  if critical_issues OR security_failed:                         │
│      → BLOCK (95% confidence)                                   │
│                                                                 │
│  elif high_severity_issues:                                     │
│      → REQUEST_CHANGES (85% confidence)                         │
│                                                                 │
│  elif score >= 0.8:                                             │
│      → APPROVE (confidence = score)                             │
│                                                                 │
│  elif score >= 0.6:                                             │
│      → REQUEST_CHANGES (confidence = score)                     │
│                                                                 │
│  else:                                                          │
│      → NEEDS_DISCUSSION (low confidence)                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: CHECK ESCALATION (Human Review Needed?)                │
│  ───────────────────────────────────────────────                │
│                                                                 │
│  Human review required if:                                      │
│  • Shadow mode (new repos always start here)                    │
│  • Confidence < 80%                                             │
│  • Risk level is HIGH or CRITICAL                               │
│  • BLOCK decision (needs human confirmation)                    │
│  • APPROVE in suggestion mode                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 7: POST RESULT TO PR                                      │
│  ─────────────────────────                                      │
│                                                                 │
│  ## 🤖 Aurix Code Review                                        │
│                                                                 │
│  ✅ **Decision**: APPROVE                                       │
│  🚀 **Automation Mode**: Auto with Review                       │
│  📊 **Confidence**: 92%                                         │
│                                                                 │
│  ### Check Results                                              │
│  - ✅ Security: 100%                                            │
│  - ✅ Logic: 95%                                                │
│  - ✅ Style: 88%                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Outcomes

| Decision | Meaning | Action |
|----------|---------|--------|
| **APPROVE** | All checks pass, low risk | Can auto-merge if thresholds met |
| **REQUEST_CHANGES** | Fixable issues found | Author must address issues |
| **NEEDS_DISCUSSION** | Low confidence, unclear | Human review required |
| **BLOCK** | Critical/security issues | PR blocked, must fix first |

### Security Patterns Detected

Aurix automatically detects these security issues:

| Pattern | Severity | Example |
|---------|----------|---------|
| Hardcoded passwords | 🔴 Critical | `password = "secret123"` |
| Hardcoded API keys | 🔴 Critical | `api_key = "sk-..."` |
| Shell injection | 🔴 Critical | `subprocess.run(shell=True)` |
| Unsafe eval/exec | 🟠 High | `eval(user_input)` |
| Unsafe pickle | 🟠 High | `pickle.load(file)` |
| Unsafe YAML | 🟠 High | `yaml.load()` without Loader |
| Insecure HTTP | 🟡 Medium | `http://api.example.com` |

---

## 🎓 Graduation System

Over time, as Aurix makes correct decisions (validated by human feedback), it graduates through automation levels:

```
SHADOW → SUGGESTION → AUTO_WITH_REVIEW → FULL_AUTO
  │           │              │               │
  │           │              │               └─ 95%+ confidence, <2% error rate
  │           │              └─ 85%+ confidence, 10% spot-check
  │           └─ 70%+ confidence, human approves
  └─ All decisions logged, human decides (new repos start here)
```

The confidence score uses **Wilson score intervals** - a statistical method that accounts for sample size, so a repo needs ~20+ reviews before it can graduate to higher autonomy levels.

### Graduation Requirements

| Mode | Min Confidence | Min Outcomes | Max Error Rate |
|------|---------------|--------------|----------------|
| Shadow | 0% | 0 | N/A |
| Suggestion | 70% | 10 | 15% |
| Auto + Review | 85% | 20 | 5% |
| Full Auto | 95% | 50 | 2% |

---

## 🔧 Team Configuration (NEW! 🆕)

Each team can customize Aurix behavior with `.aurix/config.yaml`:

```yaml
# Team identification
team_name: "Platform Engineering"

# Auto-merge settings
auto_merge:
  enabled: true
  min_score: 0.85              # Minimum quality score
  max_risk_level: low          # Maximum allowed risk
  excluded_paths:
    - "**/*.sql"               # Never auto-merge SQL
    - "**/infrastructure/**"   # Infra needs review

# Human review requirements
human_review:
  always_review_paths:
    - "**/security/**"         # Always review security
    - "**/auth/**"             # Always review auth
  min_reviewers: 1

# Risk thresholds (customize for your team)
risk:
  thresholds:
    minimal: 0.1
    low: 0.3
    medium: 0.5
    high: 0.7
    critical: 0.9
```

See `.aurix/config.example.yaml` for full configuration options.

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
          # AURIX_AI_MODEL: gpt-4o  # Optional: override default model
        run: |
          python -m aurix.actions.run \
            --repo "${{ github.repository }}" \
            --pr "${{ github.event.pull_request.number }}" \
            --action review
```

2. **Add OpenAI API key** (optional - enables AI-enhanced reviews):
   - Go to **Settings → Secrets → Actions**
   - Add `OPENAI_API_KEY`
   - Optionally add `AURIX_AI_MODEL` to override the default model (e.g., `gpt-4o`)

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

# Optional: Enable AI-enhanced reviews (~$0.01/review with gpt-4o-mini)
OPENAI_API_KEY=sk-your-openai-key

# Optional: Override the default AI model (default: gpt-4o-mini)
# Teams can use more powerful models like gpt-4o for critical repos
AURIX_AI_MODEL=gpt-4o-mini
```

### AI Model Configuration

| Model | Cost (per 1M tokens) | Best For |
|-------|---------------------|----------|
| `gpt-4o-mini` (default) | $0.15 input / $0.60 output | Cost-effective reviews |
| `gpt-4o` | $2.50 input / $10.00 output | High-stakes code |
| `gpt-4-turbo` | $10.00 input / $30.00 output | Maximum accuracy |

Configure via:
- **Environment variable**: `AURIX_AI_MODEL=gpt-4o`
- **Constructor**: `AIReviewer(model="gpt-4o")`
- **With custom costs**: `AIReviewer(model="gpt-4o", input_cost_per_1m=2.50, output_cost_per_1m=10.00)`

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
│   ├── actions/
│   │   └── run.py              # GitHub Actions runner
│   ├── ai/
│   │   └── reviewer.py         # AI reviewer (configurable model)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py           # Main Aurix engine
│   │   ├── module.py           # Module base & registry
│   │   ├── risk_assessor.py    # Risk assessment engine
│   │   └── confidence_engine.py # Confidence scoring (Wilson score)
│   ├── modules/
│   │   ├── __init__.py
│   │   └── code_review.py      # Code review automation
│   ├── config/
│   │   └── team_config.py      # Team configuration loader
│   ├── models/
│   │   └── review_action.py    # Review action models
│   ├── integrations/
│   │   └── github.py           # GitHub API integration
│   └── storage/
│       ├── base.py             # Storage interface
│       └── file_storage.py     # JSON file-based storage
├── tests/
│   └── ...
├── .github/
│   └── workflows/
│       └── aurix-review.yml
├── aurix.yaml                  # Configuration file
├── pyproject.toml              # Project metadata
└── README.md
```

## 📄 License

MIT License - See LICENSE file for details
