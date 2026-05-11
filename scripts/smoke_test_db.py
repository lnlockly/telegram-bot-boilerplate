"""End-to-end smoke test: connect, create tables from models, run a basic CRUD.

Usage:
    DATABASE_URL='postgresql+asyncpg://user:pass@host/db?sslmode=require' \
        python scripts/smoke_test_db.py

Or for Neon (pooled):
    DATABASE_URL='postgresql+asyncpg://user:pass@ep-foo-pooler.region.aws.neon.tech/dbname?sslmode=require' \
        python scripts/smoke_test_db.py

Or SQLite in-memory (no env required):
    python scripts/smoke_test_db.py --sqlite
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path


def _bootstrap_env() -> None:
    os.environ.setdefault('BOT_TOKEN', '000:fake-for-smoke-test')
    os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
    os.environ.setdefault('BACKUP_LOCATION', '/tmp/bp-smoke-backups')
    if '--sqlite' in sys.argv:
        os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
    elif not os.environ.get('DATABASE_URL'):
        sys.exit('DATABASE_URL is not set. Pass --sqlite for an in-memory run.')


_bootstrap_env()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database.database import AsyncSessionLocal, close_db, engine  # noqa: E402
from app.database.models import Base, User  # noqa: E402


async def main() -> int:
    started = time.time()
    print(f'→ Engine URL: {engine.url.render_as_string(hide_password=True)}')
    print(f'→ Dialect:    {engine.dialect.name} (driver: {engine.dialect.driver})')

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('✓ create_all OK')

    async with AsyncSessionLocal() as session:
        user = User(telegram_id=999_000_001, username='smoke', language='ru', balance_kopeks=0)
        session.add(user)
        await session.commit()
        print(f'✓ insert user.id={user.id}')

        result = await session.execute(select(User).where(User.telegram_id == 999_000_001))
        loaded = result.scalar_one()
        assert loaded.username == 'smoke', f'username mismatch: {loaded.username!r}'
        print(f'✓ select OK (id={loaded.id}, balance={loaded.balance_kopeks})')

        loaded.balance_kopeks = 12345
        await session.commit()
        await session.refresh(loaded)
        assert loaded.balance_kopeks == 12345
        print('✓ update OK')

        await session.delete(loaded)
        await session.commit()
        print('✓ delete OK')

    await close_db()
    print(f'\n✅ smoke test passed in {time.time() - started:.2f}s')
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
