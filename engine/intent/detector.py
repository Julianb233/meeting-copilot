"""IntentDetector — two-stage pipeline for meeting transcript intent extraction.

Stage 1: Batch classify sentences (INFO/ACTION_ITEM/DECISION/FOLLOW_UP/QUESTION)
Stage 2: Extract structured intents from non-INFO sentences only
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

from .fallback_chain import FallbackChain, create_default_chain
from .models import ActionType, ClassifiedSentence, Intent, IntentBatch
from .prompts import classify_keywords, format_classify_prompt, format_extract_prompt

logger = logging.getLogger("copilot.intent")


class IntentDetector:
    """Two-stage intent detection pipeline.

    Stage 1 filters out INFO sentences (~80% of traffic) to save cost.
    Stage 2 extracts structured Intent objects from actionable sentences.
    """

    def __init__(self, chain: FallbackChain | None = None) -> None:
        self.chain = chain or create_default_chain()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_sentences(
        self,
        sentences: list[dict[str, Any]],
        known_projects: list[str] | None = None,
        attendee_names: list[str] | None = None,
    ) -> IntentBatch:
        """Run the two-stage intent detection pipeline.

        Args:
            sentences: List of dicts with "text" and "speaker" keys.
            known_projects: Project names to help LLM match intents.
            attendee_names: Attendee names for assignee detection.

        Returns:
            IntentBatch with classifications and extracted intents.
        """
        start = time.monotonic()
        known_projects = known_projects or []
        attendee_names = attendee_names or []

        # Stage 1: Batch classification
        classifications = await self._classify_batch(sentences)

        # Stage 2: Extract intents from actionable sentences only
        actionable = [
            (s, c)
            for s, c in zip(sentences, classifications)
            if c.classification != "INFO"
        ]

        intents: list[Intent] = []
        model_used = "keywords"

        if actionable:
            intents, model_used = await self._extract_intents(
                [s for s, _ in actionable],
                known_projects,
                attendee_names,
            )

        elapsed = (time.monotonic() - start) * 1000
        logger.info(
            "Processed %d sentences -> %d actionable -> %d intents (%.0fms, model=%s)",
            len(sentences),
            len(actionable),
            len(intents),
            elapsed,
            model_used,
        )

        return IntentBatch(
            intents=intents,
            classifications=classifications,
            model_used=model_used,
            processing_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Stage 1: Batch classification
    # ------------------------------------------------------------------

    async def _classify_batch(
        self, sentences: list[dict[str, Any]]
    ) -> list[ClassifiedSentence]:
        """Classify sentences via LLM, falling back to keywords."""
        prompt = format_classify_prompt(sentences)
        response_text, _model = await self.chain.call(prompt)

        if response_text is not None:
            parsed = self._parse_json_response(response_text)
            if parsed is not None:
                return self._build_classifications(sentences, parsed)

        # Keyword fallback
        return [
            ClassifiedSentence(
                index=i,
                text=s["text"],
                speaker=s.get("speaker_name", s.get("speaker", "Unknown")),
                classification=classify_keywords(s["text"]),
            )
            for i, s in enumerate(sentences)
        ]

    def _build_classifications(
        self, sentences: list[dict[str, Any]], parsed: list[dict[str, Any]]
    ) -> list[ClassifiedSentence]:
        """Build ClassifiedSentence list from LLM JSON response."""
        # Build lookup: index -> classification
        lookup: dict[int, str] = {}
        for item in parsed:
            idx = item.get("index")
            cls = item.get("classification", "INFO")
            if idx is not None:
                lookup[int(idx)] = cls

        return [
            ClassifiedSentence(
                index=i,
                text=s["text"],
                speaker=s.get("speaker_name", s.get("speaker", "Unknown")),
                classification=lookup.get(i, "INFO"),
            )
            for i, s in enumerate(sentences)
        ]

    # ------------------------------------------------------------------
    # Stage 2: Structured intent extraction
    # ------------------------------------------------------------------

    _CLASSIFICATION_TO_ACTION: dict[str, ActionType] = {
        "ACTION_ITEM": ActionType.GENERAL_TASK,
        "DECISION": ActionType.DECISION,
        "FOLLOW_UP": ActionType.FOLLOW_UP,
        "QUESTION": ActionType.GENERAL_TASK,
    }

    async def _extract_intents(
        self,
        sentences: list[dict[str, Any]],
        known_projects: list[str],
        attendee_names: list[str],
    ) -> tuple[list[Intent], str]:
        """Extract structured intents from actionable sentences."""
        prompt = format_extract_prompt(sentences, known_projects, attendee_names)
        response_text, model_name = await self.chain.call(prompt)

        if response_text is not None:
            parsed = self._parse_json_response(response_text)
            if parsed is not None:
                intents: list[Intent] = []
                for item in parsed:
                    try:
                        intents.append(Intent.model_validate(item))
                    except Exception:
                        logger.debug("Skipping malformed intent item: %s", item)
                return intents, model_name

        # Heuristic fallback when all LLM providers fail
        return self._heuristic_intents(sentences), "keywords"

    def _heuristic_intents(self, sentences: list[dict[str, Any]]) -> list[Intent]:
        """Create basic intents from keyword-classified sentences."""
        intents: list[Intent] = []
        for s in sentences:
            classification = classify_keywords(s["text"])
            action_type = self._CLASSIFICATION_TO_ACTION.get(classification)
            if action_type is None:
                continue
            intents.append(
                Intent(
                    action_type=action_type,
                    target=s["text"][:80],
                    urgency="soon",
                    details=s["text"],
                    confidence=0.5,
                    source_text=s["text"],
                    speaker=s.get("speaker_name", s.get("speaker", "Unknown")),
                    requires_agent=False,
                )
            )
        return intents

    # ------------------------------------------------------------------
    # JSON parsing helper
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(text: str) -> list[dict[str, Any]] | None:
        """Parse a JSON array from LLM response text.

        Handles markdown code fences and partial JSON gracefully.
        """
        # Strip code fences if present
        text = text.strip()
        fence_match = re.match(
            r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", text, re.DOTALL
        )
        if fence_match:
            text = fence_match.group(1).strip()

        # Try direct parse
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # Try extracting array from surrounding text
        array_match = re.search(r"\[.*\]", text, re.DOTALL)
        if array_match:
            try:
                result = json.loads(array_match.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        return None


# ---------------------------------------------------------------------------
# CLI test harness
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    async def _main() -> None:
        detector = IntentDetector()
        sentences = [
            {"text": "We need to build a landing page for the new client", "speaker": "Julian", "speaker_name": "Julian"},
            {"text": "Yeah the weather is great today", "speaker": "Bob", "speaker_name": "Bob"},
            {"text": "Let's fix the login bug on the ACRE site", "speaker": "Julian", "speaker_name": "Julian"},
            {"text": "We decided to use Stripe for payments", "speaker": "Sarah", "speaker_name": "Sarah"},
        ]
        result = await detector.process_sentences(
            sentences,
            known_projects=["ACRE Partner", "Meeting Copilot"],
        )
        print(json.dumps(result.model_dump(), indent=2, default=str))

    asyncio.run(_main())
