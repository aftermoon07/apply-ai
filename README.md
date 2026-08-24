# ApplyAI

> AI-powered personal job acquisition agent — maximize interview opportunities, not application volume.

---

## Overview

ApplyAI is a modular, testable system that helps a candidate discover suitable jobs, evaluate them against their profile, generate tailored resumes, and track every application through to outcome.

**V1 scope**: Candidate profile → Job ingestion → Normalization → Deduplication → Job analysis → Candidate matching → Scoring → Shortlist.

---

## Model Access — Important Distinction

| Context | Model | Purpose |
|---|---|---|
| Antigravity IDE (development) | Claude Sonnet 4.6 Thinking | Writing and reviewing ApplyAI code |
| ApplyAI runtime (this app) | Configurable via `.env` + `settings.yaml` | Analyzing jobs and matching candidates |

The ApplyAI Python application has **no access** to the Antigravity IDE session. It calls external AI APIs independently using keys you provide. **V1 runs fully without any AI key configured** — LLM-dependent steps are skipped gracefully.

---

## Prerequisites

- macOS / Linux
- [uv](https://docs.astral.sh/uv/) — installed automatically by the setup step below

---

## Setup

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install Python 3.12 and project dependencies
uv python install 3.12
uv sync --dev

# 3. Configure environment
cp .env.example .env
# Edit .env — add API keys only if you want AI-powered analysis
# V1 works without any API key

# 4. Initialize the database
uv run alembic upgrade head
```

---

## Candidate Profile

Your candidate data lives in `candidate/private/` (gitignored). This directory is the single source of truth. The system never invents employment history, degrees, or certifications.

```bash
# 1. Copy example schemas to your private directory
cp -r candidate/example/* candidate/private/

# 2. Edit each file with your real information
# See candidate/README.md for field-by-field documentation

# 3. Validate your profile
uv run applyai profile validate
```

**Important**: `candidate/private/` is gitignored. **Never** commit real personal data.

### Skill Level Policy

Skill proficiency ≠ years of professional experience. Marking a skill `strong` reflects your assessment of your depth. It does **not** authorize the system to claim professional employment history for that skill. Professional claims must trace to evidence in `experience.json` or `projects.json`.

---

## Usage (V1)

```bash
# Profile
uv run applyai profile validate
uv run applyai profile show

# Ingest a job (paste, file, or JSON batch)
uv run applyai ingest file --file path/to/job.txt
cat job.txt | uv run applyai ingest text
uv run applyai ingest batch --file path/to/jobs.json

# Run analysis pipeline
uv run applyai analyze
uv run applyai score

# View results
uv run applyai shortlist
uv run applyai show <job-id>

# Audit log
uv run applyai events
```

---

## AI Provider Configuration

Edit `config/settings.yaml`:

```yaml
ai:
  provider: none          # "none" | "anthropic" | "gemini"
  model: ""               # validated at startup against the provider
```

Add the corresponding key to `.env`:
- `ANTHROPIC_API_KEY` for Anthropic/Claude
- `GOOGLE_API_KEY` for Google Gemini (via `google-genai` SDK)

---

## Project Structure

```
apply-ai/
├── candidate/
│   ├── example/          # synthetic data (committed)
│   └── private/          # your real profile (gitignored)
├── applyai/
│   ├── core/             # config, database, logging, exceptions
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic validation schemas
│   ├── providers/        # AI provider abstraction (Anthropic, Gemini, Null)
│   ├── agents/           # orchestrator and specialist agents
│   ├── ingestion/        # job source adapters
│   ├── processing/       # deterministic processing (no LLM)
│   ├── services/         # business logic (UI-agnostic)
│   ├── storage/          # data access layer
│   └── cli/              # Typer CLI entrypoints
├── config/
│   ├── settings.yaml     # app configuration
│   └── logging.yaml      # logging configuration
├── migrations/           # Alembic database migrations
└── tests/
```

---

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=applyai

# Create a new DB migration
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

---

## Security

- API keys live in `.env` only — never committed
- `candidate/private/` is gitignored — never committed
- V1 makes no outbound requests to job platforms, email, LinkedIn, or Telegram
- Any future external action requires explicit user approval

---

## Roadmap

| Phase | Scope |
|---|---|
| **V1** ✅ | Profile · Ingestion · Normalization · Analysis · Scoring · Shortlist |
| V2 | Resume generation · Application tracking · Job discovery APIs |
| V3 | Outreach · Referral discovery · Response monitoring |

## Development Status

Phase 8 complete. Phase 9 is in progress.
## Git Workflow

This project uses Git for version control and GitHub for remote repository hosting.