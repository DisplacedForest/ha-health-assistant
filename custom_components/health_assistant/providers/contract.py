from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..store import DEFAULT_PERSON_ID, MetricType

if TYPE_CHECKING:
    from .sink import ProviderSink


class ProviderError(Exception):
    pass


class ProviderCapabilityError(ProviderError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    metrics: frozenset[MetricType] = frozenset()
    workouts: bool = False
    sleep_sessions: bool = False
    recovery_metrics: frozenset[str] = frozenset()
    can_import: bool = True
    can_export: bool = False


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    degraded: bool = False
    last_success: datetime | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateObservation:
    metric: MetricType
    value: float
    observed_at: datetime
    external_id: str
    unit: str | None = None
    person_id: str = DEFAULT_PERSON_ID
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CandidateWorkout:
    workout_type: str
    started_at: datetime
    ended_at: datetime
    external_id: str
    title: str | None = None
    energy_kcal: float | None = None
    distance: float | None = None
    distance_unit: str | None = None
    person_id: str = DEFAULT_PERSON_ID
    provenance: dict[str, Any] = field(default_factory=dict)


class HealthProvider(ABC):
    @property
    @abstractmethod
    def key(self) -> str: ...

    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @property
    def sleep_source_ids(self) -> frozenset[str]:
        return frozenset()

    @property
    def recovery_source_ids(self) -> frozenset[str]:
        return frozenset()

    @property
    def poll_interval(self) -> timedelta | None:
        return None

    async def async_start(self, sink: ProviderSink) -> None:
        return None

    async def async_stop(self) -> None:
        return None

    async def async_sync(
        self, sink: ProviderSink, state: dict[str, Any]
    ) -> dict[str, Any] | None:
        return None

    async def async_export(self, records: list[Any]) -> None:
        raise NotImplementedError
