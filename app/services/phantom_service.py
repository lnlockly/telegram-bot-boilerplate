"""Phantom user claiming and merging.

Phantom users were originally created during guest landing purchases. The
boilerplate keeps the basic claim/merge plumbing so callers don't break,
but all subscription/RemnaWave sync logic has been removed.

TODO(boilerplate): if your product has external resources to update when a
phantom is claimed/merged, plug them in here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.rbac import AuditLogCRUD
from app.database.crud.user import get_user_by_telegram_id
from app.database.models import User, UserStatus
from app.services.account_merge_service import execute_merge
from app.utils.user_utils import generate_unique_referral_code
from app.utils.validators import sanitize_telegram_name


logger = structlog.get_logger(__name__)


async def claim_phantom(
    db: AsyncSession,
    phantom: User,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language: str,
    referrer_id: int | None,
) -> tuple[bool, User | None]:
    """Claim a phantom user by backfilling Telegram profile data."""
    phantom.telegram_id = telegram_id
    phantom.username = username
    phantom.first_name = sanitize_telegram_name(first_name)
    phantom.last_name = sanitize_telegram_name(last_name)
    phantom.language = language
    phantom.status = UserStatus.ACTIVE.value
    if referrer_id and referrer_id != phantom.id:
        phantom.referred_by_id = referrer_id
    if not phantom.referral_code:
        phantom.referral_code = await generate_unique_referral_code(db, telegram_id)
    phantom.updated_at = datetime.now(UTC)
    phantom.last_activity = datetime.now(UTC)

    try:
        async with db.begin_nested():
            await AuditLogCRUD.create(
                db,
                user_id=phantom.id,
                action='phantom_claimed',
                resource_type='user',
                resource_id=str(phantom.id),
                details={'telegram_id': telegram_id, 'username': username},
                status='success',
            )
    except Exception:
        logger.warning('Failed to write phantom claim audit log', phantom_id=phantom.id, exc_info=True)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await get_user_by_telegram_id(db, telegram_id)
        return False, existing

    return True, phantom


async def merge_phantom_into_user(
    db: AsyncSession,
    phantom: User,
    active_user: User,
) -> bool:
    """Merge phantom user into active user using the account merge service."""
    keep_from: Literal['primary', 'secondary'] = 'primary'
    await execute_merge(
        db,
        primary_user_id=active_user.id,
        secondary_user_id=phantom.id,
        keep_subscription_from=keep_from,
        provider='phantom_merge',
    )
    try:
        async with db.begin_nested():
            await AuditLogCRUD.create(
                db,
                user_id=active_user.id,
                action='phantom_merged',
                resource_type='user',
                resource_id=str(phantom.id),
                details={
                    'phantom_id': phantom.id,
                    'active_user_id': active_user.id,
                    'phantom_username': phantom.username,
                },
                status='success',
            )
    except Exception:
        logger.warning(
            'Failed to write phantom merge audit log',
            phantom_id=phantom.id,
            active_user_id=active_user.id,
            exc_info=True,
        )
    return False


async def sync_remnawave_after_phantom_merge(db: AsyncSession, user: User) -> None:
    """No-op in boilerplate (RemnaWave integration removed)."""
    return
