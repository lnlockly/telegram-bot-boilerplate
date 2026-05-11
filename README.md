# telegram-bot-boilerplate

Telegram-bot-boilerplate с готовой админкой, платёжной системой и маркетинговыми инструментами. Форк VPN-бота на базе Remnawave с вырезанной продуктовой логикой.

**Что внутри:**
- 25+ платёжных провайдеров (YooKassa, CryptoBot, Telegram Stars, Tribute, Lava, Heleket, FreeKassa, Wata, Platega и др.)
- Промокоды (% / фикс / бонус на баланс), промо-группы, промо-офферы
- Реферальная система: уровни, заработки, выводы, контесты
- Рассылки и рекламные кампании, S2S-постбэки
- Веб-админка (FastAPI cabinet) + REST API (webapi)
- RBAC, аудит-лог, тикеты, опросы, FAQ, новости
- Локализация: ru, en, fa, ua, zh

**Стек:** Python 3.11+, aiogram 3, SQLAlchemy 2.0 (async), PostgreSQL, Redis, FastAPI, Alembic.

## Быстрый старт

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pycryptodome
cp .env.example .env  # заполните BOT_TOKEN, DATABASE_URL, REDIS_URL
alembic upgrade head
python main.py
```

## Документация

**Если вы AI-агент или новый разработчик — читайте [`AGENTS.md`](./AGENTS.md).** Там карта проекта, рецепты для типовых задач (новая кнопка / новый платёжный провайдер / новый раздел админки / новая сущность БД), список заглушек и ловушек.

## Куда подключать свою бизнес-логику

Платёжные хендлеры (`app/services/payment/*.py`) сейчас просто зачисляют деньги на баланс. Точки расширения помечены `# TODO: post-payment business logic` — там вы создаёте свой заказ / подписку / лицензию / что угодно.

## Лицензия

См. [LICENSE](./LICENSE) (унаследовано от исходного проекта).
