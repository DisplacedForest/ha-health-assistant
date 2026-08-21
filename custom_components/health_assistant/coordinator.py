from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .store import (
    DEFAULT_PERSON_ID,
    HealthObservation,
    HealthRepository,
    MetricType,
    Workout,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HealthSummary:
    current_weight: HealthObservation | None
    current_body_fat: HealthObservation | None
    steps_today: HealthObservation | None
    active_energy_today: HealthObservation | None
    latest_workout: Workout | None
    workouts_last_7_days: int | None


class HealthSummaryCoordinator(DataUpdateCoordinator[HealthSummary]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        repository: HealthRepository,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry)
        self._repository = repository

    async def _async_update_data(self) -> HealthSummary:
        return await self.hass.async_add_executor_job(self._build_summary)

    def _build_summary(self) -> HealthSummary:
        repository = self._repository
        day_start = dt_util.start_of_local_day().astimezone(UTC)
        week_start = dt_util.utcnow() - timedelta(days=7)

        steps_today = max(
            repository.get_observations(
                DEFAULT_PERSON_ID, MetricType.STEPS, start=day_start
            ),
            key=lambda observation: observation.value,
            default=None,
        )
        active_energy_today = max(
            repository.get_observations(
                DEFAULT_PERSON_ID, MetricType.ACTIVE_ENERGY, start=day_start
            ),
            key=lambda observation: observation.value,
            default=None,
        )
        latest_workout = repository.latest_workout(DEFAULT_PERSON_ID)
        workouts_last_7_days = (
            None
            if latest_workout is None
            else len(repository.get_workouts(DEFAULT_PERSON_ID, start=week_start))
        )
        return HealthSummary(
            current_weight=repository.latest_observation(
                DEFAULT_PERSON_ID, MetricType.WEIGHT
            ),
            current_body_fat=repository.latest_observation(
                DEFAULT_PERSON_ID, MetricType.BODY_FAT_PERCENTAGE
            ),
            steps_today=steps_today,
            active_energy_today=active_energy_today,
            latest_workout=latest_workout,
            workouts_last_7_days=workouts_last_7_days,
        )
