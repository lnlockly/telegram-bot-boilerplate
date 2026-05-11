"""Admin routes for managing users in cabinet (stubbed).

The original admin user management surface was deeply coupled with
RemnaWave subscription provisioning, tariff management, traffic top-ups
and panel synchronisation. All of that VPN-specific functionality was
removed during the boilerplate conversion.

The router is preserved (and still mounted by ``cabinet/routes/__init__``)
so existing import paths keep working. Re-add concrete endpoints here as
the new product features land.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/admin/users', tags=['Cabinet Admin Users'])
