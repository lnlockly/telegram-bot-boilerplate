"""Mixin для платежей Tribute — простая вспомогательная обвязка."""

from __future__ import annotations

from app.config import settings
from app.utils.payment_logger import payment_logger as logger


class TributePaymentMixin:
    """Содержит методы создания платежей и проверки webhook от Tribute."""

    async def create_tribute_payment(
        self,
        amount_kopeks: int,
        user_id: int,
        description: str,
    ) -> str:
        """Возвращает URL чекаута Tribute, если он сконфигурирован.

        Tribute не предоставляет публичного API для построения checkout URL
        прямо из кода — администратор должен задать ссылку через переменную
        окружения ``TRIBUTE_DONATIONS_URL`` (или ``TRIBUTE_DONATE_LINK``).
        Пока это значение не задано, метод поднимает ``NotImplementedError``
        вместо генерации неработоспособного placeholder-URL.
        """
        if not settings.TRIBUTE_ENABLED:
            raise ValueError('Tribute payments are disabled')

        donations_url = (
            getattr(settings, 'TRIBUTE_DONATIONS_URL', None)
            or getattr(settings, 'TRIBUTE_DONATE_LINK', None)
        )
        if not donations_url:
            raise NotImplementedError(
                'Tribute checkout URL must be configured in TRIBUTE_DONATIONS_URL; '
                'see https://tribute.tg docs'
            )

        separator = '&' if '?' in donations_url else '?'
        payment_url = (
            f'{donations_url}{separator}amount={amount_kopeks}&user_id={user_id}'
        )

        logger.info(
            'Создан Tribute платеж',
            amount_kopeks=amount_kopeks,
            user_id=user_id,
            description=description,
        )
        return payment_url
