# ApplyAI

> AI-powered personal job acquisition agent designed to maximize interview opportunities rather than application volume.

ApplyAI is an end-to-end job intelligence and application-preparation system built in Python. It ingests job postings, normalizes and deduplicates them, analyzes requirements, matches each role against a structured candidate profile, scores and shortlists opportunities, and prepares tailored resumes, application answers and outreach drafts — while tracking every application through its lifecycle with audit events and AI usage/cost telemetry.

It is deliberately **not** a mass-apply bot. ApplyAI prepares; a human decides and submits.

---

## Design Principles

**Deterministic first.** Ordinary Python handles everything that can be computed exactly — SHA-256 deduplication, URL normalization, date parsing, salary extraction, weighted scoring, threshold filtering, profile and evidence validation, token/cost accounting. LLMs are used only where semantic interpretation is genuinely required.

**Evidence grounded.** The system must not invent experience, education, certifications, skills or employment history. Professional claims are linked to evidence in the candidate profile, and cross-document validation rejects references to experience or project IDs that don't exist.

**Human in the loop.** ApplyAI produces recommendations, resumes, answers, outreach drafts and application state. It never submits applications or sends messages on its own.

**Provider agnostic.** AI providers sit behind a common interface, so business logic does not depend on any one vendor.

---

## Key Features

**Job intelligence**
- Ingestion from files, stdin and JSON batches, plus a pluggable discovery-adapter framework
- Deterministic normalization: URLs, dates, salary ranges
- SHA-256 fingerprint deduplication
- AI job analysis that preserves ATS keywords
- Candidate matching with configurable, weighted scoring and shortlisting

**Candidate intelligence**
- Structured, schema-validated candidate profile (Pydantic)
- Skill proficiency levels and evidence-linked skills
- Cross-document evidence validation
- Profile hashing and candidate snapshots for reproducible analyses
- Hard privacy boundary between synthetic example data and private data

**Application preparation**
- Job-specific resume generation
- Application lifecycle state machine with validated transitions
- Evidence-grounded application QA and outreach drafts
- Referral search strategies
- Local, human-reviewable drafts

**Reliability & security**
- Provider abstraction with a `NullProvider` for fully offline operation
- Retry handling with exponential backoff
- Prompt-injection hardening (job descriptions are treated as untrusted data)
- Path-traversal protection on generated filenames
- Idempotent analysis keyed on job + profile hash
- Audit events and per-call token/cost telemetry
- 200+ automated unit and integration tests

---

## Architecture

```
CLI (Typer + Rich)
      ↓
Services         ← business logic & orchestration
      ↓
Agents           ← semantic AI tasks (analyze, match, tailor, QA, outreach)
      ↓
Provider interface
      ↓
Anthropic | Gemini | NullProvider
```

```
Discovery adapters → Discovery service → Job service → Processing + Storage
```

| Layer | Responsibility |
|---|---|
| `cli/` | User-facing commands |
| `services/` | Orchestration and business rules |
| `agents/` | LLM-backed semantic tasks |
| `providers/` | Provider-independent AI interface |
| `processing/` | Deterministic operations (dedup, normalize, score) |
| `storage/`, `models/` | Async SQLAlchemy persistence, Alembic migrations |
| `schemas/` | Pydantic validation |
| `discovery/` | Pluggable job-source adapters |
| `eval/` | Prompt evaluation runner over synthetic datasets |

---

## Pipeline

```
Candidate profile
   → Discovery / ingestion
   → Normalization → Deduplication
   → Job analysis → Candidate matching
   → Deterministic scoring → Shortlist
   → Resume & application preparation → Outreach drafts
   → Application tracking
   → Audit + usage telemetry
```

Deterministic steps and AI-powered steps are intentionally separated, so every AI step can be skipped, retried or evaluated in isolation.

---

## Candidate Matching & Scoring

1. The AI matcher produces qualitative assessments for each scoring component (technical skills, experience, education, location/work mode, seniority, project relevance, keyword coverage).
2. Python applies the weights configured in `config/settings.yaml` (validated to sum to 1.0 at startup).
3. Python computes the final 0–100 score.
4. Configured thresholds map the score to a recommendation (strong yes / yes / maybe / no) and decide shortlisting.

**The final score is never generated directly by the LLM.** An experimental "interview potential" heuristic is also computed; it is an internal signal, not a probability.

---

## AI Providers

| Provider | Setting | Requirement |
|---|---|---|
| None (offline) | `provider: none` | nothing — AI steps return `skipped` |
| Anthropic | `provider: anthropic` | `ANTHROPIC_API_KEY` in `.env`, `uv sync --extra anthropic` |
| Google Gemini | `provider: gemini` | `GOOGLE_API_KEY` in `.env`, `uv sync --extra gemini` |

The provider and model are configured only in `config/settings.yaml`; model strings are never hard-coded in source.

---

## Security & Privacy

> ApplyAI does not automatically submit applications or send external messages.

- API keys come from environment variables; `.env` is gitignored
- Real candidate data lives in `candidate/private/`, which is gitignored; only synthetic example data is committed
- No external account connections (email, LinkedIn, job boards) in the current implementation
- Job descriptions are wrapped and treated as untrusted input to resist prompt injection
- Generated filenames are sanitized against path traversal
- All database access goes through parameterized SQLAlchemy operations
- Validation errors avoid echoing private profile data
- Candidate snapshots make every analysis reproducible

---

## Candidate Profile

The profile is a set of structured JSON documents: identity, education, experience, projects, skills, skill levels, achievements, certifications, portfolio, preferences, target roles and constraints.

- A synthetic example lives in `candidate/example/`
- Private data goes in `candidate/private/` (gitignored)
- The profile is validated before any use (`applyai profile validate`)
- Skill claims can link to evidence, and cross-document checks catch references to nonexistent experience or project IDs

---

## Getting Started

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/aftermoon07/apply-ai.git
cd apply-ai
uv sync                     # add --extra anthropic / --extra gemini for AI providers
uv run alembic upgrade head # create the local SQLite database
uv run pytest               # run the test suite
```

## Usage

```bash
# Profile
uv run applyai profile validate

# Ingest jobs
uv run applyai ingest file --file path/to/job.txt
cat job.txt | uv run applyai ingest text
uv run applyai ingest batch --file path/to/jobs.json

# Discover, analyze, shortlist
uv run applyai discover run
uv run applyai analyze
uv run applyai shortlist
uv run applyai show job <job-id>

# Prepare and track
uv run applyai resume generate <job-id>
uv run applyai prep run <job-id>
uv run applyai track update <job-id> prepared
uv run applyai track list --status interviewing

# Whole workflow / telemetry / evals
uv run applyai pipeline run
uv run applyai daily
uv run applyai usage
uv run applyai eval run
```

---

## Testing

```bash
uv run pytest
uv run pytest --cov=applyai
```

The suite covers deterministic processing, scoring, the provider layer, agents (with mocked providers), services, the application state machine and end-to-end pipeline integration.

---

## Project Structure

```
applyai/
  agents/       cli/        core/       discovery/   eval/
  ingestion/    models/     processing/ providers/   schemas/
  services/     storage/
candidate/      # example (synthetic) and private (gitignored) profiles
config/         # settings.yaml, logging.yaml
migrations/     # Alembic
tests/          # unit/ and integration/
```

---

## Status & Roadmap

The core pipeline — ingestion through application tracking — is implemented and tested. Current work focuses on running it against real job searches.

Planned:
- CLI and UX polish
- Additional real job-source discovery adapters
- Final security and architecture review

---

## License

MIT
