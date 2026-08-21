from __future__ import annotations

from ..const import PROVIDER_MANUAL
from ..store import MetricType
from .contract import HealthProvider, ProviderCapabilities


class ManualProvider(HealthProvider):
    @property
    def key(self) -> str:
        return PROVIDER_MANUAL

    @property
    def display_name(self) -> str:
        return "Manual entry"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            metrics=frozenset(MetricType),
            workouts=True,
            can_import=True,
        )
