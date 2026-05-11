from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.promo_group import get_promo_group_by_id
from app.database.crud.promocode import (
    check_user_promocode_usage,
    create_promocode_use,
    get_active_discount_promocode_for_user,
    get_promocode_by_code,
    increment_promocode_uses_atomic,
)
from app.database.crud.user import add_user_balance, get_user_by_id
from app.database.crud.user_promo_group import add_user_to_promo_group, has_user_promo_group
from app.database.models import PromoCode, PromoCodeType, User


logger = structlog.get_logger(__name__)


class _SelectSubscriptionRequired(Exception):
    """Raised when multi-tariff promo requires user to select a subscription."""

    def __init__(self, eligible_subscriptions: list[dict], code: str):
        self.eligible_subscriptions = eligible_subscriptions
        self.code = code
        super().__init__('select_subscription')


class PromoCodeService:
    def __init__(self):
        # RemnaWave/subscription dependencies removed in boilerplate.
        pass

    @staticmethod
    def _format_user_log(user: User) -> str:
        """Форматирует идентификатор пользователя для логов (поддержка email-only users)."""
        if user.telegram_id:
            return str(user.telegram_id)
        if user.email:
            return f'{user.id} ({user.email})'
        return f'#{user.id}'

    async def activate_promocode(
        self, db: AsyncSession, user_id: int, code: str, *, subscription_id: int | None = None
    ) -> dict[str, Any]:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return {'success': False, 'error': 'user_not_found'}

            promocode = await get_promocode_by_code(db, code)
            if not promocode:
                return {'success': False, 'error': 'not_found'}

            if not promocode.is_valid:
                if promocode.current_uses >= promocode.max_uses:
                    return {'success': False, 'error': 'used'}
                if not promocode.is_active:
                    return {'success': False, 'error': 'inactive'}
                from app.database.models import _aware

                now = datetime.now(UTC)
                aware_from = _aware(promocode.valid_from)
                if aware_from is not None and aware_from > now:
                    return {'success': False, 'error': 'not_yet_valid'}
                return {'success': False, 'error': 'expired'}

            existing_use = await check_user_promocode_usage(db, user_id, promocode.id)
            if existing_use:
                return {'success': False, 'error': 'already_used_by_user'}

            # Лимит на количество активаций за день (анти-стакинг)
            from app.database.crud.promocode import count_user_recent_activations

            recent_count = await count_user_recent_activations(db, user_id, hours=24)
            if recent_count >= 5:
                logger.warning(
                    'Promo stacking limit: user has activations in 24h',
                    _format_user_log=self._format_user_log(user),
                    recent_count=recent_count,
                )
                return {'success': False, 'error': 'daily_limit'}

            # Проверка "только для первой покупки"
            if getattr(promocode, 'first_purchase_only', False):
                if getattr(user, 'has_had_paid_subscription', False):
                    return {'success': False, 'error': 'not_first_purchase'}

            balance_before_kopeks = user.balance_kopeks

            # Атомарно резервируем слот использования (защита от TOCTOU при max_uses).
            # Должно идти ПЕРЕД созданием PromoCodeUse и применением эффектов.
            reserved = await increment_promocode_uses_atomic(db, promocode.id)
            if not reserved:
                logger.info(
                    'ℹ️ Промокод исчерпан (атомарная проверка)',
                    _format_user_log=self._format_user_log(user),
                    code=code,
                )
                return {'success': False, 'error': 'used'}

            # Резервируем запись использования ДО применения эффектов (защита от race condition)
            promo_use = await create_promocode_use(db, promocode.id, user_id)
            if promo_use is None:
                # Откатываем атомарный инкремент, т.к. PromoCodeUse не создан (дубликат)
                await db.rollback()
                return {'success': False, 'error': 'already_used_by_user'}

            try:
                result_description = await self._apply_promocode_effects(
                    db, user, promocode, subscription_id=subscription_id
                )
            except _SelectSubscriptionRequired as e:
                # Мульти-тариф: нужен выбор подписки — откатываем всю транзакцию,
                # чтобы и PromoCodeUse, и атомарный инкремент current_uses откатились.
                await db.rollback()
                return {
                    'success': False,
                    'error': 'select_subscription',
                    'eligible_subscriptions': e.eligible_subscriptions,
                    'code': e.code,
                }
            except ValueError as e:
                # Эффекты не применены — откатываем всю транзакцию (PromoCodeUse + инкремент).
                await db.rollback()
                error_key = str(e)
                if error_key in (
                    'active_discount_exists',
                    'no_subscription_for_days',
                    'subscription_not_found',
                ):
                    return {'success': False, 'error': error_key}
                raise
            balance_after_kopeks = user.balance_kopeks

            if promocode.type == PromoCodeType.SUBSCRIPTION_DAYS.value and promocode.subscription_days > 0:
                from app.utils.user_utils import mark_user_as_had_paid_subscription

                await mark_user_as_had_paid_subscription(db, user)

                logger.info(
                    '🎯 Пользователь получил платную подписку через промокод',
                    _format_user_log=self._format_user_log(user),
                    code=code,
                )

            # Assign promo group if promocode has one
            if promocode.promo_group_id:
                try:
                    # Check if user already has this promo group
                    has_group = await has_user_promo_group(db, user_id, promocode.promo_group_id)

                    if not has_group:
                        # Get promo group details
                        promo_group = await get_promo_group_by_id(db, promocode.promo_group_id)

                        if promo_group:
                            # Add promo group to user
                            await add_user_to_promo_group(
                                db, user_id, promocode.promo_group_id, assigned_by='promocode', commit=False
                            )

                            logger.info(
                                '🎯 Пользователю назначена промогруппа (приоритет: ) через промокод',
                                _format_user_log=self._format_user_log(user),
                                promo_group_name=promo_group.name,
                                priority=promo_group.priority,
                                code=code,
                            )

                            # Add to result description
                            result_description += f'\n🎁 Назначена промогруппа: {promo_group.name}'
                        else:
                            logger.warning(
                                '⚠️ Промогруппа ID не найдена для промокода',
                                promo_group_id=promocode.promo_group_id,
                                code=code,
                            )
                    else:
                        logger.info(
                            'ℹ️ Пользователь уже имеет промогруппу ID',
                            _format_user_log=self._format_user_log(user),
                            promo_group_id=promocode.promo_group_id,
                        )
                except Exception as pg_error:
                    logger.error(
                        '❌ Ошибка назначения промогруппы для пользователя при активации промокода',
                        _format_user_log=self._format_user_log(user),
                        code=code,
                        pg_error=pg_error,
                    )
                    # Don't fail the whole promocode activation if promo group assignment fails

            # current_uses уже инкрементирован атомарно выше (increment_promocode_uses_atomic)
            await db.commit()

            logger.info('✅ Пользователь активировал промокод', _format_user_log=self._format_user_log(user), code=code)

            promocode_data = {
                'code': promocode.code,
                'type': promocode.type,
                'balance_bonus_kopeks': promocode.balance_bonus_kopeks,
                'subscription_days': promocode.subscription_days,
                'max_uses': promocode.max_uses,
                'current_uses': promocode.current_uses + 1,  # +1 because we just incremented atomically
                'valid_until': promocode.valid_until,
                'promo_group_id': promocode.promo_group_id,
            }

            return {
                'success': True,
                'description': result_description,
                'promocode': promocode_data,
                'balance_before_kopeks': balance_before_kopeks,
                'balance_after_kopeks': balance_after_kopeks,
            }

        except Exception as e:
            logger.error('Ошибка активации промокода для пользователя', code=code, user_id=user_id, error=e)
            await db.rollback()
            return {'success': False, 'error': 'server_error'}

    async def _apply_promocode_effects(
        self, db: AsyncSession, user: User, promocode: PromoCode, *, subscription_id: int | None = None
    ) -> str:
        """
        Применяет эффекты промокода к пользователю.

        Args:
            db: Сессия базы данных
            user: Пользователь
            promocode: Промокод

        Returns:
            Описание примененных эффектов

        Raises:
            ValueError: Если у пользователя уже есть активная скидка (для DISCOUNT типа)
        """
        effects = []

        # Обработка DISCOUNT типа (одноразовая скидка)
        if promocode.type == PromoCodeType.DISCOUNT.value:
            # Проверка на наличие активной скидки
            current_discount = getattr(user, 'promo_offer_discount_percent', 0) or 0
            expires_at = getattr(user, 'promo_offer_discount_expires_at', None)

            # Если есть активная скидка (процент > 0 и срок не истек)
            if current_discount > 0:
                if expires_at is None or expires_at > datetime.now(UTC):
                    logger.warning(
                        '⚠️ Пользователь попытался активировать промокод но у него уже есть активная скидка до',
                        _format_user_log=self._format_user_log(user),
                        code=promocode.code,
                        current_discount=current_discount,
                        expires_at=expires_at,
                    )
                    raise ValueError('active_discount_exists')

            # balance_bonus_kopeks хранит процент скидки (1-100)
            discount_percent = promocode.balance_bonus_kopeks
            # subscription_days хранит срок действия скидки в часах (0 = бессрочно до первой покупки)
            discount_hours = promocode.subscription_days

            # Устанавливаем процент скидки
            user.promo_offer_discount_percent = discount_percent
            user.promo_offer_discount_source = f'promocode:{promocode.code}'

            # Устанавливаем срок действия скидки
            if discount_hours > 0:
                user.promo_offer_discount_expires_at = datetime.now(UTC) + timedelta(hours=discount_hours)
                effects.append(f'💸 Получена скидка {discount_percent}% (действует {discount_hours} ч.)')
            else:
                # 0 часов = бессрочно до первой покупки
                user.promo_offer_discount_expires_at = None
                effects.append(f'💸 Получена скидка {discount_percent}% до первой покупки')

            await db.flush()

            logger.info(
                '✅ Пользователю назначена скидка (срок: ч.) по промокоду',
                _format_user_log=self._format_user_log(user),
                discount_percent=discount_percent,
                discount_hours=discount_hours,
                code=promocode.code,
            )

        if promocode.type == PromoCodeType.BALANCE.value and promocode.balance_bonus_kopeks > 0:
            await add_user_balance(db, user, promocode.balance_bonus_kopeks, f'Бонус по промокоду {promocode.code}')

            balance_bonus_rubles = promocode.balance_bonus_kopeks / 100
            effects.append(f'💰 Баланс пополнен на {balance_bonus_rubles}₽')

        if promocode.type == PromoCodeType.SUBSCRIPTION_DAYS.value and promocode.subscription_days > 0:
            # Subscriptions removed in boilerplate — convert to a balance bonus
            # equal to the promocode's balance_bonus_kopeks (if set), else no-op.
            # TODO(boilerplate): re-enable subscription extension if you re-add subs.
            bonus = promocode.balance_bonus_kopeks or 0
            if bonus > 0:
                await add_user_balance(db, user, bonus, f'Бонус по промокоду {promocode.code}')
                effects.append(f'💰 Баланс пополнен на {bonus / 100}₽')
            else:
                effects.append('ℹ️ Промокод активирован, но эффект подписки недоступен в этой сборке')

        if promocode.type == PromoCodeType.TRIAL_SUBSCRIPTION.value:
            # Trial subscriptions removed in boilerplate.
            # TODO(boilerplate): plug your trial activation here.
            effects.append('ℹ️ Триал-промокод активирован, но триальные подписки недоступны в этой сборке')

        return '\n'.join(effects) if effects else '✅ Промокод активирован'

    async def deactivate_discount_promocode(
        self,
        db: AsyncSession,
        user_id: int,
        *,
        admin_initiated: bool = False,
    ) -> dict[str, Any]:
        """
        Деактивирует активный промокод на процентную скидку у пользователя.

        Действия:
        - Сбрасывает promo_offer_discount_percent / source / expires_at на пользователе
        - Удаляет запись PromoCodeUse (чтобы промокод мог быть повторно использован, если max_uses > current_uses)
        - Декрементирует current_uses на промокоде
        - Если промокод назначил промогруппу -- снимает её с пользователя

        Args:
            db: Сессия БД
            user_id: ID пользователя
            admin_initiated: True если деактивацию инициировал админ

        Returns:
            dict с ключами success, error (опционально), deactivated_code (опционально)
        """
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return {'success': False, 'error': 'user_not_found'}

            current_discount = getattr(user, 'promo_offer_discount_percent', 0) or 0
            source = getattr(user, 'promo_offer_discount_source', None)

            if current_discount <= 0 or not source or not source.startswith('promocode:'):
                return {'success': False, 'error': 'no_active_discount_promocode'}

            expires_at = getattr(user, 'promo_offer_discount_expires_at', None)
            # Если скидка уже истекла по времени -- тоже нечего деактивировать
            if expires_at is not None and expires_at <= datetime.now(UTC):
                # Просто зачистим протухшие данные
                user.promo_offer_discount_percent = 0
                user.promo_offer_discount_source = None
                user.promo_offer_discount_expires_at = None
                user.updated_at = datetime.now(UTC)
                await db.commit()
                return {'success': False, 'error': 'discount_already_expired'}

            promocode, promo_use = await get_active_discount_promocode_for_user(db, user_id)

            deactivated_code = source.split(':', 1)[1]

            # 1. Сбрасываем скидку на пользователе
            user.promo_offer_discount_percent = 0
            user.promo_offer_discount_source = None
            user.promo_offer_discount_expires_at = None
            user.updated_at = datetime.now(UTC)

            # 2. Откатываем использование промокода (если нашли запись)
            if promocode and promo_use:
                await db.delete(promo_use)
                if promocode.current_uses > 0:
                    promocode.current_uses -= 1
                    promocode.updated_at = datetime.now(UTC)

                # 3. Если промокод назначал промогруппу -- снимаем её
                if promocode.promo_group_id:
                    from app.database.crud.user_promo_group import (
                        has_user_promo_group,
                        remove_user_from_promo_group,
                    )

                    has_group = await has_user_promo_group(db, user_id, promocode.promo_group_id)
                    if has_group:
                        await remove_user_from_promo_group(db, user_id, promocode.promo_group_id, commit=False)
                        logger.info(
                            'Снята промогруппа ID у пользователя при деактивации промокода',
                            promo_group_id=promocode.promo_group_id,
                            _format_user_log=self._format_user_log(user),
                            deactivated_code=deactivated_code,
                        )

            await db.commit()

            initiator = 'администратором' if admin_initiated else 'пользователем'
            logger.info(
                'Промокод (скидка %) деактивирован для пользователя',
                deactivated_code=deactivated_code,
                current_discount=current_discount,
                initiator=initiator,
                _format_user_log=self._format_user_log(user),
            )

            return {
                'success': True,
                'deactivated_code': deactivated_code,
                'discount_percent': current_discount,
            }

        except Exception as e:
            logger.error('Ошибка деактивации промокода для пользователя', user_id=user_id, error=e)
            await db.rollback()
            return {'success': False, 'error': 'server_error'}
