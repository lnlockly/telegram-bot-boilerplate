"""Advertising campaign bonus service.

The original VPN bot supported balance / subscription / tariff bonuses for
campaign signups. The boilerplate keeps only the balance and "no bonus"
paths. Subscription and tariff bonuses become balance equivalents (when an
amount is configured) or a simple no-op registration.

TODO(boilerplate): replace the subscription/tariff branches with your own
product perks if needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.campaign import record_campaign_registration
from app.database.crud.user import add_user_balance
from app.database.models import AdvertisingCampaign, User


logger = structlog.get_logger(__name__)


def _format_user_log(user: User) -> str:
    if user.telegram_id:
        return str(user.telegram_id)
    if user.email:
        return f'{user.id} ({user.email})'
    return f'#{user.id}'


@dataclass
class CampaignBonusResult:
    success: bool
    bonus_type: str | None = None
    balance_kopeks: int = 0
    subscription_days: int | None = None
    subscription_traffic_gb: int | None = None
    subscription_device_limit: int | None = None
    subscription_squads: list[str] | None = None
    tariff_id: int | None = None
    tariff_name: str | None = None
    tariff_duration_days: int | None = None


class AdvertisingCampaignService:
    async def apply_campaign_bonus(
        self,
        db: AsyncSession,
        user: User,
        campaign: AdvertisingCampaign,
    ) -> CampaignBonusResult:
        if not campaign.is_active:
            return CampaignBonusResult(success=False)
        if campaign.partner_user_id and campaign.partner_user_id == user.id:
            return CampaignBonusResult(success=False)
        if campaign.is_balance_bonus:
            return await self._apply_balance_bonus(db, user, campaign)
        if campaign.is_none_bonus:
            return await self._apply_none_bonus(db, user, campaign)
        # Subscription/tariff bonuses are unsupported in the boilerplate.
        # Treat them as a tracking-only registration.
        return await self._apply_none_bonus(db, user, campaign)

    async def _apply_balance_bonus(
        self,
        db: AsyncSession,
        user: User,
        campaign: AdvertisingCampaign,
    ) -> CampaignBonusResult:
        amount = campaign.balance_bonus_kopeks or 0
        if amount <= 0:
            return CampaignBonusResult(success=False)

        description = f"Бонус за регистрацию по кампании '{campaign.name}'"
        success = await add_user_balance(db, user, amount, description=description)
        if not success:
            return CampaignBonusResult(success=False)

        await record_campaign_registration(
            db,
            campaign_id=campaign.id,
            user_id=user.id,
            bonus_type='balance',
            balance_bonus_kopeks=amount,
        )
        logger.info(
            'Campaign balance bonus credited',
            user=_format_user_log(user),
            amount_kopeks=amount,
            campaign_id=campaign.id,
        )
        return CampaignBonusResult(success=True, bonus_type='balance', balance_kopeks=amount)

    async def _apply_none_bonus(
        self,
        db: AsyncSession,
        user: User,
        campaign: AdvertisingCampaign,
    ) -> CampaignBonusResult:
        await record_campaign_registration(
            db,
            campaign_id=campaign.id,
            user_id=user.id,
            bonus_type='none',
        )
        return CampaignBonusResult(success=True, bonus_type='none')
