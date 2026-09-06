from __future__ import annotations

from datetime import timedelta

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

from ..hevy_source import bound_entity, read_workout
from .contract import HealthProvider, ProviderCapabilities, ProviderError


class HevyProvider(HealthProvider):
    def __init__(self, hass, binding, request_sync):
        self._hass = hass
        self._binding = binding
        self._request_sync = request_sync
        self._services = frozenset(hass.services.async_services().get("hevy", {}))
        self._unsubscribers = []
        self._last_entity_id = None

    @property
    def key(self):
        return "hevy"

    @property
    def display_name(self):
        return "Hevy"

    @property
    def capabilities(self):
        try:
            read_workout(self._hass, self._binding)
        except ProviderError:
            return ProviderCapabilities(can_import=False)
        return ProviderCapabilities(workouts=True)

    @property
    def poll_interval(self):
        return timedelta(minutes=1)

    async def async_start(self, sink):
        self._unsubscribers = [
            self._hass.bus.async_listen(event, self._async_event)
            for event in (EVENT_STATE_CHANGED, EVENT_ENTITY_REGISTRY_UPDATED)
        ]
        entity = bound_entity(self._hass, self._binding)
        self._last_entity_id = entity.entity_id if entity else None
        await self._request_sync()

    async def async_stop(self):
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    async def _async_event(self, event):
        entity = bound_entity(self._hass, self._binding)
        current = entity.entity_id if entity else None
        if event.data.get("entity_id") in {current, self._last_entity_id}:
            self._last_entity_id = current or self._last_entity_id
            await self._request_sync()

    async def async_sync(self, sink, state):
        candidate = read_workout(self._hass, self._binding)
        await sink.async_add_workout(candidate)
