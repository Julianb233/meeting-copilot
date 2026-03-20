---
phase: 03-intent-orchestration
plan: 01
subsystem: intent-detection
tags: [llm, gemini, fallback-chain, pydantic, classification, httpx]
dependency-graph:
  requires: [01-02]
  provides: [intent-detector, fallback-chain, intent-models]
  affects: [03-02, 03-03, 03-04]
tech-stack:
  added: []
  patterns: [multi-model-fallback, two-stage-pipeline, async-httpx]
key-files:
  created:
    - engine/intent/__init__.py
    - engine/intent/models.py
    - engine/intent/prompts.py
    - engine/intent/fallback_chain.py
    - engine/intent/detector.py
  modified: []
decisions:
  - id: D-0301-1
    decision: "Gemini first in fallback chain (Anthropic has zero credits)"
    reason: "Gemini free tier works; Anthropic billing separate from fleet budget"
  - id: D-0301-2
    decision: "details field defaults to empty string for LLM null tolerance"
    reason: "Gemini sometimes returns null for details; Pydantic validation rejects None for str"
metrics:
  duration: "3m 23s"
  completed: 2026-03-20
---

# Phase 3 Plan 1: Intent Detector with Multi-Model Fallback Summary

**Two-stage intent pipeline: batch classify via Gemini then extract structured intents from actionable items only, with keyword fallback.**

## What Was Built

### Task 1: Intent Models, Prompts, and Fallback Chain
- **ActionType** enum with 12 action types (create_issue through general_task)
- **Intent** Pydantic model with action_type, target, urgency, project, confidence, requires_agent
- **ClassifiedSentence** and **IntentBatch** models for pipeline output
- **Prompt templates**: `CLASSIFY_BATCH_PROMPT` for 5-category classification, `EXTRACT_INTENTS_PROMPT` for structured extraction
- **classify_keywords()** ported from meeting-watcher.py with identical keyword lists
- **FallbackChain** with ModelHealth cooldown (2+ consecutive failures = 5min cooldown)
- Three async provider functions (Gemini, Anthropic, OpenAI) using httpx
- `create_default_chain()` factory: Gemini -> Anthropic -> OpenAI (only includes configured keys)
- `strip_code_fences()` regex to handle Gemini markdown wrapping

### Task 2: IntentDetector with Two-Stage Pipeline
- **Stage 1**: Batch classify sentences into INFO/ACTION_ITEM/DECISION/FOLLOW_UP/QUESTION
- **Stage 2**: Extract structured Intent objects from non-INFO sentences only (~80% filtered)
- `_parse_json_response()` handles code fences and partial JSON extraction
- `_heuristic_intents()` fallback creates basic intents from keyword classification
- CLI test harness with `if __name__ == "__main__"` block

## Verification Results

- All imports work cleanly from engine/ directory
- Keyword classifier: "We need to build..." -> ACTION_ITEM, "weather is nice" -> INFO, "We decided..." -> DECISION
- ModelHealth: available initially, unavailable after 2 failures
- IntentDetector end-to-end: 4 sentences -> 3 actionable -> 2 structured intents (Gemini model)
- Gemini correctly identified build_feature and fix_bug action types with high confidence

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Template curly brace escaping in classify prompt**
- **Found during:** Task 2 verification
- **Issue:** `CLASSIFY_BATCH_PROMPT` contained literal JSON example with `{"index": 0, ...}` which Python's `.format()` interpreted as template variables, raising KeyError
- **Fix:** Escaped curly braces in the JSON example: `{{"index": 0, ...}}`
- **Files modified:** engine/intent/prompts.py
- **Commit:** d5ab843

**2. [Rule 1 - Bug] Intent details field null tolerance**
- **Found during:** Task 2 verification with Gemini
- **Issue:** Gemini returned `null` for the `details` field in some intents, but Pydantic requires `str` (not `None`), causing model_validate to skip valid intents
- **Fix:** Changed `details: str` to `details: str = ""` with empty string default
- **Files modified:** engine/intent/models.py
- **Commit:** d5ab843

## Decisions Made

| ID | Decision | Rationale |
|----|----------|-----------|
| D-0301-1 | Gemini first in fallback chain | Anthropic has zero credits; Gemini free tier is functional |
| D-0301-2 | details field defaults to empty string | Gemini returns null for details; need graceful handling |

## Next Phase Readiness

- Intent detector ready for integration with WebSocket handler (03-02)
- FallbackChain can be shared by routing module (03-03, 03-04)
- No blockers for downstream plans
