"""Public landing page routes (stubbed).

The original landing/quick-purchase flow listed VPN tariffs and routed
guest checkouts through the removed pricing engine. The router is
preserved as an empty placeholder until landings are rebuilt for the
boilerplate's new product model.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/landing', tags=['Cabinet Landing'])
