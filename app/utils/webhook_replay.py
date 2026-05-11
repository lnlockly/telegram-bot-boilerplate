"""Webhook replay protection helpers.

Records (provider, event_id) of every webhook we've already processed and
exposes a freshness check on provider-supplied timestamps. Used by every
payment receiver that exposes a stable event id (yookassa, cloudpayments,
cryptobot, ...). See SECURITY_AUDIT.md HIGH #8 for context.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ProcessedWebhookEvent


logger = structlog.get_logger(__name__)


async def claim_webhook_event(
    db: AsyncSession,
    provider: str,
    event_id: str,
) -> bool:
    """Insert (provider, event_id). Return True the first time, False on duplicate.

    Callers should short-circuit (return 200 OK without crediting) when False is
    returned. The unique constraint ``uq_processed_webhook_events_provider_event``
    is the DB-level guarantee — application-level race losers raise IntegrityError
    which we swallow and treat as duplicate.
    """
    if not event_id:
        # Caller should add a TODO and skip if no stable id is available.
        return True

    try:
        db.add(ProcessedWebhookEvent(provider=provider, event_id=str(event_id)))
        await db.flush()
        return True
    except IntegrityError:
        await db.rollback()
        logger.info(
            'Webhook replay detected — событие уже было обработано',
            provider=provider,
            event_id=str(event_id),
        )
        return False


def _parse_iso_timestamp(value: Any) -> datetime | None:
    """Best-effort parser for ISO 8601 timestamps supplied by webhooks."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OSError, OverflowError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Trailing Z is not parsed by fromisoformat on older pythons.
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def is_event_fresh(
    event_timestamp: Any,
    max_age_seconds: int = 300,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if ``event_timestamp`` is within ``max_age_seconds`` of now.

    Used as defence-in-depth alongside replay storage: rejects events older
    than the freshness window to limit replay value of leaked logs/captures.
    Permissive when the timestamp can't be parsed (returns True) to avoid
    breaking providers that don't supply a usable timestamp — callers in that
    case should rely on ``claim_webhook_event`` and TODO their way to a real
    fix.
    """
    parsed = _parse_iso_timestamp(event_timestamp)
    if parsed is None:
        return True
    current = (now or datetime.now(UTC)).astimezone(timezone.utc)
    delta = current - parsed.astimezone(timezone.utc)
    return abs(delta) <= timedelta(seconds=max_age_seconds)
