from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store.wearable import WearableRepository


class WearableRuntime:
    def __init__(self, hass, database, bridge, *, clock=None):
        self.hass = hass
        self.repository = WearableRepository(database)
        self.bridge = bridge
        self.clock = clock or (lambda: datetime.now(UTC))
        self._task = None
        self._unsubscribe = None
        self._stopped = False
        self.last_maintenance = None

    async def async_start(self):
        self.bridge.register_wearable_handler(
            self.repository.apply_batch,
            tip=self.repository.tip,
            validate_pending=self.repository.validate_pending,
        )
        await self.async_maintain()
        if self._stopped:
            return
        self._unsubscribe = async_track_time_interval(
            self.hass, self.async_maintain, timedelta(hours=1)
        )

    async def _maintain(self):
        result = await self.hass.async_add_executor_job(
            self.repository.maintain, self.clock()
        )
        self.last_maintenance = result
        if result["changed_streams"] or result["degraded_streams"]:
            async_dispatcher_send(self.hass, SIGNAL_HEALTH_DATA_UPDATED)
        return result

    async def async_maintain(self, _now=None):
        if self._stopped:
            return self.last_maintenance
        if self._task is None or self._task.done():
            self._task = self.hass.async_create_task(self._maintain())
        task = self._task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await asyncio.shield(task)
            raise
        finally:
            if task.done() and self._task is task:
                self._task = None

    async def async_stop(self):
        self._stopped = True
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._task is not None:
            await asyncio.shield(self._task)
