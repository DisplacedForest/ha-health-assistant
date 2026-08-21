from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfMass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import HealthSummary, HealthSummaryCoordinator
from .store import HealthObservation, Workout


@dataclass(frozen=True, kw_only=True)
class HealthSensorDescription(SensorEntityDescription):
    value_fn: Callable[[HealthSummary], Any]
    attributes_fn: Callable[[HealthSummary], dict[str, Any]]


def _observation_attributes(
    observation: HealthObservation | None,
) -> dict[str, Any]:
    if observation is None:
        return {}
    return {
        "observed_at": observation.observed_at.isoformat(),
        "provider": observation.provider,
        "source": observation.external_id,
    }


def _workout_attributes(workout: Workout | None) -> dict[str, Any]:
    if workout is None:
        return {}
    return {
        "workout_type": workout.workout_type,
        "started_at": workout.started_at.isoformat(),
        "ended_at": workout.ended_at.isoformat(),
        "duration_seconds": (workout.ended_at - workout.started_at).total_seconds(),
        "energy_kcal": workout.energy_kcal,
        "distance_m": workout.distance_m,
        "provider": workout.provider,
        "source": workout.external_id,
    }


SENSORS: tuple[HealthSensorDescription, ...] = (
    HealthSensorDescription(
        key="current_weight",
        name="Current weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: s.current_weight.value if s.current_weight else None,
        attributes_fn=lambda s: _observation_attributes(s.current_weight),
    ),
    HealthSensorDescription(
        key="current_body_fat",
        name="Current body fat",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s: s.current_body_fat.value if s.current_body_fat else None,
        attributes_fn=lambda s: _observation_attributes(s.current_body_fat),
    ),
    HealthSensorDescription(
        key="steps_today",
        name="Steps today",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: s.steps_today.value if s.steps_today else None,
        attributes_fn=lambda s: _observation_attributes(s.steps_today),
    ),
    HealthSensorDescription(
        key="active_energy_today",
        name="Active energy today",
        native_unit_of_measurement="kcal",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda s: (
            s.active_energy_today.value if s.active_energy_today else None
        ),
        attributes_fn=lambda s: _observation_attributes(s.active_energy_today),
    ),
    HealthSensorDescription(
        key="latest_workout",
        name="Latest workout",
        value_fn=lambda s: (
            (s.latest_workout.title or s.latest_workout.workout_type)
            if s.latest_workout
            else None
        ),
        attributes_fn=lambda s: _workout_attributes(s.latest_workout),
    ),
    HealthSensorDescription(
        key="workouts_last_7_days",
        name="Workouts last 7 days",
        native_unit_of_measurement="workouts",
        suggested_display_precision=0,
        value_fn=lambda s: s.workouts_last_7_days,
        attributes_fn=lambda s: {},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        HealthSummarySensor(coordinator, description, entry.entry_id)
        for description in SENSORS
    )


class HealthSummarySensor(CoordinatorEntity[HealthSummaryCoordinator], SensorEntity):
    entity_description: HealthSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HealthSummaryCoordinator,
        description: HealthSensorDescription,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        if (
            description.device_class is SensorDeviceClass.WEIGHT
            and coordinator.hass.config.units.mass_unit == UnitOfMass.POUNDS
        ):
            self._attr_suggested_unit_of_measurement = UnitOfMass.POUNDS
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=NAME,
            manufacturer=NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.entity_description.attributes_fn(self.coordinator.data)
