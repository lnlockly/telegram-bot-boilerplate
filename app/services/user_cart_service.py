"""Generic Redis-backed user cart service.

In the original VPN bot this stored subscription/tariff configuration.
The boilerplate version is provider-agnostic: it just persists arbitrary
JSON-serialisable cart payloads keyed by user id.

TODO(boilerplate): adapt this to your product's cart schema or remove if
your product has no checkout flow.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis
import structlog

from app.config import settings


logger = structlog.get_logger(__name__)


class UserCartService:
    """Persist a small JSON cart per user in Redis with TTL."""

    def __init__(self):
        self._redis_client: redis.Redis | None = None
        self._initialized: bool = False

    def _get_redis_client(self) -> redis.Redis | None:
        if self._initialized:
            return self._redis_client
        try:
            self._redis_client = redis.from_url(settings.REDIS_URL)
            self._initialized = True
        except Exception as e:
            logger.warning('Cannot connect to Redis for cart', error=e)
            self._redis_client = None
            self._initialized = True
        return self._redis_client

    @staticmethod
    def _key(user_id: int) -> str:
        return f'user_cart:{user_id}'

    async def save_user_cart(self, user_id: int, cart_data: dict[str, Any], ttl: int | None = None) -> bool:
        client = self._get_redis_client()
        if client is None:
            return False
        try:
            effective_ttl = ttl if ttl is not None else getattr(settings, 'CART_TTL_SECONDS', 3600)
            await client.setex(self._key(user_id), effective_ttl, json.dumps(cart_data, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error('Failed to save user cart', user_id=user_id, error=e)
            return False

    async def get_user_cart(self, user_id: int) -> dict[str, Any] | None:
        client = self._get_redis_client()
        if client is None:
            return None
        try:
            raw = await client.get(self._key(user_id))
            if not raw:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.error('Failed to read user cart', user_id=user_id, error=e)
            return None

    async def delete_user_cart(self, user_id: int) -> bool:
        client = self._get_redis_client()
        if client is None:
            return False
        try:
            await client.delete(self._key(user_id))
            return True
        except Exception as e:
            logger.error('Failed to delete user cart', user_id=user_id, error=e)
            return False


user_cart_service = UserCartService()
