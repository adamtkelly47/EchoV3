"""Email's own vocabulary, kept independent of any single provider's raw
strings (Docs/DOMAIN_OWNERSHIP.md: Email owns Email Classification, Inbox
State) — same convention as domains/calendar/models.py. `EmailCategory` is
Echo's own local-model-assigned classification (PROMPT.md Phase 20 implement
item 9: "local classification"; section 12.1 item 11: "classifying emails"
is a named Ollama workload), never Gmail's own category labels — those stay
provider-specific and live in `label_ids` on the domain schema untouched.
`EmailLabel` is the small subset of Gmail's own system label ids Echo's
write capabilities touch directly (archive/label/trash), verified against
Gmail API's documented system labels (developers.google.com/gmail/api/guides/labels).
"""

from __future__ import annotations

from enum import Enum


class EmailCategory(str, Enum):
    ACTION_NEEDED = "action_needed"
    AWAITING_RESPONSE = "awaiting_response"
    INFORMATIONAL = "informational"
    PROMOTIONAL = "promotional"
    OTHER = "other"


class EmailLabel(str, Enum):
    INBOX = "INBOX"
    UNREAD = "UNREAD"
    STARRED = "STARRED"
    IMPORTANT = "IMPORTANT"
    SENT = "SENT"
    DRAFT = "DRAFT"
    TRASH = "TRASH"
    SPAM = "SPAM"
