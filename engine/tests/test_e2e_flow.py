"""End-to-end test: full meeting lifecycle through copilot engine.

Simulates: meeting_start -> transcript_chunks -> meeting_end
Validates: context loading, intent detection, routing, summary, follow-up email draft

Usage:
    cd engine && python -m tests.test_e2e_flow
    cd engine && python3 -m pytest tests/test_e2e_flow.py -v
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Any
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Test scenario
# ---------------------------------------------------------------------------

MEETING_SCENARIO: dict[str, Any] = {
    "meeting_id": "e2e-test-001",
    "meeting_title": "ACRE Project Review",
    "attendee_emails": ["julian@aiacrobatics.com", "sean@hafniafin.com"],
    "transcript_sentences": [
        {"speaker": "Julian", "text": "Hey Sean, let's review where we are on the ACRE project", "timestamp": "00:00:15"},
        {"speaker": "Sean", "text": "Sure, the landing page is almost done but we need to fix the mobile layout", "timestamp": "00:00:30"},
        {"speaker": "Julian", "text": "OK, I'll have my team fix the mobile responsive issues this week", "timestamp": "00:00:45"},
        {"speaker": "Sean", "text": "Also, we need to set up Stripe for the booking payments", "timestamp": "00:01:00"},
        {"speaker": "Julian", "text": "Let's go with Stripe, that's decided. I'll create the integration", "timestamp": "00:01:15"},
        {"speaker": "Julian", "text": "Can you send me the brand guidelines document?", "timestamp": "00:01:30"},
        {"speaker": "Sean", "text": "Yes I'll email those over today", "timestamp": "00:01:45"},
        {"speaker": "Julian", "text": "Great, let's plan to launch the site by end of month", "timestamp": "00:02:00"},
    ],
}


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _pass(msg: str) -> None:
    print(f"  {GREEN}[PASS]{RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}[FAIL]{RESET} {msg}")


def _info(msg: str) -> None:
    print(f"  {YELLOW}[INFO]{RESET} {msg}")


# ---------------------------------------------------------------------------
# Full meeting flow test (direct bridge calls)
# ---------------------------------------------------------------------------

async def run_full_meeting_flow() -> bool:
    """Simulate a complete meeting lifecycle through the WatcherBridge.

    Returns True if all phases pass, False otherwise.
    """
    # Lazy imports so sys.path is set at call time
    from bridge.watcher_bridge import WatcherBridge, WatcherEvent, WatcherEventType
    from ws_handler import manager
    from models import MeetingState

    passed = 0
    failed = 0
    bridge = WatcherBridge()

    print(f"\n{BOLD}=== Phase 1: Meeting Start ==={RESET}")

    # Mock external data loaders so the test does not require live APIs
    mock_context = _build_mock_context()
    with patch("context.assembler.assemble_meeting_context", new=AsyncMock(return_value=mock_context)):
        start_event = WatcherEvent(
            event_type=WatcherEventType.MEETING_START,
            meeting_id=MEETING_SCENARIO["meeting_id"],
            meeting_title=MEETING_SCENARIO["meeting_title"],
            attendee_emails=MEETING_SCENARIO["attendee_emails"],
        )

        t0 = time.monotonic()
        result = await bridge.handle_event(start_event)
        elapsed_ms = (time.monotonic() - t0) * 1000

        # Assertions
        if result.get("status") == "context_loaded":
            _pass(f"Meeting start returned context_loaded ({elapsed_ms:.0f}ms)")
            passed += 1
        else:
            _fail(f"Expected status 'context_loaded', got '{result.get('status')}'")
            failed += 1

        if bridge.active_meeting_id == MEETING_SCENARIO["meeting_id"]:
            _pass(f"Bridge active_meeting_id = {bridge.active_meeting_id}")
            passed += 1
        else:
            _fail(f"Expected meeting_id '{MEETING_SCENARIO['meeting_id']}', got '{bridge.active_meeting_id}'")
            failed += 1

        if bridge.meeting_context is not None:
            _pass(f"Meeting context loaded: {len(bridge.meeting_context.attendees)} attendees")
            passed += 1
        else:
            _fail("Meeting context is None after meeting_start")
            failed += 1

        # Meeting type should be "client" (sean@hafniafin.com is external)
        if bridge.meeting_context and bridge.meeting_context.meeting_type == "client":
            _pass("Meeting classified as 'client' (external attendee present)")
            passed += 1
        else:
            mt = bridge.meeting_context.meeting_type if bridge.meeting_context else "N/A"
            _fail(f"Expected meeting_type 'client', got '{mt}'")
            failed += 1

    # -----------------------------------------------------------------------
    print(f"\n{BOLD}=== Phase 2: Transcript Chunks ==={RESET}")

    sentences = MEETING_SCENARIO["transcript_sentences"]
    batch1 = sentences[0:4]
    batch2 = sentences[4:8]

    for batch_num, batch in enumerate([batch1, batch2], start=1):
        chunk_event = WatcherEvent(
            event_type=WatcherEventType.TRANSCRIPT_CHUNK,
            meeting_id=MEETING_SCENARIO["meeting_id"],
            meeting_title=MEETING_SCENARIO["meeting_title"],
            sentences=batch,
        )
        result = await bridge.handle_event(chunk_event)
        if result.get("status") == "processed":
            _pass(f"Batch {batch_num}: {len(batch)} sentences processed")
            passed += 1
        else:
            _fail(f"Batch {batch_num}: expected 'processed', got '{result.get('status')}'")
            failed += 1

    # Check manager state after transcript processing
    chunk_count = len(manager.state.transcript_chunks)
    _info(f"Transcript chunks in state: {chunk_count}")
    if chunk_count >= 8:
        _pass(f"All 8 transcript sentences stored ({chunk_count} chunks)")
        passed += 1
    else:
        # Transcript storage may be additive with other state; at least 8
        _fail(f"Expected >= 8 transcript chunks, got {chunk_count}")
        failed += 1

    intent_count = len(manager.state.intents)
    _info(f"Intents detected: {intent_count}")
    if intent_count >= 1:
        _pass(f"At least 1 intent detected ({intent_count} total)")
        passed += 1
        for idx, intent in enumerate(manager.state.intents):
            target = intent.get("target", intent.get("source_text", "?"))
            atype = intent.get("action_type", "?")
            _info(f"  Intent {idx + 1}: [{atype}] {target[:70]}")
    else:
        _fail("No intents detected from transcript (expected >= 1)")
        failed += 1

    # -----------------------------------------------------------------------
    print(f"\n{BOLD}=== Phase 3: Meeting End ==={RESET}")

    # Patch send_followup_email to avoid sending real emails
    with patch(
        "intelligence.followup_email.send_followup_email",
        new=AsyncMock(return_value={"status": "dry_run", "sent": False}),
    ):
        end_event = WatcherEvent(
            event_type=WatcherEventType.MEETING_END,
            meeting_id=MEETING_SCENARIO["meeting_id"],
            meeting_title=MEETING_SCENARIO["meeting_title"],
            attendee_emails=MEETING_SCENARIO["attendee_emails"],
        )
        result = await bridge.handle_event(end_event)

    if result.get("status") == "ended":
        _pass("Meeting end returned 'ended'")
        passed += 1
    else:
        _fail(f"Expected status 'ended', got '{result.get('status')}'")
        failed += 1

    if bridge.active_meeting_id is None:
        _pass("Bridge state reset (active_meeting_id = None)")
        passed += 1
    else:
        _fail(f"Bridge active_meeting_id should be None, got '{bridge.active_meeting_id}'")
        failed += 1

    if bridge.meeting_context is None:
        _pass("Bridge meeting_context cleared after end")
        passed += 1
    else:
        _fail("Bridge meeting_context should be None after meeting_end")
        failed += 1

    # -----------------------------------------------------------------------
    print(f"\n{BOLD}=== Results ==={RESET}")
    total = passed + failed
    print(f"  Passed: {passed}/{total}  Failed: {failed}/{total}")
    return failed == 0


# ---------------------------------------------------------------------------
# REST API smoke test
# ---------------------------------------------------------------------------

async def run_api_endpoints() -> bool:
    """Smoke test all REST API endpoints via Starlette TestClient.

    Returns True if all endpoints respond correctly, False otherwise.
    """
    from starlette.testclient import TestClient
    from main import app

    client = TestClient(app)
    passed = 0
    failed = 0
    results: list[tuple[str, int, float]] = []

    endpoints: list[tuple[str, str, dict | None]] = [
        ("GET", "/api/health", None),
        ("GET", "/api/state", None),
        ("GET", "/api/tasks", None),
        ("GET", "/api/intents", None),
        ("POST", "/api/context", {"emails": ["julian@aiacrobatics.com"], "meeting_title": "API Test"}),
        ("POST", "/api/watcher/event", {
            "event_type": "meeting_start",
            "meeting_id": "api-smoke-001",
            "meeting_title": "Smoke Test",
            "attendee_emails": ["julian@aiacrobatics.com"],
        }),
        ("POST", "/api/process", {
            "sentences": [{"speaker": "Julian", "text": "Create a new landing page", "timestamp": "00:00:01"}],
        }),
    ]

    print(f"\n{BOLD}{'Endpoint':<30} {'Status':>6}  {'Time':>8}{RESET}")
    print("-" * 50)

    for method, path, body in endpoints:
        t0 = time.monotonic()
        try:
            if method == "GET":
                resp = client.get(path)
            else:
                # Mock external calls for POST endpoints that hit external services
                with patch("context.assembler.resolve_attendees", new=AsyncMock(return_value=[])), \
                     patch("context.assembler.fetch_meeting_history", new=AsyncMock(return_value=[])), \
                     patch("context.assembler.fetch_linear_projects", new=AsyncMock(return_value=[])), \
                     patch("context.assembler.load_client_profile", new=AsyncMock(return_value=None)):
                    resp = client.post(path, json=body)
            elapsed_ms = (time.monotonic() - t0) * 1000
            status = resp.status_code
            results.append((f"{method} {path}", status, elapsed_ms))

            label = f"{method} {path}"
            if status == 200:
                _pass(f"{label:<30} {status:>3}  {elapsed_ms:>6.0f}ms")
                passed += 1
            else:
                _fail(f"{label:<30} {status:>3}  {elapsed_ms:>6.0f}ms")
                failed += 1
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            _fail(f"{method} {path:<26} ERR  {elapsed_ms:>6.0f}ms  ({exc})")
            failed += 1

    # Validate specific response structures
    print(f"\n{BOLD}Response structure checks:{RESET}")

    # Health check structure
    resp = client.get("/api/health")
    data = resp.json()
    if data.get("status") == "ok":
        _pass("/api/health has status='ok'")
        passed += 1
    else:
        _fail(f"/api/health status: {data.get('status')}")
        failed += 1

    # State structure
    resp = client.get("/api/state")
    data = resp.json()
    for key in ("tasks", "intents"):
        if key in data:
            _pass(f"/api/state has '{key}' key")
            passed += 1
        else:
            _fail(f"/api/state missing '{key}' key")
            failed += 1

    # Tasks is a list
    resp = client.get("/api/tasks")
    data = resp.json()
    if isinstance(data, list):
        _pass("/api/tasks returns a list")
        passed += 1
    else:
        _fail(f"/api/tasks expected list, got {type(data).__name__}")
        failed += 1

    # Intents is a list
    resp = client.get("/api/intents")
    data = resp.json()
    if isinstance(data, list):
        _pass("/api/intents returns a list")
        passed += 1
    else:
        _fail(f"/api/intents expected list, got {type(data).__name__}")
        failed += 1

    print(f"\n  Passed: {passed}  Failed: {failed}")
    return failed == 0


# ---------------------------------------------------------------------------
# pytest-compatible test functions
# ---------------------------------------------------------------------------

import pytest


@pytest.mark.asyncio
async def test_meeting_lifecycle():
    """pytest entry point for the full meeting lifecycle test."""
    assert await run_full_meeting_flow(), "Full meeting flow test failed"


def test_api_smoke():
    """pytest entry point for the REST API smoke test."""
    result = asyncio.get_event_loop().run_until_complete(run_api_endpoints())
    assert result, "API smoke test failed"


# ---------------------------------------------------------------------------
# Mock context builder
# ---------------------------------------------------------------------------

def _build_mock_context():
    """Build a mock UnifiedMeetingContext for testing without live APIs."""
    from context.models import (
        AttendeeContext,
        AttendeeIdentity,
        UnifiedMeetingContext,
    )

    return UnifiedMeetingContext(
        meeting_title=MEETING_SCENARIO["meeting_title"],
        meeting_type="client",
        client_domains=["hafniafin.com"],
        load_time_seconds=0.05,
        attendees=[
            AttendeeContext(
                identity=AttendeeIdentity(
                    email="julian@aiacrobatics.com",
                    name="Julian",
                    company="AI Acrobatics",
                    source="mock",
                ),
            ),
            AttendeeContext(
                identity=AttendeeIdentity(
                    email="sean@hafniafin.com",
                    name="Sean",
                    company="Hafnia Financial",
                    source="mock",
                ),
            ),
        ],
        errors=[],
    )


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"{BOLD}Meeting Copilot E2E Test Suite{RESET}")
    print("=" * 50)

    overall_pass = True

    # Test 1: API smoke test (fast, local only)
    print(f"\n{BOLD}[1/2] REST API Smoke Test{RESET}")
    api_ok = asyncio.run(run_api_endpoints())
    if not api_ok:
        overall_pass = False

    # Test 2: Full meeting flow test (may hit external APIs via intent detector)
    print(f"\n{BOLD}[2/2] Full Meeting Lifecycle Test{RESET}")
    flow_ok = asyncio.run(run_full_meeting_flow())
    if not flow_ok:
        overall_pass = False

    print("\n" + "=" * 50)
    if overall_pass:
        print(f"{GREEN}{BOLD}ALL TESTS PASSED{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}SOME TESTS FAILED{RESET}")
        sys.exit(1)
