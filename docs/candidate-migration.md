# ApplyAI — Candidate Profile Migration Guide

> **Status:** Infrastructure-only. Do NOT populate this yet with real data.  
> **When to follow this guide:** When you are ready to use ApplyAI with your real profile.

---

## Overview

This guide explains how to manually populate `candidate/private/` from your real resume.

The migration is:

```
Your Resume
    ↓
Manual extraction & human review
    ↓
candidate/private/*.json
    ↓
applyai profile validate   (schema + completeness check)
    ↓
Evidence validation
    ↓
Human sign-off
    ↓
Ready for ApplyAI pipeline
```

> [!IMPORTANT]
> The system will **never invent** employment, dates, responsibilities, skills, certifications, achievements, education, salary, or links.  
> If an item cannot be verified from your source material, **leave it blank or set to null**.  
> Never estimate or infer — only record what is explicitly documented.

---

## Step 0 — Prerequisites

1. You have a copy of your current resume (PDF, DOCX, or text).
2. `candidate/private/` exists and is empty (it is git-ignored; see `.gitignore`).
3. ApplyAI is installed: `uv run applyai version`

---

## Step 1 — Set configuration to strict private mode

In `config/settings.yaml`, set:

```yaml
candidate:
  allow_synthetic_fallback: false
```

This ensures the system will fail clearly if your private profile is missing or invalid — it will never silently fall back to the synthetic example.

---

## Step 2 — Create each profile document

Copy the template from `candidate/example/` into `candidate/private/` and fill in your real information.

> [!WARNING]
> Do NOT simply copy `candidate/example/` into `candidate/private/`. The example files contain fictional data. Replace every field with your verified real information.

### Documents to create (all required)

| File | Contents | Notes |
|------|---------|-------|
| `identity.json` | Name, email, phone, location, LinkedIn, GitHub, summary, years of experience | Required: `full_name`, `email` |
| `education.json` | Degrees, institutions, years | Exact degree title as awarded |
| `experience.json` | Work history | IDs referenced by `skill_levels.json` |
| `projects.json` | Projects | IDs referenced by `skill_levels.json` |
| `skills.json` | Flat skill inventory by category | Category list, no proficiency here |
| `skill_levels.json` | Per-skill proficiency + evidence | `evidence` must reference valid `exp_*` or `proj_*` IDs |
| `achievements.json` | Awards, recognitions | Optional entries; leave `entries: []` if none |
| `certifications.json` | Certificates, licenses | Must match official name exactly |
| `portfolio.json` | GitHub, website, publications, OSS | All optional |
| `preferences.json` | Soft preferences | Does not restrict job discovery |
| `target_roles.json` | Roles you are targeting | Drives scoring emphasis |
| `constraints.json` | Hard constraints (salary, visa, relocation) | Leave `null` if unspecified |

---

## Step 3 — Skill evidence policy

> [!IMPORTANT]
> **Skill level ≠ years of employment.**  
> `years_of_experience` in `skill_levels.json` must be supported by actual entries in `experience.json` or `projects.json`.  
> Leave `years_of_experience: null` if you cannot trace it to documented evidence.

**Evidence format:** `["exp_<company_id>", "proj_<project_id>"]`  
These IDs must match the `id` fields in `experience.json` / `projects.json`.

**Skill levels:**

| Level | Meaning |
|-------|---------|
| `strong` | Used professionally in production; can mentor others |
| `working` | Used in real projects; comfortable independently |
| `basic` | Have used it; need reference for complex tasks |
| `learning` | Currently studying; no production use |
| `none` | No experience |

---

## Step 4 — Constraints policy

Leave hard constraints **null** unless you know the value:

```json
{
  "hard_constraints": {
    "requires_visa_sponsorship": null,
    "current_work_authorization": null,
    "minimum_salary": null,
    "salary_currency": null,
    ...
  }
}
```

`null` means *"not specified — the system will not filter on this."*  
Only set values you explicitly want enforced.

---

## Step 5 — Validate the profile

```bash
uv run applyai profile validate
```

Expected output when ready:

```
Profile source: private
Schema validation: PASS
Required Documents:
  ✓ identity
  ✓ education
  ...
Profile is valid and complete.
```

Fix any errors reported before proceeding.

---

## Step 6 — Review what the AI will see

The AI pipeline receives the profile through a context builder — not raw JSON files.  
Only the fields relevant to matching and resume tailoring are sent.

To confirm what context the matcher will use, inspect the outreach evidence step in:

```
applyai prep run <job-id>
```

This is a dry-run — no external actions are taken.

---

## Step 7 — Never commit private data

`candidate/private/` is in `.gitignore`. Verify:

```bash
git check-ignore candidate/private/identity.json
```

Expected output: `candidate/private/identity.json` (ignored).

If `git status` shows any `candidate/private/` file as untracked or staged, **do not commit** until you understand why.

---

## What the system will never do

- Invent employment history, dates, or responsibilities
- Claim skills you have not documented
- Fabricate certifications or achievements
- Assume work authorization or visa status
- Submit applications without your explicit approval
- Send messages without your explicit approval
- Connect to LinkedIn, Gmail, Naukri, or any external account

---

## Schema reference

Full Pydantic schema: [`applyai/schemas/candidate.py`](../applyai/schemas/candidate.py)  
Example profiles: [`candidate/example/`](../candidate/example/)  
Synthetic test fixture: [`tests/fixtures/synthetic_private_profile/`](../tests/fixtures/synthetic_private_profile/)
