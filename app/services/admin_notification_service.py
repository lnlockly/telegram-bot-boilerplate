"""Admin notification service.

Sends notifications to an admin chat / forum topics. The original VPN bot had
many subscription-specific notifications (purchases, renewals, trials, traffic
warnings, RemnaWave panel status, etc.). Those have been removed.

What's kept:
- generic ``send_admin_notification`` / ``_send_message`` plumbing
- balance top-up notification
- partner application / withdrawal request / bulk-ban / promocode notifications
- ticket-event notifications
- version update notification
- promo group change notification
- campaign link visit notification

Subscription-related public methods are kept as no-op stubs so that callers
that still reference them don't blow up at import time.
TODO(boilerplate): replace stubs with your own product notifications.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.promo_group import get_promo_group_by_id
from app.database.crud.transaction import get_transaction_by_id
from app.database.crud.user import get_user_by_id
from app.database.models import (
    AdvertisingCampaign,
    PromoCodeType,
    PromoGroup,
    Transaction,
    User,
)
from app.utils.timezone import format_local_datetime


logger = structlog.get_logger(__name__)


class NotificationCategory(StrEnum):
    """Categories used to route messages to specific forum topics."""

    PURCHASES = 'purchases'
    RENEWALS = 'renewals'
    TRIALS = 'trials'
    BALANCE = 'balance'
    ADDONS = 'addons'
    INFRASTRUCTURE = 'infrastructure'
    ERRORS = 'errors'
    PROMO = 'promo'
    PARTNERS = 'partners'
    TICKETS = 'tickets'


class AdminNotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.chat_id = getattr(settings, 'ADMIN_NOTIFICATIONS_CHAT_ID', None)
        self.topic_id = getattr(settings, 'ADMIN_NOTIFICATIONS_TOPIC_ID', None)
        self.ticket_topic_id = getattr(settings, 'ADMIN_NOTIFICATIONS_TICKET_TOPIC_ID', None)
        self.enabled = getattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False)

        self.category_topics: dict[NotificationCategory, int | None] = {
            NotificationCategory.PURCHASES: getattr(settings, 'ADMIN_NOTIFICATIONS_PURCHASES_TOPIC_ID', None),
            NotificationCategory.RENEWALS: getattr(settings, 'ADMIN_NOTIFICATIONS_RENEWALS_TOPIC_ID', None),
            NotificationCategory.TRIALS: getattr(settings, 'ADMIN_NOTIFICATIONS_TRIALS_TOPIC_ID', None),
            NotificationCategory.BALANCE: getattr(settings, 'ADMIN_NOTIFICATIONS_BALANCE_TOPIC_ID', None),
            NotificationCategory.ADDONS: getattr(settings, 'ADMIN_NOTIFICATIONS_ADDONS_TOPIC_ID', None),
            NotificationCategory.INFRASTRUCTURE: getattr(
                settings, 'ADMIN_NOTIFICATIONS_INFRASTRUCTURE_TOPIC_ID', None
            ),
            NotificationCategory.ERRORS: getattr(settings, 'ADMIN_NOTIFICATIONS_ERRORS_TOPIC_ID', None),
            NotificationCategory.PROMO: getattr(settings, 'ADMIN_NOTIFICATIONS_PROMO_TOPIC_ID', None),
            NotificationCategory.PARTNERS: getattr(settings, 'ADMIN_NOTIFICATIONS_PARTNERS_TOPIC_ID', None),
            NotificationCategory.TICKETS: self.ticket_topic_id,
        }

        self.category_enabled: dict[NotificationCategory, bool] = {}
        for cat in NotificationCategory:
            key = f'ADMIN_NOTIFICATIONS_{cat.value.upper()}_ENABLED'
            self.category_enabled[cat] = getattr(settings, key, True)

    # --- helpers --------------------------------------------------------

    def _is_enabled(self) -> bool:
        return self.enabled and bool(self.chat_id)

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled()

    def _resolve_topic_id(self, category: NotificationCategory | None = None) -> int | None:
        if category:
            topic = self.category_topics.get(category)
            if topic is not None:
                return topic
        return self.topic_id

    async def _send_message(
        self,
        text: str,
        reply_markup: types.InlineKeyboardMarkup | None = None,
        *,
        category: NotificationCategory | None = None,
    ) -> bool:
        if not self.chat_id:
            return False
        if category and not self.category_enabled.get(category, True):
            return False
        try:
            message_kwargs: dict[str, Any] = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            }
            thread_id = self._resolve_topic_id(category)
            if thread_id:
                message_kwargs['message_thread_id'] = thread_id
            if reply_markup is not None:
                message_kwargs['reply_markup'] = reply_markup
            await self.bot.send_message(**message_kwargs)
            return True
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.error('Failed to send admin notification', error=e)
            return False
        except Exception as e:
            logger.error('Unexpected error sending admin notification', error=e)
            return False

    def _get_user_display(self, user: User) -> str:
        first_name = getattr(user, 'first_name', '') or ''
        if first_name:
            return html.escape(first_name)
        username = getattr(user, 'username', None)
        if username:
            return f'@{html.escape(username)}'
        return f'User#{getattr(user, "id", "?")}'

    def _get_user_identifier_display(self, user: User) -> str:
        telegram_id = getattr(user, 'telegram_id', None)
        if telegram_id:
            return f'TG: {telegram_id}'
        email = getattr(user, 'email', None)
        if email:
            return f'📧 {html.escape(email)}'
        return f'ID: {getattr(user, "id", "?")}'

    def _get_payment_method_display(self, payment_method: str | None) -> str:
        if not payment_method:
            return 'balance'
        return str(payment_method)

    async def _get_referrer_info(self, db: AsyncSession, referred_by_id: int | None) -> str:
        if not referred_by_id:
            return 'Нет'
        try:
            referrer = await get_user_by_id(db, referred_by_id)
            if not referrer:
                return f'ID {referred_by_id} (не найден)'
            if referrer.username:
                return f'@{html.escape(referrer.username)} (ID: {referred_by_id})'
            if referrer.telegram_id:
                return f'ID {referrer.telegram_id}'
            if referrer.email:
                return f'📧 {html.escape(referrer.email)}'
            return f'User#{referred_by_id}'
        except Exception as e:
            logger.error('Failed to fetch referrer', referred_by_id=referred_by_id, error=e)
            return f'ID {referred_by_id}'

    async def _get_user_promo_group(self, db: AsyncSession, user: User) -> PromoGroup | None:
        if getattr(user, 'promo_group', None):
            return user.promo_group
        if not getattr(user, 'promo_group_id', None):
            return None
        try:
            return await get_promo_group_by_id(db, user.promo_group_id)
        except Exception:
            return None

    # --- generic public API --------------------------------------------

    async def send_admin_notification(
        self,
        text: str,
        reply_markup: types.InlineKeyboardMarkup | None = None,
        *,
        category: NotificationCategory | None = None,
    ) -> bool:
        if not self._is_enabled():
            return False
        return await self._send_message(text, reply_markup=reply_markup, category=category)

    # --- balance --------------------------------------------------------

    async def send_balance_topup_notification(
        self,
        user: User,
        transaction: Transaction,
        old_balance: int,
        *,
        topup_status: str,
        referrer_info: str,
        subscription: Any | None = None,  # kept for back-compat, ignored
        promo_group: PromoGroup | None = None,
        db: AsyncSession | None = None,
    ) -> bool:
        if not self._is_enabled():
            return False
        try:
            payment_method = self._get_payment_method_display(transaction.payment_method)
            balance_change = user.balance_kopeks - old_balance
            timestamp = format_local_datetime(datetime.now(UTC), '%d.%m.%Y %H:%M:%S')
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)

            lines: list[str] = [
                '💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>',
                '',
                f'👤 {user_display} ({user_id_display})',
            ]
            username = getattr(user, 'username', None)
            if username:
                lines.append(f'📱 @{html.escape(username)}')
            lines.append(f'💳 {topup_status}')
            if promo_group:
                lines.append(f'🏷️ Промогруппа: {html.escape(promo_group.name)}')
            lines.append('')
            lines.extend([
                f'💵 <b>{settings.format_price(transaction.amount_kopeks)}</b> | {payment_method}',
                '',
                f'📉 {settings.format_price(old_balance)} → 📈 {settings.format_price(user.balance_kopeks)}'
                f' (<b>+{settings.format_price(balance_change)}</b>)',
            ])
            if referrer_info and referrer_info != 'Нет':
                lines.append(f'🔗 Реферер: {referrer_info}')
            detail_lines = [
                f'ID транзакции: {transaction.id}',
                f'Способ оплаты: {transaction.payment_method or "balance"}',
            ]
            if getattr(transaction, 'external_id', None):
                detail_lines.append(f'Внешний ID: {transaction.external_id}')
            if getattr(transaction, 'description', None):
                desc = transaction.description
                if len(desc) > 120:
                    desc = desc[:117] + '...'
                detail_lines.append(f'Описание: {html.escape(desc)}')
            blockquote_body = '\n'.join(detail_lines)
            lines.extend(['', f'<blockquote expandable>{blockquote_body}</blockquote>', f'<i>{timestamp}</i>'])

            return await self._send_message('\n'.join(lines), category=NotificationCategory.BALANCE)
        except Exception as e:
            logger.error('Failed to send balance topup notification', error=e)
            return False

    # --- subscription notifications (no-op stubs) ----------------------

    async def send_trial_activation_notification(self, *args, **kwargs) -> bool:
        # TODO(boilerplate): subscriptions removed; replace with your own logic.
        return False

    async def send_subscription_purchase_notification(self, *args, **kwargs) -> bool:
        # TODO(boilerplate): subscriptions removed; replace with your own logic.
        return False

    async def send_subscription_extension_notification(self, *args, **kwargs) -> bool:
        # TODO(boilerplate): subscriptions removed; replace with your own logic.
        return False

    async def send_subscription_update_notification(self, *args, **kwargs) -> bool:
        # TODO(boilerplate): subscriptions removed; replace with your own logic.
        return False

    async def send_guest_purchase_notification(self, *args, **kwargs) -> bool:
        # TODO(boilerplate): guest purchases removed; replace with your own logic.
        return False

    async def send_remnawave_panel_status_notification(self, *args, **kwargs) -> bool:
        return False

    async def send_suspicious_traffic_notification(self, *args, **kwargs) -> bool:
        return False

    async def send_maintenance_status_notification(
        self,
        is_active: bool,
        admin_user: User | None = None,
        message: str | None = None,
    ) -> bool:
        if not self._is_enabled():
            return False
        status = '🛠 Включён режим обслуживания' if is_active else '✅ Режим обслуживания выключен'
        lines = [f'<b>{status}</b>']
        if admin_user is not None:
            lines.append(f'👤 Инициатор: {self._get_user_display(admin_user)}')
        if message:
            lines.append(html.escape(message))
        return await self._send_message('\n'.join(lines), category=NotificationCategory.INFRASTRUCTURE)

    # --- promocode / campaign / promo group ----------------------------

    async def send_promocode_activation_notification(
        self,
        user: User,
        promocode: Any,
        *,
        promo_group: PromoGroup | None = None,
        db: AsyncSession | None = None,
    ) -> bool:
        if not self._is_enabled():
            return False
        try:
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)
            code = getattr(promocode, 'code', '?')
            promo_type = getattr(promocode, 'type', None)
            type_display = (
                'Баланс' if promo_type == PromoCodeType.BALANCE.value
                else str(promo_type or '—')
            )
            value = getattr(promocode, 'balance_bonus_kopeks', None) or getattr(promocode, 'bonus_kopeks', None) or 0
            lines = [
                '🎟 <b>Активация промокода</b>',
                '',
                f'👤 {user_display} ({user_id_display})',
                f'🔑 Код: <code>{html.escape(str(code))}</code>',
                f'🏷 Тип: {type_display}',
            ]
            if value:
                lines.append(f'💰 Бонус: {settings.format_price(int(value))}')
            if promo_group:
                lines.append(f'Промогруппа: {html.escape(promo_group.name)}')
            return await self._send_message('\n'.join(lines), category=NotificationCategory.PROMO)
        except Exception as e:
            logger.error('Failed to send promocode notification', error=e)
            return False

    async def send_campaign_link_visit_notification(
        self,
        user: User,
        campaign: AdvertisingCampaign,
        *,
        is_new_user: bool = False,
    ) -> bool:
        if not self._is_enabled():
            return False
        try:
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)
            campaign_name = getattr(campaign, 'name', '—')
            label = 'новый пользователь' if is_new_user else 'существующий пользователь'
            text = (
                f'📣 <b>Переход по рекламной ссылке</b>\n\n'
                f'👤 {user_display} ({user_id_display}) — {label}\n'
                f'Кампания: {html.escape(str(campaign_name))}'
            )
            return await self._send_message(text, category=NotificationCategory.PROMO)
        except Exception as e:
            logger.error('Failed to send campaign visit notification', error=e)
            return False

    async def send_user_promo_group_change_notification(
        self,
        user: User,
        old_group: PromoGroup | None,
        new_group: PromoGroup | None,
        *,
        actor: User | None = None,
        reason: str | None = None,
    ) -> bool:
        if not self._is_enabled():
            return False
        try:
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)
            old_name = getattr(old_group, 'name', '—') if old_group else '—'
            new_name = getattr(new_group, 'name', '—') if new_group else '—'
            lines = [
                '🏷 <b>Изменение промогруппы</b>',
                '',
                f'👤 {user_display} ({user_id_display})',
                f'{html.escape(str(old_name))} → {html.escape(str(new_name))}',
            ]
            if actor is not None:
                lines.append(f'Инициатор: {self._get_user_display(actor)}')
            if reason:
                lines.append(f'Причина: {html.escape(reason)}')
            return await self._send_message('\n'.join(lines), category=NotificationCategory.PROMO)
        except Exception as e:
            logger.error('Failed to send promo group change notification', error=e)
            return False

    # --- partners / withdrawal -----------------------------------------

    async def send_partner_application_notification(self, application: Any) -> bool:
        if not self._is_enabled():
            return False
        try:
            text = (
                '🤝 <b>Новая заявка партнёра</b>\n'
                f'ID: {getattr(application, "id", "?")}\n'
                f'Пользователь: {getattr(application, "user_id", "?")}'
            )
            return await self._send_message(text, category=NotificationCategory.PARTNERS)
        except Exception as e:
            logger.error('Failed to send partner application notification', error=e)
            return False

    async def send_withdrawal_request_notification(self, request: Any) -> bool:
        if not self._is_enabled():
            return False
        try:
            amount = getattr(request, 'amount_kopeks', 0)
            text = (
                '💸 <b>Запрос на вывод средств</b>\n'
                f'ID: {getattr(request, "id", "?")}\n'
                f'Сумма: {settings.format_price(int(amount or 0))}'
            )
            return await self._send_message(text, category=NotificationCategory.PARTNERS)
        except Exception as e:
            logger.error('Failed to send withdrawal notification', error=e)
            return False

    async def send_bulk_ban_notification(self, *args, **kwargs) -> bool:
        if not self._is_enabled():
            return False
        try:
            text = '🚫 <b>Массовая блокировка пользователей</b>'
            return await self._send_message(text, category=NotificationCategory.ERRORS)
        except Exception as e:
            logger.error('Failed to send bulk ban notification', error=e)
            return False

    # --- tickets / version / webhooks ----------------------------------

    async def send_ticket_event_notification(self, *args, **kwargs) -> bool:
        if not self._is_enabled():
            return False
        # Detailed ticket-event formatting was VPN-coupled. Send a generic stub.
        text = '🎫 <b>Событие тикета</b>'
        return await self._send_message(text, category=NotificationCategory.TICKETS)

    async def send_version_update_notification(
        self, current_version: str, latest_version: Any, total_updates: int
    ) -> bool:
        if not self._is_enabled():
            return False
        latest_str = getattr(latest_version, 'version', None) or str(latest_version)
        text = (
            '🆙 <b>Доступно обновление</b>\n'
            f'Текущая версия: {current_version}\n'
            f'Последняя версия: {latest_str}\n'
            f'Пропущено обновлений: {total_updates}'
        )
        return await self._send_message(text, category=NotificationCategory.INFRASTRUCTURE)

    async def send_version_check_error_notification(self, error_message: str, current_version: str) -> bool:
        if not self._is_enabled():
            return False
        text = (
            '⚠️ <b>Ошибка проверки версии</b>\n'
            f'Текущая версия: {current_version}\n'
            f'Ошибка: {html.escape(error_message)}'
        )
        return await self._send_message(text, category=NotificationCategory.ERRORS)

    async def send_webhook_notification(self, text: str) -> bool:
        if not self._is_enabled():
            return False
        return await self._send_message(text, category=NotificationCategory.INFRASTRUCTURE)
