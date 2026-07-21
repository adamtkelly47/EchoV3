"""Policies decide; they never persist data or make network calls
(CONSTITUTION.md: Policy) — same convention as domains/approvals/policies.py.
This is also where Google's raw JSON (returned as plain dicts by
domains.calendar.service.CalendarProviderPort, matching the
domains/approvals/service.py WriteAdapter precedent of providers speaking
in primitives, not domain-owned types, so providers/ never has to import
domains/) gets translated into Calendar's own typed schemas — the one place
that translation happens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from domains.calendar.errors import CalendarOAuthStateInvalidError
from domains.calendar.models import EventStatus
from domains.calendar.schemas import CalendarCredential, CalendarEvent, CalendarInfo, FreeBusyPeriod


def needs_refresh(
    credential: CalendarCredential, now: datetime, buffer: timedelta = timedelta(minutes=5)
) -> bool:
    """Refresh a little before actual expiry, not exactly at it — avoids a
    request racing the expiry boundary and failing with a stale token."""
    return now >= (credential.access_token_expires_at - buffer)


def is_recurring_instance(recurring_event_id: str | None) -> bool:
    return recurring_event_id is not None


def is_stale(synced_at: datetime, now: datetime, max_age: timedelta) -> bool:
    return now - synced_at > max_age


def _parse_rfc3339(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_event_datetime(node: dict[str, Any]) -> tuple[datetime, bool, str | None]:
    """A Google event's start/end node is either `{"date": "yyyy-mm-dd"}`
    (all-day) or `{"dateTime": "...", "timeZone": "..."}` (timed) — never
    both (developers.google.com/calendar/api/v3/reference/events, verified
    live). Returns (utc_datetime, all_day, timezone_name)."""
    if "date" in node:
        naive = datetime.strptime(node["date"], "%Y-%m-%d")
        return naive.replace(tzinfo=UTC), True, None
    parsed = _parse_rfc3339(node["dateTime"])
    return parsed.astimezone(UTC), False, node.get("timeZone")


def parse_event_status(raw: dict[str, Any]) -> EventStatus:
    try:
        return EventStatus(raw.get("status", "confirmed"))
    except ValueError:
        return EventStatus.CONFIRMED  # an unrecognized status is not a reason to fail the read


def parse_is_busy(raw: dict[str, Any]) -> bool:
    return bool(raw.get("transparency", "opaque") != "transparent")


def parse_free_busy(raw: dict[str, Any], calendar_id: str) -> list[FreeBusyPeriod]:
    calendar_data = raw.get("calendars", {}).get(calendar_id, {})
    return [
        FreeBusyPeriod(start=_parse_rfc3339(period["start"]), end=_parse_rfc3339(period["end"]))
        for period in calendar_data.get("busy", [])
    ]


def parse_event(
    raw: dict[str, Any], *, user_id: str, calendar_id: str, synced_at: datetime
) -> CalendarEvent:
    """The one place a raw Google event dict becomes a domain CalendarEvent
    — combines the datetime/status/busy translations above."""
    start, start_all_day, timezone = parse_event_datetime(raw["start"])
    end, _, _ = parse_event_datetime(raw["end"])
    return CalendarEvent(
        user_id=user_id,
        provider_event_id=raw["id"],
        calendar_id=calendar_id,
        summary=raw.get("summary", "(no title)"),
        description=raw.get("description"),
        start=start,
        end=end,
        all_day=start_all_day,
        timezone=timezone,
        status=parse_event_status(raw),
        is_busy=parse_is_busy(raw),
        recurring_event_id=raw.get("recurringEventId"),
        html_link=raw.get("htmlLink"),
        synced_at=synced_at,
    )


def parse_calendar_list(raw: dict[str, Any]) -> list[CalendarInfo]:
    return [
        CalendarInfo(
            calendar_id=item["id"],
            summary=item.get("summary", item["id"]),
            primary=item.get("primary", False),
            time_zone=item.get("timeZone"),
        )
        for item in raw.get("items", [])
    ]


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_oauth_state(user_id: str, nonce: str, now: datetime, secret: str) -> str:
    """Docs/SECURITY.md: "Redirect target validation on OAuth callback
    flows." A signed, timestamped token rather than a server-side session
    store — no new stateful infrastructure needed, and a forged or replayed
    (past max_age) state is rejected by verify_oauth_state below. The
    timestamp is encoded as a POSIX timestamp, not ISO 8601 — ISO 8601
    contains colons, which would collide with the ':'-delimited payload
    format below."""
    payload = f"{user_id}:{nonce}:{now.timestamp()}"
    signature = _sign(payload, secret)
    token = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")


def verify_oauth_state(
    state: str, secret: str, now: datetime, max_age: timedelta = timedelta(minutes=10)
) -> str:
    """Returns the user_id embedded in a valid, fresh, correctly-signed
    state token — raises CalendarOAuthStateInvalidError otherwise (bad
    signature, tampered payload, or expired)."""
    try:
        decoded = base64.urlsafe_b64decode(state.encode("utf-8")).decode("utf-8")
        user_id, nonce, timestamp_str, signature = decoded.rsplit(":", 3)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CalendarOAuthStateInvalidError("malformed OAuth state") from exc

    payload = f"{user_id}:{nonce}:{timestamp_str}"
    expected = _sign(payload, secret)
    if not hmac.compare_digest(signature, expected):
        raise CalendarOAuthStateInvalidError("OAuth state signature mismatch")

    try:
        issued_at = datetime.fromtimestamp(float(timestamp_str), tz=UTC)
    except ValueError as exc:
        raise CalendarOAuthStateInvalidError("malformed OAuth state timestamp") from exc
    if now - issued_at > max_age:
        raise CalendarOAuthStateInvalidError("OAuth state expired")

    return user_id
