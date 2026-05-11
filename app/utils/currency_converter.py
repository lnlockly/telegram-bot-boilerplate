from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import aiohttp
import structlog

from app.config import settings


logger = structlog.get_logger(__name__)


class CurrencyConverter:
    def __init__(self):
        self._cache: dict[str, Decimal] = {}
        self._cache_ttl = 3600  # 1 час
        self._last_update: dict[str, datetime] = {}

    async def get_usd_to_rub_rate(self) -> Decimal | None:
        """Получает курс USD/RUB с кешированием.

        Возвращает ``None``, если ни один источник недоступен и кеш пуст.
        Никакого 1:1 или хардкодного fallback курса — вызывающий код обязан
        отказать в начислении, чтобы не недокредитить пользователя в ~100 раз.
        """

        cache_key = 'USD_RUB'
        now = datetime.now(UTC)

        # Проверяем кеш
        if (
            cache_key in self._cache
            and cache_key in self._last_update
            and (now - self._last_update[cache_key]).seconds < self._cache_ttl
        ):
            return self._cache[cache_key]

        # Получаем новый курс
        rate = await self._fetch_exchange_rate()

        if rate is not None:
            self._cache[cache_key] = rate
            self._last_update[cache_key] = now
            logger.info('Обновлен курс USD/RUB', rate=str(rate))
            return rate

        # Возвращаем из кеша если API недоступен
        if cache_key in self._cache:
            logger.warning('API курсов недоступен, используем кешированный курс')
            return self._cache[cache_key]

        # NO fallback. Caller MUST treat None as a hard failure and refuse to
        # credit. The previous fallback (1:1 or 95.0) under-/over-credited
        # users by orders of magnitude when feeds went down.
        logger.error('Все источники курса USD/RUB недоступны и кеш пуст')
        return None

    async def _fetch_exchange_rate(self) -> Decimal | None:
        """Получает курс с нескольких источников."""

        sources = [self._fetch_from_cbr, self._fetch_from_exchangerate_api]

        if getattr(settings, 'FIXER_API_KEY', None):
            sources.append(self._fetch_from_fixer)

        for source in sources:
            try:
                rate = await source()
                if rate is not None and Decimal('50') < rate < Decimal('200'):
                    return rate
            except Exception as e:
                logger.debug('Ошибка получения курса из источника', source=source.__name__, error=e)
                continue

        return None

    @staticmethod
    def _coerce_decimal(value) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    async def _fetch_from_cbr(self) -> Decimal | None:
        """Получает курс с сайта ЦБ РФ."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get('https://www.cbr-xml-daily.ru/daily_json.js') as response:
                    if response.status == 200:
                        data = await response.json()
                        usd_rate = data['Valute']['USD']['Value']
                        return self._coerce_decimal(usd_rate)
        except Exception as e:
            logger.debug('Ошибка получения курса ЦБ', error=e)
            return None
        return None

    async def _fetch_from_exchangerate_api(self) -> Decimal | None:
        """Получает курс с exchangerate-api.com."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get('https://api.exchangerate-api.com/v4/latest/USD') as response:
                    if response.status == 200:
                        data = await response.json()
                        rub_rate = data['rates']['RUB']
                        return self._coerce_decimal(rub_rate)
        except Exception as e:
            logger.debug('Ошибка получения курса exchangerate-api', error=e)
            return None
        return None

    async def _fetch_from_fixer(self) -> Decimal | None:
        """Получает курс с fixer.io (требуется FIXER_API_KEY в settings)."""
        api_key = getattr(settings, 'FIXER_API_KEY', None)
        if not api_key:
            return None
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                url = (
                    'https://api.fixer.io/latest'
                    f'?access_key={api_key}&symbols=USD,RUB'
                )
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            usd_eur = self._coerce_decimal(data['rates'].get('USD'))
                            rub_eur = self._coerce_decimal(data['rates'].get('RUB'))
                            if usd_eur and rub_eur and usd_eur != 0:
                                return rub_eur / usd_eur
        except Exception as e:
            logger.debug('Ошибка получения курса fixer', error=e)
            return None
        return None

    async def usd_to_rub(self, usd_amount) -> Decimal | None:
        """Конвертирует USD в RUB. Возвращает ``None`` при сбое получения курса."""
        rate = await self.get_usd_to_rub_rate()
        if rate is None:
            return None
        amount = self._coerce_decimal(usd_amount)
        if amount is None:
            return None
        return amount * rate

    async def rub_to_usd(self, rub_amount) -> Decimal | None:
        """Конвертирует RUB в USD. Возвращает ``None`` при сбое получения курса."""
        rate = await self.get_usd_to_rub_rate()
        if rate is None or rate == 0:
            return None
        amount = self._coerce_decimal(rub_amount)
        if amount is None:
            return None
        return amount / rate


# Глобальный экземпляр
currency_converter = CurrencyConverter()
