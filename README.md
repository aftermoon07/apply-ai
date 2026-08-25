# ApplyAI — README Rewrite

You are modifying ONLY the public-facing README.md of the existing ApplyAI repository.

IMPORTANT:
This is a documentation-only task.

Do NOT modify Python code, tests, configuration, migrations, database models, candidate files, Git history, or any other repository file.

Do NOT perform a full architecture review.
Do NOT re-analyze the entire codebase.
Do NOT refactor anything.
Do NOT create new files.

Inspect only the existing README and, if necessary, briefly verify current project capabilities from filenames/known implementation structure.

==================================================
OBJECTIVE
==================================================

Rewrite README.md into a professional, portfolio-quality GitHub README that presents ApplyAI as a serious software engineering project.

The README should focus on:

- What ApplyAI does
- Why it exists
- Its architecture
- Engineering decisions
- Key features
- Security and privacy
- Testing
- AI provider architecture
- Usage
- Project structure
- Development status
- Roadmap

The README should NOT prominently discuss the AI development tools used to create the project.

In particular:

REMOVE the current section:

"Model Access — Important Distinction"

and remove references to:

- Antigravity IDE
- Claude being used to write/review the project
- development-agent model usage
- internal AI coding workflow
- prompts used to build the project
- token limits of the development environment
- internal development conversations

The README is for GitHub visitors, recruiters, engineers, and interviewers.

It should describe the SOFTWARE PROJECT, not the development environment used to create it.

Do not falsely claim that the project was developed without AI assistance. Simply do not make the development tooling part of the public project description.

==================================================
OPENING
==================================================

Use this opening structure:

# ApplyAI

> AI-powered personal job acquisition agent designed to maximize interview opportunities rather than application volume.

Then explain that ApplyAI is an end-to-end job intelligence and application preparation system built with Python.

Explain that it can:

- ingest and discover jobs
- normalize and deduplicate job postings
- analyze job requirements
- match jobs against a structured candidate profile
- score opportunities
- shortlist suitable roles
- generate tailored resumes
- prepare application answers
- generate evidence-grounded outreach drafts
- provide referral search strategies
- track application lifecycle
- record audit events
- track AI token usage and estimated costs

Make the description concise but technically credible.

==================================================
CORE DESIGN PRINCIPLES
==================================================

Add:

## Design Principles

Include these principles:

### Deterministic First

Use ordinary Python logic wherever deterministic processing is possible.

Examples:

- SHA-256 deduplication
- URL normalization
- date parsing
- salary extraction
- weighted scoring
- threshold filtering
- candidate validation
- evidence validation
- token/cost calculations

LLMs are reserved for tasks that genuinely require semantic interpretation.

### Evidence Grounded

The system must not invent candidate experience, education, certifications, skills, or employment history.

Professional claims must be traceable to candidate evidence.

### Human in the Loop

ApplyAI prepares recommendations, resumes, answers, outreach drafts, and application state.

It does not automatically submit applications or send messages.

Any future external action requires explicit user approval.

### Provider Agnostic

The application does not depend on one AI provider.

Providers are abstracted behind a common interface.

==================================================
KEY FEATURES
==================================================

Add a strong feature section.

Use categories:

### Job Intelligence
- Job ingestion
- Job discovery adapter framework
- Deterministic normalization
- URL normalization
- Salary extraction
- Date parsing
- SHA-256 deduplication
- AI job analysis
- ATS keyword preservation
- Candidate matching
- Configurable scoring
- Shortlisting

### Candidate Intelligence
- Structured candidate profile
- Skill proficiency levels
- Evidence-linked skills
- Cross-document evidence validation
- Candidate snapshots
- Profile hashing
- Privacy boundary between synthetic and private data

### Application Preparation
- Job-specific resume generation
- Application lifecycle state machine
- Evidence-grounded application QA
- Evidence-grounded outreach
- Referral search strategies
- Human-reviewable local drafts

### Reliability & Security
- Provider abstraction
- NullProvider for offline operation
- Retry handling
- Prompt-injection protection
- Path traversal protection
- Idempotent analysis
- Audit events
- Token/cost telemetry
- Comprehensive automated testing

Do not claim functionality that does not exist.

==================================================
ARCHITECTURE
==================================================

Add:

## Architecture

Show this conceptual diagram:

CLI / Application Interface
        ↓
Services
        ↓
Agents
        ↓
AI Provider Abstraction
        ↓
Anthropic | Gemini | NullProvider

And separately:

Discovery Adapters
        ↓
Discovery Service
        ↓
Job Service
        ↓
Processing + Storage

Explain the layers briefly:

- CLI: user-facing commands
- Services: business logic and orchestration
- Agents: semantic AI tasks
- Providers: provider-independent AI interface
- Processing: deterministic operations
- Storage: database access
- Models: SQLAlchemy persistence
- Schemas: Pydantic validation
- Discovery: pluggable job-source architecture

Do not include internal filesystem paths specific to one developer machine.

==================================================
END-TO-END PIPELINE
==================================================

Add:

## Pipeline

Show:

Candidate Profile
        ↓
Job Discovery / Ingestion
        ↓
Normalization
        ↓
Deduplication
        ↓
Job Analysis
        ↓
Candidate Matching
        ↓
Deterministic Scoring
        ↓
Shortlist
        ↓
Resume / Application Preparation
        ↓
Outreach Drafts
        ↓
Application Tracking
        ↓
Audit + Usage Telemetry

Explain that deterministic operations and AI-powered operations are intentionally separated.

==================================================
AI ARCHITECTURE
==================================================

Add:

## AI Architecture

Explain that supported runtime providers include:

- Anthropic
- Google Gemini
- NullProvider

Configuration is controlled through settings.yaml and environment variables.

The application can run without an AI API key when using the NullProvider.

Explain that provider-specific implementation is isolated from business logic.

Do NOT mention Antigravity.

Do NOT mention which model was used to develop the project.

Do NOT include development-tool model information.

==================================================
SCORING
==================================================

Add:

## Candidate Matching & Scoring

Explain:

1. The AI matcher produces qualitative component assessments.
2. Python applies configured scoring weights.
3. Python calculates the final 0–100 score.
4. Thresholds determine recommendations.
5. The final score is NOT generated directly by the LLM.

Mention that the system also contains an experimental interview-potential heuristic and that it is not presented as a guaranteed probability.

==================================================
SECURITY & PRIVACY
==================================================

Add:

## Security & Privacy

Include:

- API keys stored through environment variables
- `.env` excluded from Git
- private candidate directory excluded from Git
- synthetic example data used for development/testing
- no automatic application submission
- no automatic email or LinkedIn messaging
- no external account connections in the current implementation
- untrusted job descriptions treated as untrusted data
- prompt injection protections
- generated filenames sanitized against path traversal
- SQLAlchemy parameterized database operations
- evidence-grounded candidate claims
- privacy-safe validation errors
- candidate snapshots for reproducibility

Make clear:

> ApplyAI does not automatically submit applications or send external messages.

==================================================
CANDIDATE PROFILE
==================================================

Add:

## Candidate Profile

Explain that the candidate profile is represented as structured JSON documents.

Mention categories such as:

- identity
- education
- experience
- projects
- skills
- skill levels
- achievements
- certifications
- portfolio
- preferences
- target roles
- constraints

Explain:

- synthetic example data is committed
- private candidate data is gitignored
- profile validation occurs before use
- professional skill claims can be linked to evidence
- cross-document evidence validation prevents references to nonexistent experience/project IDs

Do NOT include any real candidate information.

==================================================
USAGE
==================================================

Keep useful CLI examples, but update them to reflect the current implementation.

Use:

```bash
uv run applyai profile validate
uv run applyai profile show

uv run applyai ingest file --file path/to/job.txt
cat job.txt | uv run applyai ingest text
uv run applyai ingest batch --file path/to/jobs.json

uv run applyai discover run

uv run applyai analyze
uv run applyai score

uv run applyai shortlist
uv run applyai show <job-id>

uv run applyai resume generate <job-id>

uv run applyai track update <job-id> prepared
uv run applyai track list --status interviewing

uv run applyai prep run <job-id>

uv run applyai usage
