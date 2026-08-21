from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from ..store import HealthRepository
from .contract import (
    HealthProvider,
    ProviderCapabilityError,
    ProviderError,
    ProviderStatus,
)
from .sink import ProviderSink

_LOGGER = logging.getLogger(__name__)

DEFAULT_SYNC_TIMEOUT = 300.0


class ProviderRegistry:
    def __init__(
        self,
        hass: HomeAssistant,
        repository: HealthRepository,
        sync_timeout: float = DEFAULT_SYNC_TIMEOUT,
    ) -> None:
        self._hass = hass
        self._repository = repository
        self._sync_timeout = sync_timeout
        self._providers: dict[str, HealthProvider] = {}
        self._sinks: dict[str, ProviderSink] = {}
        self._statuses: dict[str, ProviderStatus] = {}
        self._timers: list[CALLBACK_TYPE] = []
        self._sync_locks: dict[str, asyncio.Lock] = {}

    @property
    def providers(self) -> Mapping[str, HealthProvider]:
        return MappingProxyType(self._providers)

    def register(self, provider: HealthProvider) -> None:
        key = provider.key
        if key in self._providers:
            raise ProviderError(f"provider {key!r} is already registered")
        self._providers[key] = provider
        self._sinks[key] = ProviderSink(
            self._hass, self._repository, provider, self._record_result
        )
        self._statuses[key] = ProviderStatus()
        self._sync_locks[key] = asyncio.Lock()

    def sink(self, key: str) -> ProviderSink:
        return self._sinks[key]

    def status(self, key: str) -> ProviderStatus:
        return self._statuses[key]

    @property
    def statuses(self) -> Mapping[str, ProviderStatus]:
        return MappingProxyType(self._statuses)

    def _record_result(self, key: str, error: str | None) -> None:
        if error is None:
            self._statuses[key] = ProviderStatus(
                degraded=False,
                last_success=dt_util.utcnow(),
                last_error=self._statuses[key].last_error,
            )
        else:
            self._statuses[key] = ProviderStatus(
                degraded=True,
                last_success=self._statuses[key].last_success,
                last_error=error,
            )

    async def async_start(self) -> None:
        for key, provider in self._providers.items():
            try:
                await provider.async_start(self._sinks[key])
            except Exception as err:
                _LOGGER.exception("provider %s failed to start", key)
                self._record_result(key, str(err))
                continue
            interval = provider.poll_interval
            if interval is not None:
                self._timers.append(
                    async_track_time_interval(
                        self._hass,
                        self._make_sync_listener(key),
                        interval,
                    )
                )

    def _make_sync_listener(self, key: str):
        async def _listener(now: Any) -> None:
            await self.async_sync(key)

        return _listener

    async def async_stop(self) -> None:
        for timer in self._timers:
            timer()
        self._timers.clear()
        for key, provider in self._providers.items():
            try:
                await provider.async_stop()
            except Exception:
                _LOGGER.exception("provider %s failed to stop", key)

    async def async_sync(self, key: str) -> None:
        provider = self._providers[key]
        async with self._sync_locks[key]:
            try:
                state = await self._hass.async_add_executor_job(
                    self._repository.get_provider_state, key
                )
                async with asyncio.timeout(self._sync_timeout):
                    new_state = await provider.async_sync(self._sinks[key], state)
                if new_state is not None:
                    await self._hass.async_add_executor_job(
                        self._repository.set_provider_state, key, new_state
                    )
            except Exception as err:
                _LOGGER.exception("provider %s sync failed", key)
                self._record_result(key, str(err) or type(err).__name__)
                return
        self._record_result(key, None)

    async def async_export(self, key: str, records: list[Any]) -> None:
        provider = self._providers[key]
        if not provider.capabilities.can_export:
            raise ProviderCapabilityError(
                f"provider {key!r} does not declare export capability"
            )
        try:
            async with asyncio.timeout(self._sync_timeout):
                await provider.async_export(records)
        except ProviderCapabilityError:
            raise
        except Exception as err:
            _LOGGER.exception("provider %s export failed", key)
            self._record_result(key, str(err))
            raise
        self._record_result(key, None)
