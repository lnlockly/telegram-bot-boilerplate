"""Admin advertising-campaign routes (stubbed).

Campaigns previously awarded VPN subscription/tariff bonuses to invited
users and joined against ``Subscription``/``Tariff`` to surface stats.
The router is preserved as an empty placeholder until campaigns are
re-implemented for the boilerplate's new product model.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/admin/campaigns', tags=['Cabinet Admin Campaigns'])
