"""Admin broadcast routes (stubbed).

Broadcast targeting was tightly coupled to the removed VPN subscription
tariff filters. The router is preserved as an empty placeholder so it
can be re-implemented against the new product targeting model.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/admin/broadcasts', tags=['Cabinet Admin Broadcasts'])
