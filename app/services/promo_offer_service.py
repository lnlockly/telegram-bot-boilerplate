"""Promo offer service stub.

The original VPN bot used promo offers to grant temporary access to extra
RemnaWave squads (`test_squad_uuids`, `test_duration_hours`). All that logic
has been removed.

TODO(boilerplate): plug your own promo-offer reward (balance bonus, perks,
etc.) here.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DiscountOffer, User


logger = structlog.get_logger(__name__)


class PromoOfferService:
    async def grant_test_access(
        self,
        db: AsyncSession,
        user: User,
        offer: DiscountOffer,
    ) -> tuple[bool, list[str] | None, datetime | None, str]:
        # Test/squad access removed in the boilerplate.
        return False, None, None, 'not_supported'

    async def cleanup_expired_test_access(self, db: AsyncSession) -> int:
        return 0


promo_offer_service = PromoOfferService()
