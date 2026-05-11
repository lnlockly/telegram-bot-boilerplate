"""Miniapp endpoints (stubbed).

The original VPN miniapp surface (subscriptions, tariffs, server squads,
trial activation, traffic top-ups, RemnaWave provisioning, etc.) was
removed during the boilerplate conversion. This module retains only a
router placeholder so the FastAPI app can mount the miniapp namespace
without import errors.

Re-introduce concrete endpoints here as the new product features land.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter()


@router.get('/health')
async def miniapp_health() -> dict[str, str]:
    """Lightweight liveness probe for the miniapp namespace."""
    return {'status': 'ok', 'service': 'miniapp'}
