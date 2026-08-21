from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

DEFAULT_PERSON_ID = "primary"


class MetricType(StrEnum):
    WEIGHT = "weight"
    BODY_FAT_PERCENTAGE = "body_fat_percentage"
    LEAN_MASS = "lean_mass"
    STEPS = "steps"
    DISTANCE = "distance"
    ACTIVE_ENERGY = "active_energy"


CANONICAL_UNITS: dict[MetricType, str] = {
    MetricType.WEIGHT: "kg",
    MetricType.BODY_FAT_PERCENTAGE: "%",
    MetricType.LEAN_MASS: "kg",
    MetricType.STEPS: "count",
    MetricType.DISTANCE: "m",
    MetricType.ACTIVE_ENERGY: "kcal",
}

BODY_MEASUREMENT_METRICS = frozenset(
    {MetricType.WEIGHT, MetricType.BODY_FAT_PERCENTAGE, MetricType.LEAN_MASS}
)

DAILY_ACTIVITY_METRICS = frozenset(
    {MetricType.STEPS, MetricType.DISTANCE, MetricType.ACTIVE_ENERGY}
)


class RecordStatus(StrEnum):
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class HealthObservation:
    person_id: str
    metric: MetricType
    value: float
    unit: str
    observed_at: datetime
    provider: str
    external_id: str
    ingested_at: datetime
    provenance: dict[str, Any] = field(default_factory=dict)
    status: RecordStatus = RecordStatus.ACTIVE
    id: int | None = None


@dataclass(frozen=True, slots=True)
class Workout:
    person_id: str
    provider: str
    external_id: str
    workout_type: str
    started_at: datetime
    ended_at: datetime
    ingested_at: datetime
    title: str | None = None
    energy_kcal: float | None = None
    distance_m: float | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    status: RecordStatus = RecordStatus.ACTIVE
    id: int | None = None


@dataclass(frozen=True, slots=True)
class BodyMeasurement:
    person_id: str
    observed_at: datetime
    weight_kg: float | None = None
    body_fat_percentage: float | None = None
    lean_mass_kg: float | None = None


@dataclass(frozen=True, slots=True)
class DailyActivity:
    person_id: str
    day: date
    steps: float | None = None
    distance_m: float | None = None
    active_energy_kcal: float | None = None
