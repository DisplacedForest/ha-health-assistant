from __future__ import annotations

import asyncio
import sqlite3
import time
from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_state_report_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .store import StoreError, StoreValidationError
from .store.environment import (
    DAY_MS,
    WINDOW_MS,
    EnvironmentAccumulator,
    EnvironmentRepository,
    normalize_environment,
)

CONF_ENVIRONMENT = "environment_mappings"


def now_ms() -> int:
    return int(dt_util.utcnow().timestamp() * 1000)


@callback
def resolve_mapping(hass: HomeAssistant, mapping: dict, validate: bool = False) -> dict:
    result = dict(mapping)
    registry = er.async_get(hass)
    ref = mapping.get("entity_registry_id")
    entity = registry.async_get(ref or mapping.get("entity_id", ""))
    if ref and (entity is None or entity.disabled_by is not None):
        raise StoreValidationError("Environmental source is unavailable")
    entity_id = entity.entity_id if entity else mapping.get("entity_id", "")
    if not isinstance(entity_id, str) or not entity_id.startswith("sensor."):
        raise StoreValidationError("Choose an environmental sensor")
    if entity:
        result["entity_registry_id"] = entity.id
    result["entity_id"] = entity_id
    result["source_id"] = f"{entity.platform}:{entity.id}" if entity else entity_id
    if not result.get("area_override", False):
        device = (
            dr.async_get(hass).async_get(entity.device_id)
            if entity and entity.device_id
            else None
        )
        result["area_id"] = (entity.area_id if entity else None) or (
            device.area_id if device else None
        )
    area = ar.async_get(hass).async_get_area(result.get("area_id", ""))
    if area is None:
        raise StoreValidationError("Choose an area for this sensor")
    result["area_name"] = area.name
    if validate:
        state = hass.states.get(entity_id)
        if state is None or state.attributes.get("restored"):
            raise StoreValidationError("Environmental source is unavailable")
        normalize_environment(
            result.get("metric", ""),
            state.state,
            state.attributes.get("unit_of_measurement", ""),
        )
    return result


class EnvironmentalCapture:
    def __init__(self, hass, database, mappings, entry_id=None) -> None:
        self.hass = hass
        self.repository = EnvironmentRepository(database)
        self.mappings = mappings
        self.entry_id = entry_id
        self.reloading = False
        self.accumulators = {}
        self.sources = {}
        self.pending = {}
        self.unsubscribers = []
        self.writer = None
        self.maintenance = None
        self.capture_failed = False
        self.mapping_failed = False
        self.stopping = False
        self.last_maintenance = 0

    async def async_start(self) -> None:
        resolved = []
        for mapping in self.mappings:
            try:
                resolved.append(resolve_mapping(self.hass, mapping))
            except StoreValidationError:
                self.mapping_failed = True
        try:
            streams = await self.hass.async_add_executor_job(
                self.repository.register_all, resolved
            )
        except StoreError, sqlite3.Error, OSError:
            self.mapping_failed = True
            streams = []
        timestamp = now_ms()
        for stream in streams:
            initial = await self.hass.async_add_executor_job(
                self.repository.bucket, stream["id"], timestamp // WINDOW_MS * WINDOW_MS
            )
            self.accumulators[stream["id"]] = EnvironmentAccumulator(
                stream["id"], timestamp, initial
            )
            self.sources.setdefault(stream["entity_id"], []).append(stream)
        if self.sources:
            self.unsubscribers.extend(
                [
                    async_track_state_change_event(
                        self.hass, self.sources, self._report
                    ),
                    async_track_state_report_event(
                        self.hass, self.sources, self._report
                    ),
                ]
            )
        if self.entry_id and self.mappings:
            for event_type in (
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                ar.EVENT_AREA_REGISTRY_UPDATED,
            ):
                self.unsubscribers.append(
                    self.hass.bus.async_listen(event_type, self._registry_changed)
                )
        self.unsubscribers.append(
            async_track_time_interval(self.hass, self._tick, timedelta(seconds=30))
        )
        self.maintenance = self.hass.async_create_task(self.async_maintain())

    @callback
    def _registry_changed(self, event) -> None:
        if self.stopping or self.reloading:
            return
        resolved = []
        mapping_failed = False
        for mapping in self.mappings:
            try:
                resolved.append(resolve_mapping(self.hass, mapping))
            except StoreValidationError:
                mapping_failed = True
        current = {
            (
                s["source_id"],
                s["entity_id"],
                s["metric"],
                s["area_id"],
                s["area_name"],
            )
            for sources in self.sources.values()
            for s in sources
        }
        updated = {
            (
                s["source_id"],
                s["entity_id"],
                s["metric"],
                s["area_id"],
                s["area_name"],
            )
            for s in resolved
        }
        changed = current != updated or mapping_failed != self.mapping_failed
        if changed:
            self.reloading = True
            timestamp = int(event.time_fired.timestamp() * 1000)
            for accumulator in self.accumulators.values():
                self._queue(accumulator.stop(timestamp))
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.entry_id)
            )

    @callback
    def _report(self, event) -> None:
        if self.stopping or self.reloading or self.capture_failed:
            return
        state = event.data.get("new_state")
        reported = state.last_reported if state else event.time_fired
        report_us = (reported - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(
            microseconds=1
        )
        timestamp = report_us // 1000
        for stream in self.sources.get(event.data["entity_id"], []):
            value = None
            if state and not state.attributes.get("restored"):
                try:
                    value = normalize_environment(
                        stream["metric"],
                        state.state,
                        state.attributes.get("unit_of_measurement", ""),
                    )
                except StoreValidationError:
                    pass
            self._queue(
                self.accumulators[stream["id"]].report(
                    timestamp, value, report_us=report_us
                )
            )

    @callback
    def _queue(self, buckets) -> None:
        for bucket in buckets:
            key = (bucket.stream_id, bucket.start_ms)
            if len(self.pending) >= 96 and key not in self.pending:
                self.capture_failed = True
                for accumulator in self.accumulators.values():
                    accumulator.value = None
                break
            self.pending[key] = bucket
        if self.pending and (self.writer is None or self.writer.done()):
            self.writer = self.hass.async_create_task(self._drain())

    async def _drain(self) -> None:
        try:
            while self.pending:
                batch = list(self.pending.items())[:48]
                await self.hass.async_add_executor_job(
                    self.repository.save, [bucket for _, bucket in batch], now_ms()
                )
                for key, bucket in batch:
                    if self.pending.get(key) is bucket:
                        self.pending.pop(key)
                await asyncio.sleep(0)
            if self.capture_failed:
                self.capture_failed = False
                timestamp = now_ms()
                for accumulator in self.accumulators.values():
                    accumulator.value = None
                    accumulator.advance(timestamp)
        except StoreError, sqlite3.Error, OSError:
            self.capture_failed = True
            for accumulator in self.accumulators.values():
                accumulator.value = None

    @callback
    def _tick(self, _now) -> None:
        if self.stopping:
            return
        timestamp = now_ms()
        if not self.capture_failed:
            for accumulator in self.accumulators.values():
                self._queue(accumulator.advance(timestamp))
        self._queue([])
        if timestamp - self.last_maintenance >= DAY_MS and (
            self.maintenance is None or self.maintenance.done()
        ):
            self.maintenance = self.hass.async_create_task(self.async_maintain())

    async def async_maintain(self) -> None:
        timestamp = now_ms()
        began = time.monotonic()
        totals = {"rolled_up": 0, "deleted": 0}
        self.last_maintenance = timestamp
        try:
            while not self.stopping:
                result = await self.hass.async_add_executor_job(
                    self.repository.maintain_batch, timestamp
                )
                for key in totals:
                    totals[key] += result[key]
                if not result["more"]:
                    await self.hass.async_add_executor_job(
                        self.repository.database.execute,
                        "UPDATE environment_maintenance SET last_success_ms=?, duration_ms=?, rolled_up=?, deleted=?, failed=0 WHERE id=1",
                        (
                            timestamp,
                            int((time.monotonic() - began) * 1000),
                            totals["rolled_up"],
                            totals["deleted"],
                        ),
                    )
                    break
                await asyncio.sleep(0)
        except StoreError, sqlite3.Error, OSError:
            await self.hass.async_add_executor_job(
                self.repository.database.execute,
                "UPDATE environment_maintenance SET failed=1 WHERE id=1",
            )

    async def async_stop(self) -> None:
        self.stopping = True
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        self.unsubscribers.clear()
        timestamp = now_ms()
        for accumulator in self.accumulators.values():
            self._queue(accumulator.stop(timestamp))
        if self.writer:
            await self.writer
        if self.maintenance:
            await self.maintenance

    def diagnostics(self) -> dict:
        return {
            "active_mappings": len(self.accumulators),
            "capture_failed": self.capture_failed,
            "mapping_failed": self.mapping_failed,
            "pending_buckets": len(self.pending),
        }
