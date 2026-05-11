"""Gift subscription routes (stubbed).

The original gift flow purchased VPN tariffs for a recipient via the
removed pricing engine and tariff CRUD. The router is preserved as an
empty placeholder until gifting is rebuilt for the boilerplate's new
product model.
"""

from __future__ import annotations

from fastapi import APIRouter


router = APIRouter(prefix='/gift', tags=['Cabinet Gift'])
