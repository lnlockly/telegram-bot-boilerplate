import html
from decimal import ROUND_HALF_UP, Decimal

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.user import get_user_by_telegram_id
from app.external.telegram_stars import TelegramStarsService
from app.localization.loader import DEFAULT_LANGUAGE
from app.localization.texts import get_texts
from app.services.payment_service import PaymentService


logger = structlog.get_logger(__name__)


async def _handle_wheel_spin_payment(
    message: types.Message,
    db: AsyncSession,
    user,
    stars_amount: int,
    payload: str,
    texts,
):
    """Обработка Stars платежа для колеса удачи."""
    from app.database.crud.wheel import get_or_create_wheel_config, get_wheel_prizes
    from app.services.wheel_service import wheel_service

    try:
        config = await get_or_create_wheel_config(db)

        if not config.is_enabled:
            await message.answer(
                '❌ Колесо удачи временно недоступно. Звезды будут возвращены.',
            )
            return False

        # Выполняем спин напрямую (оплата уже прошла через Stars)
        prizes = await get_wheel_prizes(db, config.id, active_only=True)

        if not prizes:
            await message.answer(
                '❌ Призы не настроены. Обратитесь в поддержку.',
            )
            return False

        # Рассчитываем стоимость в копейках для статистики
        rubles_amount = TelegramStarsService.calculate_rubles_from_stars(stars_amount)
        payment_value_kopeks = int((rubles_amount * Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP))

        # Рассчитываем вероятности и выбираем приз
        prizes_with_probs = wheel_service.calculate_prize_probabilities(config, prizes, payment_value_kopeks)
        selected_prize = wheel_service._select_prize(prizes_with_probs)

        # Применяем приз
        generated_promocode = await wheel_service._apply_prize(db, user, selected_prize, config)

        # Создаем запись спина
        from app.database.crud.wheel import create_wheel_spin
        from app.database.models import WheelSpinPaymentType

        promocode_id = None
        if generated_promocode:
            from sqlalchemy import text

            result = await db.execute(
                text('SELECT id FROM promocodes WHERE code = :code'), {'code': generated_promocode}
            )
            row = result.fetchone()
            if row:
                promocode_id = row[0]

        logger.info(
            '🎰 Creating wheel spin: user.id=, user.telegram_id=, prize',
            user_id=user.id,
            telegram_id=user.telegram_id,
            display_name=selected_prize.display_name,
        )

        spin = await create_wheel_spin(
            db=db,
            user_id=user.id,
            prize_id=selected_prize.id,
            payment_type=WheelSpinPaymentType.TELEGRAM_STARS.value,
            payment_amount=stars_amount,
            payment_value_kopeks=payment_value_kopeks,
            prize_type=selected_prize.prize_type,
            prize_value=selected_prize.prize_value,
            prize_display_name=selected_prize.display_name,
            prize_value_kopeks=selected_prize.prize_value_kopeks,
            generated_promocode_id=promocode_id,
            is_applied=True,
        )

        logger.info('🎰 Wheel spin created: spin.id=, spin.user_id', spin_id=spin.id, user_id=spin.user_id)

        await db.commit()

        # Отправляем результат
        prize_message = wheel_service._get_prize_message(selected_prize, generated_promocode)

        emoji = selected_prize.emoji or '🎁'
        await message.answer(
            f'🎰 <b>Колесо удачи!</b>\n\n'
            f'{emoji} <b>{html.escape(selected_prize.display_name)}</b>\n\n'
            f'{prize_message}\n\n'
            f'⭐ Потрачено: {stars_amount} Stars',
            parse_mode='HTML',
        )

        logger.info(
            '🎰 Wheel spin via Stars: user=, prize=, stars',
            user_id=user.id,
            display_name=selected_prize.display_name,
            stars_amount=stars_amount,
        )
        return True

    except Exception as e:
        logger.error('Ошибка обработки wheel spin payment', error=e, exc_info=True)
        await message.answer(
            '❌ Произошла ошибка при обработке спина. Обратитесь в поддержку.',
        )
        return False


async def handle_pre_checkout_query(query: types.PreCheckoutQuery):
    texts = get_texts(DEFAULT_LANGUAGE)

    try:
        logger.info(
            '📋 Pre-checkout query от XTR, payload',
            from_user_id=query.from_user.id,
            total_amount=query.total_amount,
            invoice_payload=query.invoice_payload,
        )

        allowed_prefixes = ('balance_', 'admin_stars_test_', 'wheel_spin_')

        if not query.invoice_payload or not query.invoice_payload.startswith(allowed_prefixes):
            logger.warning('Невалидный payload', invoice_payload=query.invoice_payload)
            await query.answer(
                ok=False,
                error_message=texts.t(
                    'STARS_PRECHECK_INVALID_PAYLOAD',
                    'Ошибка валидации платежа. Попробуйте еще раз.',
                ),
            )
            return

        try:
            from app.database.database import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                user = await get_user_by_telegram_id(db, query.from_user.id)
                if not user:
                    logger.warning('Пользователь не найден в БД', from_user_id=query.from_user.id)
                    await query.answer(
                        ok=False,
                        error_message=texts.t(
                            'STARS_PRECHECK_USER_NOT_FOUND',
                            'Пользователь не найден. Обратитесь в поддержку.',
                        ),
                    )
                    return
                texts = get_texts(user.language or DEFAULT_LANGUAGE)
        except Exception as db_error:
            logger.error('Ошибка подключения к БД в pre_checkout_query', db_error=db_error)
            await query.answer(
                ok=False,
                error_message=texts.t(
                    'STARS_PRECHECK_TECHNICAL_ERROR',
                    'Техническая ошибка. Попробуйте позже.',
                ),
            )
            return

        await query.answer(ok=True)
        logger.info('✅ Pre-checkout одобрен для пользователя', from_user_id=query.from_user.id)

    except Exception as e:
        logger.error('Ошибка в pre_checkout_query', error=e, exc_info=True)
        await query.answer(
            ok=False,
            error_message=texts.t(
                'STARS_PRECHECK_TECHNICAL_ERROR',
                'Техническая ошибка. Попробуйте позже.',
            ),
        )


async def handle_successful_payment(message: types.Message, db: AsyncSession, state: FSMContext, **kwargs):
    texts = get_texts(DEFAULT_LANGUAGE)

    try:
        payment = message.successful_payment
        user_id = message.from_user.id

        logger.info(
            '💳 Успешный Stars платеж от XTR, payload: charge_id',
            user_id=user_id,
            total_amount=payment.total_amount,
            invoice_payload=payment.invoice_payload,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
        )

        user = await get_user_by_telegram_id(db, user_id)
        texts = get_texts(user.language if user and user.language else DEFAULT_LANGUAGE)

        if not user:
            logger.error('Пользователь не найден при обработке Stars платежа', user_id=user_id)
            await message.answer(
                texts.t(
                    'STARS_PAYMENT_USER_NOT_FOUND',
                    '❌ Ошибка: пользователь не найден. Обратитесь в поддержку.',
                )
            )
            return

        # Обработка оплаты спина колеса удачи
        if payment.invoice_payload and payment.invoice_payload.startswith('wheel_spin_'):
            await _handle_wheel_spin_payment(
                message=message,
                db=db,
                user=user,
                stars_amount=payment.total_amount,
                payload=payment.invoice_payload,
                texts=texts,
            )
            return

        payment_service = PaymentService(message.bot)

        state_data = await state.get_data()
        prompt_message_id = state_data.get('stars_prompt_message_id')
        prompt_chat_id = state_data.get('stars_prompt_chat_id', message.chat.id)
        invoice_message_id = state_data.get('stars_invoice_message_id')
        invoice_chat_id = state_data.get('stars_invoice_chat_id', message.chat.id)

        for chat_id, message_id, label in [
            (prompt_chat_id, prompt_message_id, 'запрос суммы'),
            (invoice_chat_id, invoice_message_id, 'инвойс Stars'),
        ]:
            if message_id:
                try:
                    await message.bot.delete_message(chat_id, message_id)
                except Exception as delete_error:  # pragma: no cover - зависит от прав бота
                    logger.warning(
                        'Не удалось удалить сообщение после оплаты Stars', label=label, delete_error=delete_error
                    )

        success = await payment_service.process_stars_payment(
            db=db,
            user_id=user.id,
            stars_amount=payment.total_amount,
            payload=payment.invoice_payload,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
        )

        await state.update_data(
            stars_prompt_message_id=None,
            stars_prompt_chat_id=None,
            stars_invoice_message_id=None,
            stars_invoice_chat_id=None,
        )

        if success:
            rubles_amount = TelegramStarsService.calculate_rubles_from_stars(payment.total_amount)
            amount_kopeks = int((rubles_amount * Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP))
            amount_text = settings.format_price(amount_kopeks).replace(' ₽', '')

            keyboard = await payment_service.build_topup_success_keyboard(user)

            transaction_id_short = payment.telegram_payment_charge_id[:8]

            await message.answer(
                texts.t(
                    'STARS_PAYMENT_SUCCESS',
                    '🎉 <b>Платеж успешно обработан!</b>\n\n'
                    '⭐ Потрачено звезд: {stars_spent}\n'
                    '💰 Зачислено на баланс: {amount} ₽\n'
                    '🆔 ID транзакции: {transaction_id}...\n\n'
                    'Спасибо за пополнение! 🚀',
                ).format(
                    stars_spent=payment.total_amount,
                    amount=amount_text,
                    transaction_id=transaction_id_short,
                ),
                parse_mode='HTML',
                reply_markup=keyboard,
            )

            logger.info(
                '✅ Stars платеж успешно обработан: пользователь , звезд →',
                user_id=user.id,
                total_amount=payment.total_amount,
                format_price=settings.format_price(amount_kopeks),
            )
        else:
            logger.error('Ошибка обработки Stars платежа для пользователя', user_id=user.id)
            await message.answer(
                texts.t(
                    'STARS_PAYMENT_ENROLLMENT_ERROR',
                    '❌ Произошла ошибка при зачислении средств. '
                    'Обратитесь в поддержку, платеж будет проверен вручную.',
                )
            )

    except Exception as e:
        logger.error('Ошибка в successful_payment', error=e, exc_info=True)
        await message.answer(
            texts.t(
                'STARS_PAYMENT_PROCESSING_ERROR',
                '❌ Техническая ошибка при обработке платежа. Обратитесь в поддержку для решения проблемы.',
            )
        )


def register_stars_handlers(dp: Dispatcher):
    dp.pre_checkout_query.register(handle_pre_checkout_query, F.currency == 'XTR')

    dp.message.register(handle_successful_payment, F.successful_payment)

    logger.info('🌟 Зарегистрированы обработчики Telegram Stars платежей')
