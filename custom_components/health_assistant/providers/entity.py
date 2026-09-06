from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from ..const import CONF_MAPPINGS, PROVIDER_HA_ENTITY
from ..store import MetricType, StoreValidationError, UnitConversionError
from ..store.units import canonical_unit
from .contract import CandidateObservation, HealthProvider, ProviderCapabilities
from .sink import ProviderSink

_LOGGER = logging.getLogger(__name__)

_MASS_METRICS = {MetricType.WEIGHT, MetricType.LEAN_MASS}


def default_source_unit(hass: HomeAssistant, metric: MetricType) -> str:
    metric_system = hass.config.units is METRIC_SYSTEM
    if metric in _MASS_METRICS:
        return "kg" if metric_system else "lb"
    if metric is MetricType.DISTANCE:
        return "m" if metric_system else "mi"
    return canonical_unit(metric)


class EntityProvider(HealthProvider):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._metrics_by_entity: dict[str, list[MetricType]] = {}
        for metric_value, entity_ids in entry.options.get(CONF_MAPPINGS, {}).items():
            try:
                metric = MetricType(metric_value)
            except ValueError:
                _LOGGER.debug("ignoring mapping for unknown metric %r", metric_value)
                continue
            for entity_id in entity_ids:
                metrics = self._metrics_by_entity.setdefault(entity_id, [])
                if metric not in metrics:
                    metrics.append(metric)
        self._sink: ProviderSink | None = None
        self._unsubscribe = None

    @property
    def key(self) -> str:
        return PROVIDER_HA_ENTITY

    @property
    def display_name(self) -> str:
        return "Home Assistant entities"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            metrics=frozenset(
                metric
                for metrics in self._metrics_by_entity.values()
                for metric in metrics
            ),
            can_import=True,
        )

    async def async_start(self, sink: ProviderSink) -> None:
        self._sink = sink
        if not self._metrics_by_entity:
            return
        self._unsubscribe = async_track_state_change_event(
            self._hass, list(self._metrics_by_entity), self._async_handle_event
        )
        for entity_id in self._metrics_by_entity:
            await self._async_ingest_state(self._hass.states.get(entity_id))

    async def async_stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    async def _async_handle_event(self, event: Event[EventStateChangedData]) -> None:
        await self._async_ingest_state(event.data.get("new_state"))

    async def _async_ingest_state(self, state: State | None) -> None:
        if state is None or self._sink is None:
            return
        metrics = self._metrics_by_entity.get(state.entity_id)
        if not metrics:
            return
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            _LOGGER.debug("ignoring %s: state is %s", state.entity_id, state.state)
            return
        try:
            raw_value = float(state.state)
        except ValueError:
            _LOGGER.debug(
                "ignoring %s: non-numeric state %r", state.entity_id, state.state
            )
            return
        for metric in metrics:
            source_unit = state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            ) or default_source_unit(self._hass, metric)
            candidate = CandidateObservation(
                metric=metric,
                value=raw_value,
                unit=str(source_unit),
                observed_at=state.last_updated,
                external_id=state.entity_id,
                provenance={
                    "entity_id": state.entity_id,
                    "source_unit": str(source_unit),
                    "raw_value": state.state,
                },
            )
            try:
                await self._sink.async_add_observation(candidate)
            except UnitConversionError:
                _LOGGER.debug(
                    "ignoring %s: cannot convert unit %r to %s for %s",
                    state.entity_id,
                    source_unit,
                    canonical_unit(metric),
                    metric,
                )
            except StoreValidationError:
                _LOGGER.debug(
                    "ignoring %s: rejected by store", state.entity_id, exc_info=True
                )
