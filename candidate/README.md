# Candidate Knowledge Base

This directory contains the candidate profile — the single source of truth for all AI operations.

## Directory Structure

```
candidate/
├── example/        # Synthetic example data (committed to Git)
│   └── *.json      # Shows schema structure — not real candidate data
└── private/        # Your real profile (gitignored — never committed)
    └── *.json      # Your actual information — fill this in
```

## Setup Instructions

```bash
# Copy example files to private directory as a starting point
cp candidate/example/*.json candidate/private/

# Edit each file with your real information
# Then validate
uv run applyai profile validate
```

## Files

| File | Purpose |
|---|---|
| `identity.json` | Name, contact details, professional summary |
| `education.json` | Degrees and institutions |
| `experience.json` | Work history |
| `projects.json` | Personal and professional projects |
| `skills.json` | Skill inventory by category |
| `skill_levels.json` | Per-skill proficiency with evidence |
| `achievements.json` | Awards, recognitions, notable accomplishments |
| `certifications.json` | Certifications and credentials |
| `portfolio.json` | GitHub, website, publications, OSS contributions |
| `preferences.json` | Soft preferences (work mode, team size, industry) |
| `target_roles.json` | Target job titles and seniority levels |
| `constraints.json` | Hard constraints (visa, location, salary floor) |

## Skill Level Policy

Skill levels reflect **personal proficiency assessment** — not years of employment.

| Level | Meaning |
|---|---|
| `strong` | Used in production; can mentor others |
| `working` | Used in real projects; comfortable independently |
| `basic` | Have used it; need reference for complex tasks |
| `learning` | Currently studying; not yet used in real work |
| `none` | No experience |

> **Important**: Marking a skill `strong` does NOT authorize the system to claim
> professional employment history for that skill. Every professional claim must
> trace to an ID in `experience.json` or `projects.json` via the `evidence` field.

## What the System Will Never Do

- Invent employment history
- Invent education or degrees
- Invent certifications or dates
- Represent `basic` or `learning` skills as professional experience
- Claim project ownership not documented in your profile
- Assume constraint values (salary, visa, location) — these must be explicitly set

## Constraints Policy

All fields in `constraints.json` default to `null` (unset). The system treats
`null` as "no constraint specified" — it does not infer or assume values from
other profile fields. Only set a constraint if you explicitly want it applied.
