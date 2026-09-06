from __future__ import annotations

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from ..sources import SOURCE_NAMES, binding_entity, valid_source_unit
from ..store import MetricType, StoreValidationError, UnitConversionError
from .contract import CandidateObservation, HealthProvider, ProviderCapabilities
from .sink import ProviderSink


class CuratedEntityProvider(HealthProvider):
    def __init__(self, hass: HomeAssistant, key: str, binding: dict) -> None:
        self._hass = hass
        self._key = key
        self._entry_id = binding["config_entry_id"]
        self._entities = {
            MetricType(metric): ref for metric, ref in binding["entities"].items()
        }
        self._sink: ProviderSink | None = None
        self._unsubscribe = None

    @property
    def key(self) -> str:
        return self._key

    @property
    def display_name(self) -> str:
        return SOURCE_NAMES[self.key]

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(metrics=frozenset(self._entities))

    async def async_start(self, sink: ProviderSink) -> None:
        self._sink = sink
        self._unsubscribe = self._hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._async_event
        )
        for metric, ref in self._entities.items():
            entity = binding_entity(self._hass, self.key, self._entry_id, metric, ref)
            if entity is not None:
                await self._async_ingest(
                    metric, ref, self._hass.states.get(entity.entity_id)
                )

    async def async_stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._sink = None

    async def _async_event(self, event) -> None:
        state = event.data.get("new_state")
        if state is None:
            return
        for metric, ref in self._entities.items():
            entity = binding_entity(self._hass, self.key, self._entry_id, metric, ref)
            if entity is not None and state.entity_id == entity.entity_id:
                await self._async_ingest(metric, ref, state)

    async def _async_ingest(self, metric, ref, state) -> None:
        if (
            self._sink is None
            or state is None
            or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        ):
            return
        unit = state.attributes.get("unit_of_measurement")
        if not valid_source_unit(metric, unit):
            return
        try:
            value = float(state.state)
        except ValueError:
            return
        try:
            await self._sink.async_add_observation(
                CandidateObservation(
                    metric=metric,
                    value=value,
                    unit=unit,
                    observed_at=state.last_updated,
                    external_id=ref,
                    provenance={
                        "integration": self.key,
                        "config_entry_id": self._entry_id,
                        "entity_id": state.entity_id,
                        "source_unit": unit,
                        "raw_value": state.state,
                    },
                )
            )
        except StoreValidationError, UnitConversionError:
            return
