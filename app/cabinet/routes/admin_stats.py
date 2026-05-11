"""Admin statistics dashboard routes (stubbed).

The original admin dashboard combined RemnaWave node data, subscription
stats, server squad stats and tariff stats. All of those data sources
were removed during the boilerplate conversion. The router is kept so
new dashboard endpoints can be added without re-wiring registration.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/admin/stats', tags=['Cabinet Admin Stats'])
