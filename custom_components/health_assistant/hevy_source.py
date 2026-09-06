from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .providers.contract import CandidateWorkout, ProviderError
from .store import UnitConversionError
from .store.units import convert

MAX_EXERCISES = 100
MAX_SETS = 100
MAX_TOTAL_SETS = 1000
MAX_PAYLOAD_BYTES = 262144
MAX_DURATION_SECONDS = 604800
SUMMARY_ID = re.compile(r"[0-9a-f]{8}_last_workout_summary\Z")


def invalid_workout() -> ProviderError:
    return ProviderError("Hevy completed workout is unavailable or invalid")


def text_value(value, maximum, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise invalid_workout()
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise invalid_workout() from None
    return value.strip()


def number_value(value, maximum=1e12):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise invalid_workout()
    if value < 0 or value > maximum or not math.isfinite(value):
        raise invalid_workout()
    return float(value)


def converted_value(value, unit, canonical):
    number = number_value(value)
    if not isinstance(unit, str) or len(unit) > 16:
        raise invalid_workout()
    try:
        return round(number_value(convert(number, unit, canonical)), 6)
    except UnitConversionError:
        raise invalid_workout() from None


def parse_workout(state: State, account: str, now: datetime) -> CandidateWorkout:
    if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        raise invalid_workout()
    title = text_value(state.state, 255)
    attrs = state.attributes
    date = text_value(attrs.get("date"), 64)
    try:
        started_at = datetime.fromisoformat(date)
        if started_at.tzinfo is None or started_at.utcoffset() is None:
            raise invalid_workout()
        started_at = started_at.astimezone(UTC)
        duration = (
            number_value(attrs.get("duration_minutes"), MAX_DURATION_SECONDS / 60) * 60
        )
        ended_at = started_at + timedelta(seconds=duration)
    except ValueError, OverflowError:
        raise invalid_workout() from None
    if started_at.year < 1970 or ended_at > now.astimezone(UTC):
        raise invalid_workout()
    exercises = attrs.get("exercises", [])
    if not isinstance(exercises, list) or len(exercises) > MAX_EXERCISES:
        raise invalid_workout()
    if "exercise_count" in attrs:
        count = number_value(attrs["exercise_count"], MAX_EXERCISES)
        if count != len(exercises):
            raise invalid_workout()
    cleaned = []
    total_sets = 0
    distances = []
    for exercise in exercises:
        if not isinstance(exercise, dict):
            raise invalid_workout()
        sets = exercise.get("sets", [])
        if not isinstance(sets, list) or len(sets) > MAX_SETS:
            raise invalid_workout()
        total_sets += len(sets)
        if total_sets > MAX_TOTAL_SETS:
            raise invalid_workout()
        item = {"name": text_value(exercise.get("name"), 200), "sets": []}
        notes = exercise.get("notes")
        if notes is not None and notes != "":
            item["notes"] = text_value(notes, 1000)
        for raw_set in sets:
            if not isinstance(raw_set, dict):
                raise invalid_workout()
            row = {"type": text_value(raw_set.get("type", "normal"), 32)}
            if raw_set.get("weight") is not None:
                row["weight_kg"] = converted_value(
                    raw_set["weight"], raw_set.get("weight_unit"), "kg"
                )
            if raw_set.get("distance") is not None:
                row["distance_m"] = converted_value(
                    raw_set["distance"], raw_set.get("distance_unit"), "m"
                )
                distances.append(row["distance_m"])
            if raw_set.get("reps") is not None:
                reps = number_value(raw_set["reps"], 100000)
                if not reps.is_integer():
                    raise invalid_workout()
                row["reps"] = int(reps)
            if raw_set.get("duration_seconds") is not None:
                row["duration_seconds"] = number_value(
                    raw_set["duration_seconds"], MAX_DURATION_SECONDS
                )
            item["sets"].append(row)
        cleaned.append(item)
    provenance = {
        "integration": "hevy",
        "entity_id": state.entity_id,
        "capture": "latest_completed_workout",
        "exercises": cleaned,
    }
    if attrs.get("total_volume") is not None:
        provenance["total_volume_kg_reps"] = converted_value(
            attrs["total_volume"], attrs.get("total_volume_unit"), "kg"
        )
    if len(json.dumps(provenance, sort_keys=True).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise invalid_workout()
    workout_id = attrs.get("workout_id")
    if workout_id is not None:
        identity = "id:" + text_value(workout_id, 128)
    else:
        header = [started_at.isoformat(), ended_at.isoformat(), title]
        identity = (
            "summary:"
            + hashlib.sha256(
                json.dumps(header, ensure_ascii=False).encode()
            ).hexdigest()
        )
    return CandidateWorkout(
        workout_type="workout",
        title=title,
        started_at=started_at,
        ended_at=ended_at,
        external_id=f"{account}:{identity}",
        distance=sum(distances) if distances else None,
        distance_unit="m" if distances else None,
        provenance=provenance,
    )


def entity_binding(entity: er.RegistryEntry) -> dict:
    return {
        "config_entry_id": entity.config_entry_id,
        "entity_id": entity.id,
        "identity": hashlib.sha256(entity.unique_id.encode()).hexdigest(),
    }


def bound_entity(hass: HomeAssistant, binding: dict) -> er.RegistryEntry | None:
    entry = hass.config_entries.async_get_entry(binding.get("config_entry_id", ""))
    entity = er.async_get(hass).async_get(binding.get("entity_id", ""))
    if (
        entry is None
        or entry.domain != "hevy"
        or entry.disabled_by is not None
        or entity is None
        or entity.disabled_by is not None
        or entity.config_entry_id != entry.entry_id
        or entity.platform != "hevy"
        or entity.domain != "sensor"
        or not SUMMARY_ID.fullmatch(entity.unique_id)
        or entity_binding(entity) != binding
    ):
        return None
    if entity.device_id:
        device = dr.async_get(hass).async_get(entity.device_id)
        if device is None or entry.entry_id not in device.config_entries:
            return None
    return entity


def read_workout(hass: HomeAssistant, binding: dict) -> CandidateWorkout:
    entity = bound_entity(hass, binding)
    state = hass.states.get(entity.entity_id) if entity else None
    if state is None:
        raise invalid_workout()
    return parse_workout(state, binding["config_entry_id"], dt_util.utcnow())


@dataclass(frozen=True, slots=True)
class HevyOffer:
    config_entry_id: str
    label: str
    binding: dict | None
    warning: str | None
    services: frozenset[str]

    @property
    def choice(self):
        return f"hevy:{self.config_entry_id}"


def discover_hevy(hass: HomeAssistant) -> list[HevyOffer]:
    entries = hass.config_entries.async_entries("hevy")
    titles = Counter(entry.title for entry in entries)
    registry = er.async_get(hass)
    services = frozenset(hass.services.async_services().get("hevy", {}))
    offers = []
    for entry in entries:
        candidates = [
            entity
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
            if entity.domain == "sensor"
            and entity.platform == "hevy"
            and SUMMARY_ID.fullmatch(entity.unique_id)
        ]
        warning = None
        binding = None
        if titles[entry.title] > 1:
            warning = "Rename accounts with the same name in Home Assistant before choosing one."
        elif entry.disabled_by is not None:
            warning = "Integration disabled."
        elif len(candidates) != 1:
            warning = "Completed workout summary is missing or ambiguous."
        else:
            binding = entity_binding(candidates[0])
            try:
                read_workout(hass, binding)
            except ProviderError:
                binding = None
                warning = "Completed workout details are unavailable or invalid."
        offers.append(
            HevyOffer(
                entry.entry_id, f"Hevy ({entry.title})", binding, warning, services
            )
        )
    return offers
