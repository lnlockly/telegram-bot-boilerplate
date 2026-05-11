import re

import structlog
from aiogram import Bot, types
from aiohttp import web

from app.config import settings
from app.database.crud.transaction import create_transaction, get_transaction_by_external_id
from app.database.crud.user import add_user_balance, get_user_by_id, get_user_by_telegram_id
from app.database.database import AsyncSessionLocal
from app.database.models import PaymentMethod, TransactionType
from app.external.tribute import TributeService


# Acceptable Tribute payment_id format: non-empty, alphanumeric/-/_, length ≥ 8.
# Refuses placeholder ids like `tribute_<tg>_<amount>` (which contain literal user/amount
# and are forgeable from public data) and the legacy "donation_unknown" string.
_TRIBUTE_PAYMENT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-]{7,}$')


def _is_valid_tribute_payment_id(payment_id: object) -> bool:
    if not isinstance(payment_id, str):
        return False
    if not _TRIBUTE_PAYMENT_ID_RE.match(payment_id):
        return False
    lowered = payment_id.lower()
    if lowered.startswith('tribute_') or lowered.endswith('_unknown'):
        return False
    return True


logger = structlog.get_logger(__name__)

# Глобальная ссылка на бота для отправки уведомлений
_bot_instance: Bot | None = None


def set_webhook_bot(bot: Bot) -> None:
    """Устанавливает экземпляр бота для отправки уведомлений об ошибках в webhook."""
    global _bot_instance
    _bot_instance = bot


async def tribute_webhook(request):
    try:
        signature = request.headers.get('trbt-signature', '')
        payload = await request.text()

        tribute_service = TributeService()

        if not tribute_service.verify_webhook_signature(payload, signature):
            logger.warning('Неверная подпись Tribute webhook')
            return web.Response(status=400, text='Invalid signature')

        webhook_data = await request.json()
        processed_data = await tribute_service.process_webhook(webhook_data)

        if not processed_data:
            logger.error('Ошибка обработки Tribute webhook')
            return web.Response(status=400, text='Invalid webhook data')

        payment_id = processed_data.get('payment_id')
        telegram_user_id = processed_data.get('user_id')
        amount_kopeks = processed_data.get('amount_kopeks', 0)
        status = processed_data.get('status')

        # Refuse webhook payloads that lack a real provider-issued payment id.
        # The forgeable fallback `tribute_<tg>_<amount>` MUST never be credited.
        if not _is_valid_tribute_payment_id(payment_id):
            logger.warning(
                'Отклоняем Tribute webhook: некорректный или forgeable payment_id',
                payment_id=payment_id,
                telegram_user_id=telegram_user_id,
            )
            return web.Response(status=400, text='Invalid payment_id')

        if not telegram_user_id:
            logger.warning('Отклоняем Tribute webhook: отсутствует telegram_user_id')
            return web.Response(status=400, text='Missing telegram_user_id')

        async with AsyncSessionLocal() as db:
            try:
                existing_transaction = await get_transaction_by_external_id(
                    db, payment_id, PaymentMethod.TRIBUTE
                )

                if existing_transaction:
                    logger.info('Платеж уже обработан', payment_id=payment_id)
                    return web.Response(status=200, text='Already processed')

                if status == 'completed' or status == 'paid':
                    # `processed_data['user_id']` is actually the Telegram ID
                    # (see TributeService.process_webhook). Look up the local user
                    # via telegram_id, NOT internal User.id.
                    user = await get_user_by_telegram_id(db, telegram_user_id)

                    if user:
                        # Credit balance WITHOUT auto-creating a transaction row,
                        # then create one transaction with external_id=payment_id
                        # so future webhook retries hit the idempotency lookup above.
                        # Previously both add_user_balance AND create_transaction
                        # were called → double booking.
                        await add_user_balance(
                            db,
                            user,
                            amount_kopeks,
                            f'Пополнение через Tribute: {payment_id}',
                            payment_method=PaymentMethod.TRIBUTE,
                            create_transaction=False,
                            commit=False,
                        )

                        await create_transaction(
                            db=db,
                            user_id=user.id,
                            type=TransactionType.DEPOSIT,
                            amount_kopeks=amount_kopeks,
                            description=f'Пополнение через Tribute: {payment_id}',
                            payment_method=PaymentMethod.TRIBUTE,
                            external_id=payment_id,
                            commit=False,
                        )

                        logger.info('✅ Обработан Tribute платеж', payment_id=payment_id)
                    else:
                        logger.warning(
                            'Tribute webhook: пользователь не найден по telegram_id',
                            telegram_user_id=telegram_user_id,
                            payment_id=payment_id,
                        )

                await db.commit()
                return web.Response(status=200, text='OK')

            except Exception as e:
                logger.error('Ошибка обработки Tribute webhook', error=e)
                await db.rollback()
                return web.Response(status=500, text='Internal error')

    except Exception as e:
        logger.error('Ошибка в Tribute webhook', error=e)
        return web.Response(status=500, text='Internal error')


async def handle_successful_payment(message: types.Message):
    try:
        payment = message.successful_payment

        payload_parts = payment.invoice_payload.split('_')
        if len(payload_parts) >= 3 and payload_parts[0] == 'balance':
            user_id = int(payload_parts[1])
            amount_kopeks = int(payload_parts[2])

            async with AsyncSessionLocal() as db:
                try:
                    existing_transaction = await get_transaction_by_external_id(
                        db, payment.telegram_payment_charge_id, PaymentMethod.TELEGRAM_STARS
                    )

                    if existing_transaction:
                        logger.info(
                            'Stars платеж уже обработан', telegram_payment_charge_id=payment.telegram_payment_charge_id
                        )
                        return

                    user = await get_user_by_id(db, user_id)

                    if user:
                        await add_user_balance(db, user, amount_kopeks, 'Пополнение через Telegram Stars')

                        await create_transaction(
                            db=db,
                            user_id=user.id,
                            type=TransactionType.DEPOSIT,
                            amount_kopeks=amount_kopeks,
                            description='Пополнение через Telegram Stars',
                            payment_method=PaymentMethod.TELEGRAM_STARS,
                            external_id=payment.telegram_payment_charge_id,
                        )

                        await message.answer(
                            f'✅ Баланс успешно пополнен на {settings.format_price(amount_kopeks)}!\n\n'
                            'Средства зачислены на ваш баланс!'
                        )

                        logger.info(
                            '✅ Обработан Stars платеж', telegram_payment_charge_id=payment.telegram_payment_charge_id
                        )

                    await db.commit()

                except Exception as e:
                    logger.error('Ошибка обработки Stars платежа', error=e)
                    await db.rollback()

    except Exception as e:
        logger.error('Ошибка в обработчике Stars платежа', error=e)


async def handle_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    try:
        await pre_checkout_query.answer(ok=True)
        logger.info('Pre-checkout query принят', pre_checkout_query_id=pre_checkout_query.id)

    except Exception as e:
        logger.error('Ошибка в pre-checkout query', error=e)
        await pre_checkout_query.answer(ok=False, error_message='Ошибка обработки платежа')
