"""Admin bulk-action routes (stubbed).

The original bulk action endpoints (extend/cancel/activate subscription,
change tariff, add traffic, grant subscription, etc.) were tightly tied
to the removed RemnaWave subscription stack. The router is kept as a
placeholder so it can be re-populated with non-VPN bulk actions later.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/admin/bulk-actions', tags=['Cabinet Admin Bulk Actions'])
