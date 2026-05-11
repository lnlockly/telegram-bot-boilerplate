"""Shared payment utilities used across all payment provider mixins.

In the original VPN bot this module also drove subscription checkout
resumption, auto-purchase, and guest fulfilment. The boilerplate keeps
just the generic top-up notification helpers.

TODO(boilerplate): plug your post-payment business logic here. The default
behaviour is to credit the user's balance.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.user import get_user_by_telegram_id
from app.database.database import get_db
from app.localization.texts import get_texts
from app.utils.miniapp_buttons import build_miniapp_or_callback_button
from app.utils.payment_logger import payment_logger as logger


class PaymentCommonMixin:
    """Mixin with shared post-payment helpers."""

    async def build_topup_success_keyboard(self, user: Any) -> InlineKeyboardMarkup:
        texts = get_texts(getattr(user, 'language', 'ru') if user else 'ru')

        keyboard_rows: list[list[InlineKeyboardButton]] = [
            [
                build_miniapp_or_callback_button(
                    text=getattr(texts, 'MY_BALANCE_BUTTON', '💰 Мой баланс'),
                    callback_data='menu_balance',
                )
            ],
            [
                InlineKeyboardButton(
                    text=getattr(texts, 'MAIN_MENU_BUTTON', '🏠 Главное меню'),
                    callback_data='back_to_menu',
                )
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    async def _send_payment_success_notification(
        self,
        telegram_id: int | None,
        amount_kopeks: int,
        user: Any | None = None,
        *,
        db: AsyncSession | None = None,
        payment_method_title: str | None = None,
    ) -> None:
        # Lazy import to avoid circular dependency.
        try:
            from app.cabinet.routes.websocket import notify_user_balance_topup
        except Exception:
            notify_user_balance_topup = None  # type: ignore[assignment]

        user_id = getattr(user, 'id', None) if user else None
        if user_id and notify_user_balance_topup is not None:
            try:
                new_balance = getattr(user, 'balance_kopeks', 0)
                await notify_user_balance_topup(
                    user_id=user_id,
                    amount_kopeks=amount_kopeks,
                    new_balance_kopeks=new_balance,
                    description=payment_method_title or '',
                )
            except Exception as ws_error:
                logger.warning(
                    'Failed to send WS topup notification',
                    user_id=user_id,
                    ws_error=ws_error,
                )

        if not getattr(self, 'bot', None):
            return
        if not telegram_id:
            return

        snapshot = await self._ensure_user_snapshot(telegram_id, user, db=db)
        try:
            payment_method = payment_method_title or 'Балансовое пополнение'
            keyboard = await self.build_topup_success_keyboard(snapshot)
            message = (
                '✅ <b>Платёж успешно завершён!</b>\n\n'
                f'💰 Сумма: {settings.format_price(amount_kopeks)}\n'
                f'💳 Способ: {payment_method}\n\n'
                'Средства зачислены на ваш баланс!'
            )
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='HTML',
                reply_markup=keyboard,
            )
        except Exception as error:
            logger.error('Failed to send topup notification', telegram_id=telegram_id, error=error)

    async def _ensure_user_snapshot(
        self,
        telegram_id: int | None,
        user: Any | None,
        *,
        db: AsyncSession | None = None,
    ) -> Any | None:
        def _build_snapshot(source: Any | None) -> SimpleNamespace | None:
            if source is None:
                return None
            return SimpleNamespace(
                id=getattr(source, 'id', None),
                telegram_id=getattr(source, 'telegram_id', None),
                language=getattr(source, 'language', 'ru'),
                balance_kopeks=getattr(source, 'balance_kopeks', 0),
            )

        try:
            snapshot = _build_snapshot(user)
        except MissingGreenlet:
            snapshot = None
        if snapshot is not None:
            return snapshot

        if db is not None and telegram_id is not None:
            try:
                fetched = await get_user_by_telegram_id(db, telegram_id)
                return _build_snapshot(fetched)
            except Exception:
                pass

        if telegram_id is not None:
            try:
                async for db_session in get_db():
                    fetched = await get_user_by_telegram_id(db_session, telegram_id)
                    return _build_snapshot(fetched)
            except Exception:
                pass
        return None

    async def process_successful_payment(
        self,
        payment_id: str,
        amount_kopeks: int,
        user_id: int,
        payment_method: str,
    ) -> bool:
        """Generic post-payment hook.

        TODO(boilerplate): plug your post-payment business logic here. Default
        behaviour: credit balance is performed by the per-provider mixin's
        webhook handler — this just logs.
        """
        try:
            logger.info(
                'Payment successful',
                payment_id=payment_id,
                amount_kopeks=amount_kopeks,
                user_id=user_id,
                payment_method=payment_method,
            )
            return True
        except Exception as error:
            logger.error('process_successful_payment failed', payment_id=payment_id, error=error)
            return False


async def send_cart_notification_after_topup(
    user: Any,
    amount_kopeks: int,
    db: AsyncSession,
    bot: Any | None,
) -> bool:
    """No-op in boilerplate (cart auto-purchase removed).

    TODO(boilerplate): replace with your own post-topup checkout flow.
    """
    return False


async def try_fulfill_guest_purchase(
    db: AsyncSession,
    *,
    metadata: dict[str, Any] | None,
    payment_amount_kopeks: int,
    provider_payment_id: str,
    provider_name: str,
    skip_amount_check: bool = False,
) -> bool | None:
    """No-op in boilerplate (guest purchases removed).

    Returns ``None`` so callers fall through to their normal handling.
    """
    return None
