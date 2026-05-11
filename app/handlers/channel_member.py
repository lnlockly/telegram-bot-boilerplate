"""ChatMemberUpdated event handler for real-time channel subscription tracking.

Generic boilerplate version: tracks join/leave events on required channels and
maintains the channel_subscription_service cache. No VPN-specific coupling.
"""

import structlog
from aiogram import Dispatcher, F
from aiogram.types import ChatMemberUpdated

from app.services.channel_subscription_service import channel_subscription_service


logger = structlog.get_logger(__name__)


async def handle_chat_member_update(event: ChatMemberUpdated) -> None:
    """Handle ChatMemberUpdated events for required channels.

    Tracks join/leave events and updates the channel subscription cache so
    the channel checker middleware can immediately reflect the new state.
    """
    try:
        chat = event.chat
        user = event.new_chat_member.user if event.new_chat_member else None

        if not chat or not user or user.is_bot:
            return

        channel_id = chat.id

        required_ids = await channel_subscription_service.get_required_channel_ids()
        if channel_id not in required_ids:
            return

        old_status = event.old_chat_member.status if event.old_chat_member else None
        new_status = event.new_chat_member.status if event.new_chat_member else None

        joined_statuses = {'member', 'administrator', 'creator', 'restricted'}
        left_statuses = {'left', 'kicked'}

        was_in = old_status in joined_statuses
        is_in = new_status in joined_statuses

        if not was_in and is_in:
            await channel_subscription_service.on_user_joined(user.id, channel_id)
            logger.info(
                'User joined required channel',
                user_id=user.id,
                channel_id=channel_id,
            )
        elif was_in and (new_status in left_statuses or not is_in):
            await channel_subscription_service.on_user_left(user.id, channel_id)
            logger.info(
                'User left required channel',
                user_id=user.id,
                channel_id=channel_id,
            )
    except Exception as e:
        logger.error('Error handling ChatMemberUpdated event', error=e)


def register_handlers(dp: Dispatcher) -> None:
    dp.chat_member.register(handle_chat_member_update)
