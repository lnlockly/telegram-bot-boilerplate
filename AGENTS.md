# AGENTS.md

Read this first. This file is the entry point for AI agents working on this codebase.

## What this is

A Telegram-bot boilerplate with admin panel, payment system, and marketing tools (promocodes, referrals, broadcasts, campaigns, contests). It was forked from a Remnawave VPN-selling bot — all VPN business logic was stripped out. **You plug in your own product on top.**

## What's inside, what's not

| ✅ Included | ❌ Removed |
|---|---|
| User registration, profile, balance | VPN subscriptions, tariffs, server selection |
| 25+ payment providers (YooKassa, CryptoBot, Telegram Stars, Tribute, etc.) | Trial activation, traffic monitoring, autopay |
| Promocodes (% / fixed amount / balance bonus) | Remnawave panel sync |
| Referral system + withdrawals + contests | Squad / server / device management |
| Promo groups (per-cohort discounts) | Pricing engine for periods/devices/traffic |
| Broadcasts, campaigns, S2S postbacks | All `app.handlers.subscription.*` handlers |
| Web admin (cabinet) + REST API (webapi) | All `app.services.{remnawave_*, subscription_*, trial_*, traffic_*}` |
| RBAC (admin roles, audit log) | |
| Localization (5 languages: ru, en, fa, ua, zh) | |
| Tickets, FAQ, polls, contests, news, public offer | |

**Important:** payment success handlers (`app/services/payment/*.py`) currently only **credit user balance**. Subscription-creation paths were stripped and marked with `# TODO: post-payment business logic` — that's where you wire your product.

## Tech stack

- **Python 3.11+**, async throughout
- **aiogram 3** (Telegram bot framework)
- **SQLAlchemy 2.0** (async, with Alembic migrations)
- **PostgreSQL** + **Redis**
- **FastAPI** (cabinet web admin + webapi REST)
- **pydantic-settings** (config from env)
- **structlog** (structured logging)

## Project layout

```
telegram-bot-boilerplate/
├── main.py                    # Entry point: starts bot polling + web servers
├── app/
│   ├── bot.py                 # Aiogram dispatcher, middleware wiring, handler registration
│   ├── bot_factory.py         # Creates Bot/Dispatcher instances
│   ├── config.py              # Settings (pydantic-settings, ~2500 lines)
│   ├── states.py              # All FSM state groups
│   ├── database/
│   │   ├── models.py          # SQLAlchemy models (single file, ~3300 lines)
│   │   ├── database.py        # Engine, session factory
│   │   └── crud/              # One file per entity (e.g. user.py, transaction.py)
│   ├── handlers/              # Telegram handlers
│   │   ├── start.py, menu.py, common.py, balance/, referral.py, promocode.py
│   │   ├── tickets.py, support.py, contests.py, polls.py
│   │   ├── stars_payments.py  # Telegram Stars
│   │   ├── webhooks.py        # External webhook callbacks
│   │   └── admin/             # Admin panel handlers (33 files)
│   ├── keyboards/             # Inline keyboards (inline.py, admin.py)
│   ├── services/              # Business logic
│   │   ├── payment/           # Payment-success handlers per provider
│   │   ├── payment_service.py # Aggregator across all providers
│   │   ├── *_service.py       # ~50 service modules
│   │   └── menu_layout/       # Configurable main-menu button layouts
│   ├── middlewares/           # auth, blacklist, channel_checker, etc.
│   ├── external/              # 3rd-party API clients & webhook endpoints
│   ├── cabinet/               # FastAPI web admin
│   │   ├── routes/            # Admin & user routes
│   │   ├── auth/              # JWT + Telegram auth
│   │   └── schemas/           # Pydantic response schemas
│   ├── webapi/                # FastAPI public REST API
│   │   ├── routes/
│   │   └── schemas/
│   ├── webserver/             # Unified webhook server (ASGI app)
│   ├── utils/                 # decorators, formatters, cache, validators
│   ├── localization/          # i18n
│   │   ├── locales/*.json     # ru, en, fa, ua, zh
│   │   ├── default_locales/   # Bundled defaults (yml)
│   │   └── texts.py           # Localization loader
│   └── lib/nalogo/            # Russian fiscal receipts (NaloGO)
├── migrations/                # Alembic
├── tests/                     # pytest
├── docs/                      # Project docs (legacy from VPN era — partly outdated)
└── requirements.txt
```

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pycryptodome
cp .env.example .env  # fill BOT_TOKEN, DATABASE_URL, REDIS_URL
alembic upgrade head
python main.py
```

`main.py` boots: bot polling (or webhook), cabinet (port from `WEB_API_PORT`), webapi, unified webserver, scheduled tasks (broadcasts, campaigns, contest rotation, payment verification).

## Where to make changes — common recipes

### Add a new menu button

1. **Keyboard:** `app/keyboards/inline.py` → `get_main_menu_keyboard` — add `InlineKeyboardButton(text=..., callback_data="my_feature")`.
2. **Handler:** create `app/handlers/my_feature.py`:
   ```python
   from aiogram import F, Router
   router = Router()

   @router.callback_query(F.data == "my_feature")
   async def handle_my_feature(callback, db_user, ...):
       await callback.message.edit_text("Hi from my feature")

   def register_handlers(dp):
       dp.include_router(router)
   ```
3. **Wire it:** `app/bot.py` — add `from app.handlers.my_feature import register_handlers as register_my_feature` and call `register_my_feature(dp)` in `setup_bot()`.
4. **Localization:** add a key in `app/localization/locales/*.json` and use via `texts.t("MY_FEATURE_TITLE", "fallback text")`.

### Add a new payment provider

1. **Provider client:** `app/services/<name>_service.py` — singleton with `create_invoice()`, `verify_callback()`.
2. **Webhook receiver:** `app/external/<name>_webhook.py` (FastAPI router) — registered in `app/webserver/unified_app.py`.
3. **Payment-success handler mixin:** `app/services/payment/<name>.py` — `class <Name>PaymentMixin` with `_process_<name>_success(...)`. Mixed into `PaymentService` via `app/services/payment_service.py`.
4. **CRUD model:** new table for the provider's payment records → `app/database/models.py` + `app/database/crud/<name>.py`.
5. **User-facing handlers:** `app/handlers/balance/<name>.py` — top-up flow buttons.
6. **Config:** add `<NAME>_ENABLED`, `<NAME>_API_KEY` etc. in `app/config.py` Settings class + `.env.example`.
7. **Migration:** `alembic revision --autogenerate -m "add <name> payments"`.

### Add a new admin panel section

1. **Handler:** `app/handlers/admin/<name>.py` with `register_handlers(dp)`.
2. **Wire:** `app/handlers/admin/__init__.py` — add to imports.
3. **Keyboard:** `app/keyboards/admin.py` → `get_admin_main_keyboard` — add the entry button.
4. **RBAC permission:** if needed, register in `app/services/rbac_bootstrap_service.py`.

### Add a new database entity

1. **Model:** `app/database/models.py` — add a class inheriting `Base`.
2. **CRUD:** `app/database/crud/<entity>.py` — `create_*`, `get_*`, `update_*`, `delete_*` async functions taking `db: AsyncSession`.
3. **Migration:** `alembic revision --autogenerate -m "add <entity>"`.
4. Use it in services / handlers via the CRUD layer — never write raw queries in handlers.

### Plug your business logic into payment success

Open `app/services/payment_service.py` and the per-provider files in `app/services/payment/*.py`. Search for `# TODO: post-payment business logic`. The default behavior is `add_user_balance(...)`. Replace with: create your subscription/order/license, send success message, fire S2S postback (`s2s_postback_service`), trigger Yandex offline conversions (`yandex_offline_conv_service`), credit referral (`referral_service.process_referral_earning`).

## Patterns to follow

- **Always async.** All DB calls, all I/O.
- **Sessions:** get a session via `async with AsyncSessionLocal() as db:` or via DI in handlers (`db: AsyncSession` is injected by middleware).
- **Localization:** never hardcode user-facing strings — go through `texts.t(key, fallback, **fmt)`.
- **Logging:** `logger = structlog.get_logger(__name__)` at top of each module.
- **Errors:** wrap handlers with `@error_handler` from `app.utils.decorators`.
- **Admin gating:** `@admin_required` from `app.utils.decorators`.
- **Money:** stored in **kopeks** (1₽ = 100 kopeks). All amounts are `int`. UI formatting via `app.utils.formatters`.
- **No comments unless non-obvious.** The code is supposed to be self-documenting.
- **No backwards-compat shims.** This is a boilerplate — fork it and reshape it.

## ⚠️ Security must-fix before production

A security audit found **4 CRITICAL** and **7 HIGH** issues inherited from the upstream VPN bot. Read [`SECURITY_AUDIT.md`](./SECURITY_AUDIT.md) before deploying. Top hits:

- **CRITICAL:** `CABINET_JWT_SECRET` falls back to `BOT_TOKEN` (`app/config.py:2321`). Make it mandatory.
- **CRITICAL:** Telegram Stars payment is NOT idempotent — Telegram retries credit balance twice (`app/services/payment/stars.py:78`).
- **CRITICAL:** Tribute webhook confuses `user_id` vs `telegram_id` + double-bookkeeping (`app/handlers/webhooks.py:25`).
- **CRITICAL:** Promocode redemption has a TOCTOU race — single-use code can be redeemed by N concurrent users (`app/services/promocode_service.py:185`).
- **HIGH:** YooKassa webhook only IP-validated, signature ignored (`app/external/yookassa_webhook.py:246`).
- **HIGH:** Float arithmetic on money in CryptoBot / CloudPayments paths.
- **HIGH:** No webhook replay protection across any provider.

## Known stubs / loose ends

These were stripped but kept as no-op stubs so imports work:

- `app/handlers/admin/users.py` — admin user-detail panels still reference deleted Subscription objects in handler bodies. Imports cleanly but clicking VPN-related actions raises AttributeError. **Strip or repurpose for your product.**
- `app/handlers/admin/bot_configuration.py` — `botcfg_test_remnawave` callback is a no-op stub.
- `app/handlers/admin/promo_offers.py` — `get_display_subscription_link` is a stub returning `None`.
- `app/services/system_settings_service.py` — `refresh_period_prices` / `refresh_traffic_prices` / `refresh_classic_period_prices` / `clear_db_period_prices` are no-ops.
- `app/services/promo_offer_service.py`, `app/services/wheel_service.py`, `app/services/campaign_service.py` — many functions return early when their VPN dependencies are gone.
- `app/states.py` — `AdminStates` retains stub `State()` entries for legacy admin handlers (`adding_traffic`, `extending_subscription`, `editing_user_devices`, etc.) so handlers register at import time. They're unreachable from the boilerplate's keyboards.
- `WheelPrizeType.SUBSCRIPTION_DAYS` / `.TRAFFIC_GB` — wheel-of-fortune prize enum values still exist; rendering code returns no-op.
- `User.has_had_paid_subscription`, `User.restriction_subscription`, `PromoCode.subscription_days`, `TransactionType.SUBSCRIPTION_PAYMENT` — column/enum survivors that are conceptually about subscriptions but harmless to keep until you decide your product's data model.
- Some Pydantic schemas in `app/cabinet/schemas/users.py` still expose `subscription`, `tariff`, `traffic` fields — they'll just be `null` in API responses.
- `tests/` — VPN-specific test files were deleted. Remaining tests cover payment / promo / referral / RBAC.
- `docs/` — legacy docs from the VPN era; **outdated**.

## Migrations

The original VPN-era migration chain was deleted and replaced with a single fresh `initial` migration generated from the current models. Apply it on a clean database:

```bash
alembic upgrade head
```

Two manual edits live in the generated migration file and must be preserved when you regenerate:
- `import app.database.models` near the top (custom types are referenced fully-qualified).
- All `app.database.models.AwareDateTime(timezone=True)` were replaced with `sa.DateTime(timezone=True)` — `AwareDateTime` is a TypeDecorator that does not accept constructor args, so autogenerate emits a broken call.

Regen after a model change:

```bash
alembic revision --autogenerate -m "your_message"
# then fix any AwareDateTime references in the new file (see above)
```

## Database support

**Production-ready: PostgreSQL only.** Tested with PostgreSQL 17.

The codebase declares `aiosqlite` in requirements, but SQLite mode is **broken** out of the box: 10 columns use `postgresql.JSONB`, which SQLite's compiler refuses to emit. If you want SQLite for local dev, you'll need to replace those columns with `JSON().with_variant(JSONB(), 'postgresql')`. Until then, run Postgres locally (Docker or Homebrew).

### Neon (serverless Postgres)

Neon works, with two gotchas the boilerplate already handles:

1. **SSL:** asyncpg ignores `?sslmode=require` in the DSN. `app/database/database.py` parses the query param and passes `ssl=…` via `connect_args` automatically.
2. **PgBouncer pooled endpoint:** Neon's pooled host (`*-pooler.region.aws.neon.tech`) is PgBouncer transaction-mode; asyncpg prepared statements break there. The boilerplate auto-detects `-pooler.` in the hostname and disables the statement cache (`statement_cache_size=0`, `prepared_statement_cache_size=0`).

Use a Neon DSN with the `+asyncpg` driver prefix:

```bash
DATABASE_URL='postgresql+asyncpg://USER:PASS@ep-foo-pooler.us-east-2.aws.neon.tech/dbname?sslmode=require'
alembic upgrade head
python main.py
```

For a non-pooled (direct) Neon endpoint, the statement cache stays enabled — slightly faster but with Neon's connection limits.

### Smoke-test the DB end-to-end

```bash
python scripts/smoke_test_db.py
# or against a fresh local sqlite (limited — fails on table creation due to JSONB)
python scripts/smoke_test_db.py --sqlite
```

## Verifying imports after a refactor

```bash
BOT_TOKEN=000:fake DATABASE_URL=sqlite+aiosqlite:///:memory: \
  REDIS_URL=redis://localhost:6379/0 BACKUP_LOCATION=/tmp/bp-backups \
  python -c "import app.bot; import main; print('OK')"
```

Should print `OK`. If `ImportError: cannot import name 'X' from 'app.database.models'`, that name was deleted from models — find the import with `grep -rn "import.*\\bX\\b" app/` and stub it.

## When in doubt

- **Don't reintroduce VPN concepts.** No "subscription URLs", "server squads", "trial periods", "traffic GB" — those belong to the original product.
- **Reuse, don't duplicate.** Payment, promo, referral, broadcast infrastructure is mature. Wire your feature through it instead of inventing parallel code paths.
- **Migrations are forward-only.** Generate a new migration; don't edit committed ones.
- **Test by running.** `python main.py` with a real bot token in a sandbox group is the fastest feedback loop.
