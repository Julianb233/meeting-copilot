"""Context engine modules for meeting attendee and environment enrichment."""

from context.assembler import assemble_meeting_context
from context.models import (
    AttendeeContext,
    AttendeeIdentity,
    ClientProfile,
    LinearIssue,
    LinearProject,
    TranscriptSummary,
    UnifiedMeetingContext,
)
