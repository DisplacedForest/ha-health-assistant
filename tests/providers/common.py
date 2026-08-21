from datetime import UTC, datetime
from typing import Any

from custom_components.health_assistant.providers import (
    CandidateObservation,
    HealthProvider,
    ProviderCapabilities,
)
from custom_components.health_assistant.store import MetricType

OBSERVED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


class SyntheticProvider(HealthProvider):
    def __init__(
        self,
        key="synthetic",
        capabilities=None,
        poll_interval=None,
        sync=None,
        export=None,
    ):
        self._key = key
        self._capabilities = capabilities or ProviderCapabilities(
            metrics=frozenset({MetricType.WEIGHT}), workouts=True, can_import=True
        )
        self._poll_interval = poll_interval
        self._sync = sync
        self._export = export
        self.sync_calls: list[dict[str, Any]] = []
        self.export_calls: list[list[Any]] = []

    @property
    def key(self):
        return self._key

    @property
    def display_name(self):
        return "Synthetic"

    @property
    def capabilities(self):
        return self._capabilities

    @property
    def poll_interval(self):
        return self._poll_interval

    async def async_sync(self, sink, state):
        self.sync_calls.append(state)
        if self._sync is None:
            return None
        return await self._sync(sink, state)

    async def async_export(self, records):
        self.export_calls.append(records)
        if self._export is not None:
            await self._export(records)


def weight_candidate(external_id="obs-1", value=80.0, unit="kg"):
    return CandidateObservation(
        metric=MetricType.WEIGHT,
        value=value,
        unit=unit,
        observed_at=OBSERVED_AT,
        external_id=external_id,
    )
