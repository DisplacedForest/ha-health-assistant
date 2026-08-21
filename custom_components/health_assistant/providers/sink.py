from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from ..signals import SIGNAL_HEALTH_DATA_UPDATED
from ..store import HealthObservation, HealthRepository, MetricType, Workout
from ..store.units import canonical_unit, convert
from .contract import (
    CandidateObservation,
    CandidateWorkout,
    HealthProvider,
    ProviderCapabilityError,
)


class ProviderSink:
    def __init__(
        self,
        hass: HomeAssistant,
        repository: HealthRepository,
        provider: HealthProvider,
        on_result: Callable[[str, str | None], None],
    ) -> None:
        self._hass = hass
        self._repository = repository
        self._provider = provider
        self._on_result = on_result

    def _require_import(self) -> None:
        if not self._provider.capabilities.can_import:
            raise ProviderCapabilityError(
                f"provider {self._provider.key!r} does not declare import capability"
            )

    async def async_add_observation(
        self, candidate: CandidateObservation
    ) -> HealthObservation:
        self._require_import()
        capabilities = self._provider.capabilities
        if candidate.metric not in capabilities.metrics:
            raise ProviderCapabilityError(
                f"provider {self._provider.key!r} does not declare metric "
                f"{candidate.metric}"
            )
        canonical = canonical_unit(candidate.metric)
        value = convert(candidate.value, candidate.unit or canonical, canonical)
        observation = HealthObservation(
            person_id=candidate.person_id,
            metric=candidate.metric,
            value=value,
            unit=canonical,
            observed_at=candidate.observed_at,
            provider=self._provider.key,
            external_id=candidate.external_id,
            ingested_at=dt_util.utcnow(),
            provenance=dict(candidate.provenance),
        )
        stored = await self._hass.async_add_executor_job(
            self._repository.upsert_observation, observation
        )
        self._on_result(self._provider.key, None)
        async_dispatcher_send(self._hass, SIGNAL_HEALTH_DATA_UPDATED)
        return stored

    async def async_add_workout(self, candidate: CandidateWorkout) -> Workout:
        self._require_import()
        if not self._provider.capabilities.workouts:
            raise ProviderCapabilityError(
                f"provider {self._provider.key!r} does not declare workout capability"
            )
        distance_m = None
        if candidate.distance is not None:
            canonical = canonical_unit(MetricType.DISTANCE)
            distance_m = convert(
                candidate.distance, candidate.distance_unit or canonical, canonical
            )
        workout = Workout(
            person_id=candidate.person_id,
            provider=self._provider.key,
            external_id=candidate.external_id,
            workout_type=candidate.workout_type,
            title=candidate.title,
            started_at=candidate.started_at,
            ended_at=candidate.ended_at,
            energy_kcal=candidate.energy_kcal,
            distance_m=distance_m,
            ingested_at=dt_util.utcnow(),
            provenance=dict(candidate.provenance),
        )
        stored = await self._hass.async_add_executor_job(
            self._repository.upsert_workout, workout
        )
        self._on_result(self._provider.key, None)
        async_dispatcher_send(self._hass, SIGNAL_HEALTH_DATA_UPDATED)
        return stored
