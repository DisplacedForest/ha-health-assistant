from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .store import MetricType, UnitConversionError
from .store.units import canonical_unit, convert

SOURCE_NAMES = {
    "withings": "Withings",
    "fitbit": "Fitbit",
    "garmin_connect": "Garmin Connect",
    "apple_health": "Apple Health bridge",
    "health_connect": "Health Connect bridge",
}
SOURCE_METRICS = {
    "withings": {
        MetricType.WEIGHT: "weight_kg",
        MetricType.BODY_FAT_PERCENTAGE: "fat_ratio_pct",
        MetricType.LEAN_MASS: "fat_free_mass_kg",
        MetricType.STEPS: "activity_steps_today",
        MetricType.DISTANCE: "activity_distance_today",
    },
    "fitbit": {
        MetricType.WEIGHT: "body/weight",
        MetricType.BODY_FAT_PERCENTAGE: "body/fat",
        MetricType.STEPS: "activities/steps",
        MetricType.DISTANCE: "activities/distance",
    },
}


@dataclass(slots=True)
class SourceOffer:
    key: str
    label: str
    config_entry_id: str | None = None
    entities: dict[MetricType, str] = field(default_factory=dict)
    metrics: frozenset[MetricType] = frozenset()
    warnings: list[str] = field(default_factory=list)

    @property
    def choice(self) -> str:
        return (
            f"{self.key}:{self.config_entry_id}" if self.config_entry_id else self.key
        )


def expected_unique_id(source: str, profile: str, metric: MetricType) -> str:
    key = SOURCE_METRICS[source][metric]
    return f"withings_{profile}_{key}" if source == "withings" else f"{profile}_{key}"


def binding_entity(
    hass: HomeAssistant,
    source: str,
    config_entry_id: str,
    metric: MetricType,
    entity_ref: str,
) -> er.RegistryEntry | None:
    entry = hass.config_entries.async_get_entry(config_entry_id)
    if (
        entry is None
        or entry.domain != source
        or entry.disabled_by is not None
        or not entry.unique_id
        or metric not in SOURCE_METRICS.get(source, {})
    ):
        return None
    entity = er.async_get(hass).async_get(entity_ref)
    if (
        entity is None
        or entity.config_entry_id != entry.entry_id
        or entity.platform != source
        or entity.domain != "sensor"
        or entity.disabled_by is not None
        or entity.unique_id != expected_unique_id(source, entry.unique_id, metric)
    ):
        return None
    if entity.device_id:
        device = dr.async_get(hass).async_get(entity.device_id)
        if device is None or entry.entry_id not in device.config_entries:
            return None
    return entity


def valid_source_unit(metric: MetricType, unit: object) -> bool:
    if not isinstance(unit, str) or not unit.strip():
        return False
    try:
        convert(1.0, unit, canonical_unit(metric))
    except UnitConversionError:
        return False
    return True


def discover_sources(hass: HomeAssistant) -> list[SourceOffer]:
    registry = er.async_get(hass)
    offers = []
    entries = hass.config_entries.async_entries()
    account_names = Counter((entry.domain, entry.title) for entry in entries)
    for entry in entries:
        if entry.domain not in SOURCE_NAMES:
            continue
        offer = SourceOffer(
            key=entry.domain,
            label=f"{SOURCE_NAMES[entry.domain]} ({entry.title})",
            config_entry_id=entry.entry_id,
        )
        offers.append(offer)
        if account_names[(entry.domain, entry.title)] > 1:
            offer.warnings.append(
                "More than one account has this name. Rename the integrations in Home Assistant before choosing a source."
            )
            continue
        if entry.disabled_by is not None:
            offer.warnings.append("Integration disabled. Enable it in Home Assistant.")
            continue
        if entry.domain not in SOURCE_METRICS:
            offer.warnings.append(
                "No verified automatic map. Use manual entity mapping."
            )
            continue
        if not entry.unique_id:
            offer.warnings.append(
                "Account identity missing. Use manual entity mapping."
            )
            continue
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        for metric in SOURCE_METRICS[entry.domain]:
            label = metric.value.replace("_", " ")
            expected = expected_unique_id(entry.domain, entry.unique_id, metric)
            matches = [
                e for e in entities if e.unique_id == expected and e.domain == "sensor"
            ]
            if len(matches) != 1:
                reason = "missing" if not matches else "ambiguous"
                offer.warnings.append(f"{label}: {reason} entity.")
                continue
            entity = matches[0]
            if entity.disabled_by is not None:
                offer.warnings.append(f"{label}: {entity.entity_id} is disabled.")
                continue
            if (
                binding_entity(hass, entry.domain, entry.entry_id, metric, entity.id)
                is None
            ):
                offer.warnings.append(
                    f"{label}: entity ownership could not be verified."
                )
                continue
            state = hass.states.get(entity.entity_id)
            if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                offer.warnings.append(f"{label}: {entity.entity_id} is unavailable.")
                continue
            if not valid_source_unit(
                metric, state.attributes.get("unit_of_measurement")
            ):
                offer.warnings.append(
                    f"{label}: {entity.entity_id} has missing or incompatible units."
                )
                continue
            offer.entities[metric] = entity.id
        offer.metrics = frozenset(offer.entities)
    return offers
