"""Monitoring service stub.

The original VPN bot ran a heavyweight monitoring loop that:
- expired/extended subscriptions and synced them with RemnaWave
- processed autopayments / trial reminders / traffic warnings
- emitted discount offers and ticket SLA escalations

All subscription/RemnaWave/tariff/traffic logic has been removed for the
boilerplate. What remains is:
- a no-op ``start_monitoring`` / ``stop_monitoring`` lifecycle
- generic ``MonitoringLog`` accessors used by webapi/admin handlers

TODO(boilerplate): plug your own periodic background work here (cleanup of
inactive users, ticket SLA, low-balance alerts, etc.).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal
from app.database.models import MonitoringLog


logger = structlog.get_logger(__name__)


class MonitoringService:
    """Lightweight monitoring loop placeholder."""

    def __init__(self, bot=None):
        self.is_running = False
        self.bot = bot
        self._task: asyncio.Task | None = None
        self._sla_task = None

    async def start_monitoring(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        logger.info('Monitoring service started (boilerplate stub)')
        # TODO(boilerplate): start your periodic tasks here.
        try:
            while self.is_running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        finally:
            self.is_running = False
            logger.info('Monitoring service stopped')

    def stop_monitoring(self) -> None:
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def get_monitoring_status(self, db: AsyncSession) -> dict[str, Any]:
        return {
            'is_running': self.is_running,
            'note': 'boilerplate stub',
        }

    async def force_check_subscriptions(self, db: AsyncSession) -> dict[str, int]:
        # Subscriptions no longer exist; nothing to do.
        return {'checked': 0, 'expired': 0, 'extended': 0, 'errors': 0}

    async def _log_monitoring_event(
        self,
        db: AsyncSession,
        event_type: str,
        message: str,
        is_success: bool = True,
        data: dict | None = None,
    ) -> None:
        try:
            log = MonitoringLog(
                event_type=event_type,
                message=message,
                is_success=is_success,
                data=data,
            )
            db.add(log)
            await db.commit()
        except Exception as e:
            logger.warning('Failed to write MonitoringLog', error=e)

    async def get_monitoring_logs(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[MonitoringLog]:
        stmt = select(MonitoringLog)
        if event_type:
            stmt = stmt.where(MonitoringLog.event_type == event_type)
        stmt = stmt.order_by(MonitoringLog.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_monitoring_logs_count(self, db: AsyncSession, event_type: str | None = None) -> int:
        from sqlalchemy import func

        stmt = select(func.count(MonitoringLog.id))
        if event_type:
            stmt = stmt.where(MonitoringLog.event_type == event_type)
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    async def get_monitoring_event_types(self, db: AsyncSession) -> list[str]:
        result = await db.execute(select(MonitoringLog.event_type).distinct())
        return [row[0] for row in result.all() if row[0]]

    async def cleanup_old_logs(self, db: AsyncSession, days: int = 30) -> int:
        from sqlalchemy import delete

        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = delete(MonitoringLog).where(MonitoringLog.created_at < cutoff)
        result = await db.execute(stmt)
        await db.commit()
        return int(result.rowcount or 0)


monitoring_service = MonitoringService()
