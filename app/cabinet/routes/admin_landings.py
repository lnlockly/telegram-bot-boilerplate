"""Admin landing-page management routes (stubbed).

The previous implementation joined ``GuestPurchase`` rows against the
removed ``Tariff`` model and depended on the VPN subscription pipeline
to settle purchases. Until landings are reworked for the boilerplate's
new product model the router is exposed as an empty placeholder.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/admin/landings', tags=['Cabinet Admin Landings'])
