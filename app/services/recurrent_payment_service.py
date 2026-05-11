"""Recurrent payment service stub.

The original VPN bot used this to auto-top-up balance on saved cards so the
subscription auto-renewal monitor could extend subscriptions. Subscriptions
are gone in the boilerplate, so this is reduced to a no-op.

TODO(boilerplate): plug your own recurring auto-payment logic here if you need
recurring top-ups for your product.
"""

from __future__ import annotations

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession


logger = structlog.get_logger(__name__)


async def process_recurrent_payments(db: AsyncSession, bot: Bot | None = None) -> dict:
    """No-op recurrent payment processor (boilerplate stub)."""
    return {'skipped': True, 'reason': 'recurrent_payments_disabled_in_boilerplate'}
