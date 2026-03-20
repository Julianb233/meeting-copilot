"""Context engine modules for meeting attendee and environment enrichment."""

from context.assembler import (
    AttendeeContext,
    UnifiedMeetingContext,
    assemble_meeting_context,
)
from context.contacts import AttendeeIdentity
from context.fireflies import TranscriptSummary
from context.linear_client import LinearIssue, LinearProject
from context.profiles import ClientProfile
