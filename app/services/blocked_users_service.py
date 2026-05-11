"""Service for detecting users that have blocked the bot.

VPN/Remnawave-specific cleanup paths have been removed. The service can
still scan users, mark them as blocked, or wipe them from the database
along with their generic associated data.

TODO(boilerplate): if your product has external resources to revoke when a
user is removed, plug them into ``cleanup_blocked_users``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AdvertisingCampaignRegistration,
    ButtonClickLog,
    CabinetRefreshToken,
    CloudPaymentsPayment,
    ContestAttempt,
    CryptoBotPayment,
    DiscountOffer,
    FreekassaPayment,
    HeleketPayment,
    KassaAiPayment,
    MulenPayPayment,
    Pal24Payment,
    PlategaPayment,
    PollResponse,
    PromoCodeUse,
    ReferralContestEvent,
    ReferralEarning,
    SentNotification,
    Ticket,
    TicketMessage,
    TicketNotification,
    Transaction,
    User,
    UserPromoGroup,
    UserStatus,
    WataPayment,
    WheelSpin,
    WithdrawalRequest,
    YooKassaPayment,
)


logger = structlog.get_logger(__name__)


class BlockCheckStatus(Enum):
    BLOCKED = 'blocked'
    ACTIVE = 'active'
    NO_TELEGRAM_ID = 'no_telegram_id'
    ERROR = 'error'


class BlockedUserAction(Enum):
    DELETE_FROM_DB = 'delete_from_db'
    DELETE_FROM_REMNAWAVE = 'delete_from_remnawave'  # kept for callers' compatibility, becomes a no-op
    DELETE_BOTH = 'delete_both'
    MARK_AS_BLOCKED = 'mark_as_blocked'


@dataclass
class BlockCheckResult:
    user_id: int
    telegram_id: int | None
    username: str | None
    full_name: str
    status: BlockCheckStatus
    error_message: str | None = None
    remnawave_uuid: str | None = None  # always None in boilerplate
    remnawave_uuids: list[str] = field(default_factory=list)


@dataclass
class BlockedUsersScanResult:
    total_checked: int = 0
    blocked_users: list[BlockCheckResult] = field(default_factory=list)
    active_users: int = 0
    errors: int = 0
    skipped_no_telegram: int = 0
    scan_duration_seconds: float = 0.0

    @property
    def blocked_count(self) -> int:
        return len(self.blocked_users)


@dataclass
class CleanupResult:
    deleted_from_db: int = 0
    deleted_from_remnawave: int = 0  # always 0 in boilerplate
    marked_as_blocked: int = 0
    errors: list[str] = field(default_factory=list)


class BlockedUsersService:
    CHECK_DELAY_SECONDS: float = 0.05
    MAX_CONCURRENT_CHECKS: int = 10
    API_DELAY_SECONDS: float = 0.15

    def __init__(self, bot: Bot):
        self.bot = bot

    async def check_user_blocked(self, telegram_id: int) -> BlockCheckStatus:
        try:
            await self.bot.send_chat_action(chat_id=telegram_id, action='typing')
            return BlockCheckStatus.ACTIVE
        except TelegramForbiddenError:
            return BlockCheckStatus.BLOCKED
        except TelegramBadRequest as e:
            error_lower = str(e).lower()
            if 'chat not found' in error_lower or 'user not found' in error_lower:
                return BlockCheckStatus.BLOCKED
            return BlockCheckStatus.ERROR
        except TelegramAPIError:
            return BlockCheckStatus.ERROR
        except Exception as e:
            logger.error('Unexpected error while checking block status', telegram_id=telegram_id, error=e)
            return BlockCheckStatus.ERROR

    async def _check_single_user(self, user: User) -> BlockCheckResult:
        if not user.telegram_id:
            return BlockCheckResult(
                user_id=user.id,
                telegram_id=None,
                username=user.username,
                full_name=user.full_name,
                status=BlockCheckStatus.NO_TELEGRAM_ID,
            )
        status = await self.check_user_blocked(user.telegram_id)
        return BlockCheckResult(
            user_id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            full_name=user.full_name,
            status=status,
        )

    async def scan_all_users(
        self,
        db: AsyncSession,
        *,
        only_active: bool = True,
        batch_size: int = 100,
        progress_callback: Callable | None = None,
    ) -> BlockedUsersScanResult:
        start_time = datetime.now(tz=UTC)
        result = BlockedUsersScanResult()

        query = select(User)
        if only_active:
            query = query.where(User.status == UserStatus.ACTIVE.value)
        query = query.where(User.telegram_id.isnot(None))

        users_result = await db.execute(query)
        all_users = users_result.scalars().all()
        total_users = len(all_users)

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_CHECKS)

        async def check_with_semaphore(user: User) -> BlockCheckResult:
            async with semaphore:
                check_result = await self._check_single_user(user)
                await asyncio.sleep(self.CHECK_DELAY_SECONDS)
                return check_result

        checked = 0
        for i in range(0, total_users, batch_size):
            batch = all_users[i : i + batch_size]
            tasks = [check_with_semaphore(user) for user in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for check_result in batch_results:
                if isinstance(check_result, Exception):
                    result.errors += 1
                    continue
                result.total_checked += 1
                if check_result.status == BlockCheckStatus.BLOCKED:
                    result.blocked_users.append(check_result)
                elif check_result.status == BlockCheckStatus.ACTIVE:
                    result.active_users += 1
                elif check_result.status == BlockCheckStatus.NO_TELEGRAM_ID:
                    result.skipped_no_telegram += 1
                else:
                    result.errors += 1
            checked += len(batch)
            if progress_callback:
                await progress_callback(checked, total_users)

        result.scan_duration_seconds = (datetime.now(tz=UTC) - start_time).total_seconds()
        return result

    async def delete_user_from_remnawave(self, remnawave_uuid: str) -> bool:
        # No remnawave integration in boilerplate.
        return True

    async def delete_user_from_db(self, db: AsyncSession, user_id: int) -> bool:
        try:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return False

            await db.execute(delete(YooKassaPayment).where(YooKassaPayment.user_id == user.id))
            await db.execute(delete(CryptoBotPayment).where(CryptoBotPayment.user_id == user.id))
            await db.execute(delete(HeleketPayment).where(HeleketPayment.user_id == user.id))
            await db.execute(delete(MulenPayPayment).where(MulenPayPayment.user_id == user.id))
            await db.execute(delete(Pal24Payment).where(Pal24Payment.user_id == user.id))
            await db.execute(delete(WataPayment).where(WataPayment.user_id == user.id))
            await db.execute(delete(PlategaPayment).where(PlategaPayment.user_id == user.id))
            await db.execute(delete(CloudPaymentsPayment).where(CloudPaymentsPayment.user_id == user.id))
            await db.execute(delete(FreekassaPayment).where(FreekassaPayment.user_id == user.id))
            await db.execute(delete(KassaAiPayment).where(KassaAiPayment.user_id == user.id))
            await db.execute(delete(Transaction).where(Transaction.user_id == user.id))

            await db.execute(delete(TicketNotification).where(TicketNotification.user_id == user.id))
            await db.execute(delete(TicketMessage).where(TicketMessage.user_id == user.id))
            await db.execute(delete(Ticket).where(Ticket.user_id == user.id))

            await db.execute(delete(ReferralEarning).where(ReferralEarning.user_id == user.id))
            await db.execute(delete(ReferralEarning).where(ReferralEarning.referral_id == user.id))
            await db.execute(delete(WithdrawalRequest).where(WithdrawalRequest.user_id == user.id))
            await db.execute(delete(PromoCodeUse).where(PromoCodeUse.user_id == user.id))
            await db.execute(delete(DiscountOffer).where(DiscountOffer.user_id == user.id))
            await db.execute(delete(SentNotification).where(SentNotification.user_id == user.id))
            await db.execute(delete(PollResponse).where(PollResponse.user_id == user.id))
            await db.execute(delete(ContestAttempt).where(ContestAttempt.user_id == user.id))
            await db.execute(delete(ReferralContestEvent).where(ReferralContestEvent.referrer_id == user.id))
            await db.execute(delete(ReferralContestEvent).where(ReferralContestEvent.referral_id == user.id))
            await db.execute(
                delete(AdvertisingCampaignRegistration).where(AdvertisingCampaignRegistration.user_id == user.id)
            )
            await db.execute(delete(UserPromoGroup).where(UserPromoGroup.user_id == user.id))
            await db.execute(delete(CabinetRefreshToken).where(CabinetRefreshToken.user_id == user.id))
            await db.execute(delete(ButtonClickLog).where(ButtonClickLog.user_id == user.id))
            await db.execute(delete(WheelSpin).where(WheelSpin.user_id == user.id))

            referrals_query = select(User).where(User.referred_by_id == user.id)
            referrals_result = await db.execute(referrals_query)
            for referral in referrals_result.scalars().all():
                referral.referred_by_id = None

            await db.delete(user)
            await db.commit()
            return True
        except Exception as e:
            logger.error('Failed to delete user from db', user_id=user_id, error=e)
            await db.rollback()
            return False

    async def mark_user_as_blocked(self, db: AsyncSession, user_id: int) -> bool:
        try:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return False
            user.status = UserStatus.BLOCKED.value
            user.updated_at = datetime.now(tz=UTC)
            await db.commit()
            return True
        except Exception as e:
            logger.error('Failed to mark user as blocked', user_id=user_id, error=e)
            await db.rollback()
            return False

    async def cleanup_blocked_users(
        self,
        db: AsyncSession,
        blocked_users: list[BlockCheckResult],
        action: BlockedUserAction,
        *,
        progress_callback: Callable | None = None,
    ) -> CleanupResult:
        result = CleanupResult()
        total = len(blocked_users)
        for i, user_result in enumerate(blocked_users):
            try:
                if action in (BlockedUserAction.DELETE_FROM_DB, BlockedUserAction.DELETE_BOTH):
                    success = await self.delete_user_from_db(db, user_result.user_id)
                    if success:
                        result.deleted_from_db += 1
                    else:
                        result.errors.append(f'Failed to delete user {user_result.user_id} from DB')
                if action == BlockedUserAction.MARK_AS_BLOCKED:
                    success = await self.mark_user_as_blocked(db, user_result.user_id)
                    if success:
                        result.marked_as_blocked += 1
                    else:
                        result.errors.append(f'Failed to mark user {user_result.user_id} as blocked')
                # DELETE_FROM_REMNAWAVE is a no-op in the boilerplate.
                if progress_callback:
                    await progress_callback(i + 1, total)
            except Exception as e:
                result.errors.append(f'Error processing user {user_result.user_id}: {e}')
        return result
