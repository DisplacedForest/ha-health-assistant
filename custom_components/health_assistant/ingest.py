from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import CONF_MAPPINGS, PROVIDER_HA_ENTITY
from .store import (
    DEFAULT_PERSON_ID,
    HealthObservation,
    HealthRepository,
    MetricType,
    StoreValidationError,
    UnitConversionError,
)
from .store.units import canonical_unit, convert

_LOGGER = logging.getLogger(__name__)

_MASS_METRICS = {MetricType.WEIGHT, MetricType.LEAN_MASS}


def default_source_unit(hass: HomeAssistant, metric: MetricType) -> str:
    metric_system = hass.config.units is METRIC_SYSTEM
    if metric in _MASS_METRICS:
        return "kg" if metric_system else "lb"
    if metric is MetricType.DISTANCE:
        return "m" if metric_system else "mi"
    return canonical_unit(metric)


class EntityIngestion:
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        repository: HealthRepository,
    ) -> None:
        self._hass = hass
        self._repository = repository
        self._metric_by_entity: dict[str, MetricType] = {}
        for metric_value, entity_ids in entry.options.get(CONF_MAPPINGS, {}).items():
            try:
                metric = MetricType(metric_value)
            except ValueError:
                _LOGGER.debug("ignoring mapping for unknown metric %r", metric_value)
                continue
            for entity_id in entity_ids:
                self._metric_by_entity[entity_id] = metric
        self._unsubscribe = None

    async def async_start(self) -> None:
        if not self._metric_by_entity:
            return
        self._unsubscribe = async_track_state_change_event(
            self._hass, list(self._metric_by_entity), self._async_handle_event
        )
        for entity_id in self._metric_by_entity:
            await self._async_ingest_state(self._hass.states.get(entity_id))

    @callback
    def async_stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    async def _async_handle_event(self, event: Event[EventStateChangedData]) -> None:
        await self._async_ingest_state(event.data.get("new_state"))

    async def _async_ingest_state(self, state: State | None) -> None:
        if state is None:
            return
        metric = self._metric_by_entity.get(state.entity_id)
        if metric is None:
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
        source_unit = state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        ) or default_source_unit(self._hass, metric)
        try:
            value = convert(raw_value, str(source_unit), canonical_unit(metric))
        except UnitConversionError:
            _LOGGER.debug(
                "ignoring %s: cannot convert unit %r to %s for %s",
                state.entity_id,
                source_unit,
                canonical_unit(metric),
                metric,
            )
            return
        observation = HealthObservation(
            person_id=DEFAULT_PERSON_ID,
            metric=metric,
            value=value,
            unit=canonical_unit(metric),
            observed_at=state.last_updated,
            provider=PROVIDER_HA_ENTITY,
            external_id=state.entity_id,
            ingested_at=dt_util.utcnow(),
            provenance={
                "entity_id": state.entity_id,
                "source_unit": str(source_unit),
                "raw_value": state.state,
            },
        )
        try:
            await self._hass.async_add_executor_job(
                self._repository.upsert_observation, observation
            )
        except StoreValidationError:
            _LOGGER.debug(
                "ignoring %s: rejected by store", state.entity_id, exc_info=True
            )
