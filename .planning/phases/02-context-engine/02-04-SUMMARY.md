---
phase: 02-context-engine
plan: 04
subsystem: context-engine
tags: [profiles, obsidian, pydantic, yaml, filesystem]
dependency-graph:
  requires: []
  provides: [client-profile-loader, ClientProfile-model]
  affects: [02-05, 03-xx]
tech-stack:
  added: [pyyaml]
  patterns: [async-filesystem-io, frontmatter-parsing, dual-source-search]
key-files:
  created:
    - engine/context/profiles.py
  modified:
    - engine/requirements.txt
decisions:
  - id: D-0204-1
    decision: "Use pyyaml for frontmatter parsing instead of manual key:value parser"
    reason: "Reliable YAML parsing worth the dependency — handles edge cases"
  - id: D-0204-2
    decision: "Search client-profiles/ before Obsidian contacts (priority order)"
    reason: "Client-profiles has richer communication data; Obsidian is fallback"
  - id: D-0204-3
    decision: "Trim raw_content to 2000 chars for LLM context injection"
    reason: "Keeps token usage manageable while providing sufficient context"
metrics:
  duration: ~2 min
  completed: 2026-03-20
---

# Phase 2 Plan 4: Client Profile Loader Summary

**One-liner:** Async client profile loader searching client-profiles/ and Obsidian vault Contacts/ with YAML frontmatter parsing via pyyaml

## What Was Built

`engine/context/profiles.py` — an async profile loader that finds and parses client communication profiles from two filesystem locations:

1. `/opt/agency-workspace/client-profiles/*.md` — rich communication profiles with style tables, language profiles, behavioral patterns
2. `/opt/agency-workspace/obsidian-vault/Contacts/*.md` — Obsidian contact notes with frontmatter metadata

### Key Components

- **ClientProfile** (Pydantic BaseModel): slug, name, email, company, role, relationship, communication_style, formality, status, raw_content, source
- **load_client_profile(email, company)**: Async function searching both locations, returning first match or None
- **Frontmatter parser**: Uses `yaml.safe_load()` on `---` delimited blocks
- **CLI entry point**: `python -m context.profiles [email] [--company name]`

### Matching Logic

- **By email**: Case-insensitive search in frontmatter fields AND full text content
- **By company**: Matches against frontmatter `client`, `company`, `name`, and `slug` fields

## Verification Results

| Test | Result |
|------|--------|
| Import `load_client_profile, ClientProfile` | Pass |
| Load by email (brendan@acrepartner.com) | Returns ACRE Partner profile with comm style |
| Load by company ("Axel Towing") | Returns Elliott profile |
| Unknown email | Returns None, no crash |

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| 6adcea2 | feat(02-04): add client profile loader from Obsidian vault |

## Next Phase Readiness

- Profile loader ready for integration into context engine pipeline
- Other context plans (meeting notes, project context) can follow same pattern
- LLM prompt injection: use `raw_content` field for rich meeting context
