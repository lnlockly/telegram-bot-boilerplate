"""Contests routes (stubbed).

Contest participation was gated on the removed VPN ``Subscription``
model and prizes extended ``end_date`` / added traffic. The router is
preserved so the front-end keeps a stable URL but currently exposes no
endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/contests', tags=['Cabinet Contests'])
