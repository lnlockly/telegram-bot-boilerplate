"""Fortune Wheel service.

The original VPN bot allowed paying for spins with subscription days and
awarding subscription-days / traffic-GB prizes. In the boilerplate the
wheel only supports Stars (balance) payments and credits any "subscription
days" / "traffic GB" prizes to the user balance instead.

TODO(boilerplate): swap the no-op subscription/traffic prize handlers for
your own product-specific reward logic.
"""

from __future__ import annotations

import random
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.user import add_user_balance
from app.database.crud.wheel import (
    create_wheel_spin,
    get_or_create_wheel_config,
    get_user_spins_today,
    get_wheel_prizes,
    get_wheel_statistics,
)
from app.database.models import (
    PromoCode,
    PromoCodeType,
    User,
    WheelConfig,
    WheelPrize,
    WheelPrizeType,
    WheelSpinPaymentType,
)


logger = structlog.get_logger(__name__)


@dataclass
class SpinResult:
    success: bool
    prize_id: int | None = None
    prize_type: str | None = None
    prize_value: int = 0
    prize_display_name: str = ''
    emoji: str = '🎁'
    color: str = '#3B82F6'
    rotation_degrees: float = 0.0
    message: str = ''
    promocode: str | None = None
    error: str | None = None


@dataclass
class EligibleSubscription:
    """Kept as a typed placeholder for backward-compatible API responses."""

    id: int
    tariff_name: str | None
    days_left: int


@dataclass
class SpinAvailability:
    can_spin: bool
    reason: str | None = None
    spins_remaining_today: int = 0
    can_pay_stars: bool = False
    can_pay_days: bool = False
    min_subscription_days: int = 0
    user_subscription_days: int = 0
    user_balance_kopeks: int = 0
    required_balance_kopeks: int = 0
    eligible_subscriptions: list[EligibleSubscription] | None = None


class FortuneWheelService:
    def __init__(self):
        pass

    async def check_availability(self, db: AsyncSession, user: User) -> SpinAvailability:
        config = await get_or_create_wheel_config(db)
        if not config.is_enabled:
            return SpinAvailability(can_spin=False, reason='wheel_disabled')

        spins_today = await get_user_spins_today(db, user.id)
        spins_remaining = config.daily_spin_limit - spins_today if config.daily_spin_limit > 0 else 999
        if config.daily_spin_limit > 0 and spins_today >= config.daily_spin_limit:
            return SpinAvailability(can_spin=False, reason='daily_limit_reached', spins_remaining_today=0)

        can_pay_stars = False
        required_balance_kopeks = 0
        if config.spin_cost_stars_enabled and config.spin_cost_stars > 0:
            stars_rate = Decimal(str(settings.get_stars_rate()))
            rubles = Decimal(config.spin_cost_stars) * stars_rate
            required_balance_kopeks = int(rubles * 100)
            if user.balance_kopeks >= required_balance_kopeks:
                can_pay_stars = True

        # Subscription-day payments are removed in the boilerplate.
        can_pay_days = False

        if not can_pay_stars and not can_pay_days:
            reason = 'no_payment_method_available'
            if config.spin_cost_stars_enabled and user.balance_kopeks < required_balance_kopeks:
                reason = 'insufficient_balance'
            return SpinAvailability(
                can_spin=False,
                reason=reason,
                spins_remaining_today=spins_remaining,
                can_pay_stars=can_pay_stars,
                can_pay_days=can_pay_days,
                user_balance_kopeks=user.balance_kopeks,
                required_balance_kopeks=required_balance_kopeks,
            )

        prizes = await get_wheel_prizes(db, config.id, active_only=True)
        if not prizes:
            return SpinAvailability(can_spin=False, reason='no_prizes_configured')

        return SpinAvailability(
            can_spin=True,
            spins_remaining_today=spins_remaining,
            can_pay_stars=can_pay_stars,
            can_pay_days=can_pay_days,
            user_balance_kopeks=user.balance_kopeks,
            required_balance_kopeks=required_balance_kopeks,
        )

    def calculate_prize_probabilities(
        self, config: WheelConfig, prizes: list[WheelPrize], spin_cost_kopeks: int
    ) -> list[tuple[WheelPrize, float]]:
        if not prizes:
            return []
        target_payout = spin_cost_kopeks * (config.rtp_percent / 100)

        manual_prizes: list[tuple[WheelPrize, float]] = []
        auto_prizes: list[WheelPrize] = []
        manual_prob_sum = 0.0
        for prize in prizes:
            if prize.manual_probability is not None and prize.manual_probability > 0:
                manual_prizes.append((prize, prize.manual_probability))
                manual_prob_sum += prize.manual_probability
            else:
                auto_prizes.append(prize)

        remaining_prob = max(0, 1.0 - manual_prob_sum)
        if not auto_prizes or remaining_prob <= 0:
            if manual_prizes:
                total = sum(p[1] for p in manual_prizes)
                return [(p[0], p[1] / total) for p in manual_prizes]
            return []

        weights = []
        for prize in auto_prizes:
            if prize.prize_value_kopeks > 0:
                weight = target_payout / prize.prize_value_kopeks
            else:
                weight = 1.0
            weights.append((prize, max(weight, 0.01)))
        total_weight = sum(w[1] for w in weights)
        auto_probabilities = [(prize, (weight / total_weight) * remaining_prob) for prize, weight in weights]

        result = manual_prizes + auto_probabilities
        total = sum(p[1] for p in result)
        if total > 0:
            result = [(p[0], p[1] / total) for p in result]
        return result

    def _select_prize(self, prizes_with_probabilities: list[tuple[WheelPrize, float]]) -> WheelPrize:
        if not prizes_with_probabilities:
            raise ValueError('No prizes to select from')
        rand = random.random()
        cumulative = 0.0
        for prize, probability in prizes_with_probabilities:
            cumulative += probability
            if rand <= cumulative:
                return prize
        return prizes_with_probabilities[-1][0]

    def _calculate_rotation(self, prizes: list[WheelPrize], selected_prize: WheelPrize) -> float:
        if not prizes:
            return 0.0
        prize_index = next((i for i, p in enumerate(prizes) if p.id == selected_prize.id), 0)
        sector_angle = 360 / len(prizes)
        base_angle = prize_index * sector_angle + sector_angle / 2
        offset = random.uniform(-sector_angle * 0.3, sector_angle * 0.3)
        stop_angle = 360 - base_angle + offset
        full_rotations = random.randint(5, 8) * 360
        return full_rotations + stop_angle

    async def _process_stars_payment(self, db: AsyncSession, user: User, config: WheelConfig) -> int:
        stars_rate = Decimal(str(settings.get_stars_rate()))
        rubles = Decimal(config.spin_cost_stars) * stars_rate
        kopeks = int(rubles * 100)

        from app.database.crud.user import lock_user_for_update

        user = await lock_user_for_update(db, user)
        if user.balance_kopeks < kopeks:
            raise ValueError('Недостаточно средств на балансе')
        user.balance_kopeks -= kopeks
        return kopeks

    async def _apply_prize(
        self,
        db: AsyncSession,
        user: User,
        prize: WheelPrize,
        config: WheelConfig,
        subscription: Any | None = None,
    ) -> str | None:
        prize_type = prize.prize_type

        if prize_type == WheelPrizeType.NOTHING.value:
            return None

        if prize_type == WheelPrizeType.BALANCE_BONUS.value:
            await add_user_balance(
                db,
                user,
                prize.prize_value,
                description=f'Выигрыш в колесе удачи: {prize.prize_value / 100:.2f}₽',
                create_transaction=True,
            )
            return None

        if prize_type in (WheelPrizeType.SUBSCRIPTION_DAYS.value, WheelPrizeType.TRAFFIC_GB.value):
            # Subscriptions/traffic are not modelled in the boilerplate;
            # convert the prize to its rouble equivalent and credit the balance.
            await add_user_balance(
                db,
                user,
                prize.prize_value_kopeks,
                description=(
                    f'Выигрыш в колесе удачи: {prize.prize_value} (конвертировано в баланс)'
                ),
                create_transaction=True,
            )
            return None

        if prize_type == WheelPrizeType.PROMOCODE.value:
            promocode = await self._generate_prize_promocode(db, user, prize, config)
            return promocode.code

        return None

    async def _generate_prize_promocode(
        self, db: AsyncSession, user: User, prize: WheelPrize, config: WheelConfig
    ) -> PromoCode:
        code = f'{config.promo_prefix}{secrets.token_hex(4).upper()}'
        # Subscription-days promo codes don't extend anything in the boilerplate;
        # always issue a balance promocode.
        promo_type = PromoCodeType.BALANCE.value
        promocode = PromoCode(
            code=code,
            type=promo_type,
            balance_bonus_kopeks=prize.promo_balance_bonus_kopeks or prize.prize_value_kopeks,
            subscription_days=0,
            max_uses=1,
            valid_until=datetime.now(UTC) + timedelta(days=config.promo_validity_days),
            is_active=True,
            created_by=user.id,
        )
        db.add(promocode)
        await db.flush()
        return promocode

    async def spin(
        self, db: AsyncSession, user: User, payment_type: str, *, subscription_id: int | None = None
    ) -> SpinResult:
        try:
            availability = await self.check_availability(db, user)
            if not availability.can_spin:
                return SpinResult(
                    success=False,
                    error=availability.reason,
                    message=self._get_error_message(availability.reason),
                )

            config = await get_or_create_wheel_config(db)
            prizes = await get_wheel_prizes(db, config.id, active_only=True)
            if not prizes:
                return SpinResult(success=False, error='no_prizes', message='Призы не настроены')

            if payment_type == WheelSpinPaymentType.TELEGRAM_STARS.value:
                if not availability.can_pay_stars:
                    return SpinResult(success=False, error='cannot_pay_stars', message='Оплата Stars недоступна')
                payment_amount = config.spin_cost_stars
                payment_value_kopeks = await self._process_stars_payment(db, user, config)
            elif payment_type == WheelSpinPaymentType.SUBSCRIPTION_DAYS.value:
                # Subscription-day payment is no longer available in the boilerplate.
                return SpinResult(
                    success=False,
                    error='cannot_pay_days',
                    message='Оплата днями подписки недоступна',
                )
            else:
                return SpinResult(success=False, error='invalid_payment_type', message='Неверный способ оплаты')

            prizes_with_probs = self.calculate_prize_probabilities(config, prizes, payment_value_kopeks)
            selected_prize = self._select_prize(prizes_with_probs)
            rotation = self._calculate_rotation(prizes, selected_prize)

            generated_promocode = await self._apply_prize(db, user, selected_prize, config)
            promocode_id = None
            if generated_promocode:
                from sqlalchemy import text

                result = await db.execute(
                    text('SELECT id FROM promocodes WHERE code = :code'), {'code': generated_promocode}
                )
                row = result.fetchone()
                if row:
                    promocode_id = row[0]

            await create_wheel_spin(
                db=db,
                user_id=user.id,
                prize_id=selected_prize.id,
                payment_type=payment_type,
                payment_amount=payment_amount,
                payment_value_kopeks=payment_value_kopeks,
                prize_type=selected_prize.prize_type,
                prize_value=selected_prize.prize_value,
                prize_display_name=selected_prize.display_name,
                prize_value_kopeks=selected_prize.prize_value_kopeks,
                generated_promocode_id=promocode_id,
                is_applied=True,
            )
            await db.commit()

            message = self._get_prize_message(selected_prize, generated_promocode)
            return SpinResult(
                success=True,
                prize_id=selected_prize.id,
                prize_type=selected_prize.prize_type,
                prize_value=selected_prize.prize_value,
                prize_display_name=selected_prize.display_name,
                emoji=selected_prize.emoji,
                color=selected_prize.color,
                rotation_degrees=rotation,
                message=message,
                promocode=generated_promocode,
            )
        except ValueError as e:
            await db.rollback()
            return SpinResult(success=False, error='payment_error', message=str(e))
        except Exception as e:
            await db.rollback()
            logger.exception('Wheel spin error', user_id=user.id, error=e)
            return SpinResult(success=False, error='internal_error', message='Произошла ошибка, попробуйте позже')

    def _get_error_message(self, reason: str | None) -> str:
        messages = {
            'wheel_disabled': 'Колесо удачи временно недоступно',
            'daily_limit_reached': 'Вы достигли лимита спинов на сегодня',
            'no_payment_method_available': 'Нет доступных способов оплаты',
            'no_prizes_configured': 'Призы еще не настроены',
            'insufficient_balance': 'Недостаточно средств на балансе. Пополните баланс для оплаты спина.',
        }
        return messages.get(reason, 'Произошла ошибка')

    def _get_prize_message(self, prize: WheelPrize, promocode: str | None) -> str:
        prize_type = prize.prize_type
        if prize_type == WheelPrizeType.NOTHING.value:
            return 'К сожалению, в этот раз не повезло. Попробуйте еще!'
        if prize_type == WheelPrizeType.BALANCE_BONUS.value:
            return f'Поздравляем! Вы выиграли {prize.prize_value / 100:.0f}₽ на баланс!'
        if prize_type == WheelPrizeType.SUBSCRIPTION_DAYS.value:
            return f'Поздравляем! Бонус начислен на баланс ({prize.prize_value_kopeks / 100:.0f}₽).'
        if prize_type == WheelPrizeType.TRAFFIC_GB.value:
            return f'Поздравляем! Бонус начислен на баланс ({prize.prize_value_kopeks / 100:.0f}₽).'
        if prize_type == WheelPrizeType.PROMOCODE.value:
            return f'Поздравляем! Ваш промокод: {promocode}'
        return 'Поздравляем с выигрышем!'

    async def get_statistics(
        self, db: AsyncSession, date_from: datetime | None = None, date_to: datetime | None = None
    ) -> dict[str, Any]:
        return await get_wheel_statistics(db, date_from, date_to)


wheel_service = FortuneWheelService()
