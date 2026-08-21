from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PROVIDER_MANUAL
from .paths import backup_directory
from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store import (
    DEFAULT_PERSON_ID,
    HealthDatabase,
    HealthObservation,
    HealthRepository,
    MetricType,
    StoreError,
    StoreValidationError,
    UnitConversionError,
    Workout,
)
from .store.units import canonical_unit, convert

SERVICE_ADD_OBSERVATION = "add_observation"
SERVICE_ADD_BODY_MEASUREMENT = "add_body_measurement"
SERVICE_ADD_WORKOUT = "add_workout"
SERVICE_CREATE_BACKUP = "create_backup"

CREATE_BACKUP_SCHEMA = vol.Schema({})

ADD_OBSERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("metric"): vol.In([metric.value for metric in MetricType]),
        vol.Required("value"): vol.Coerce(float),
        vol.Optional("unit"): cv.string,
        vol.Optional("observed_at"): cv.datetime,
        vol.Optional("person_id", default=DEFAULT_PERSON_ID): cv.string,
        vol.Optional("external_id"): cv.string,
        vol.Optional("source"): cv.string,
    }
)

ADD_BODY_MEASUREMENT_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional("weight"): vol.Coerce(float),
            vol.Optional("weight_unit"): cv.string,
            vol.Optional("body_fat_percentage"): vol.Coerce(float),
            vol.Optional("lean_mass"): vol.Coerce(float),
            vol.Optional("lean_mass_unit"): cv.string,
            vol.Optional("observed_at"): cv.datetime,
            vol.Optional("person_id", default=DEFAULT_PERSON_ID): cv.string,
            vol.Optional("external_id"): cv.string,
            vol.Optional("source"): cv.string,
        }
    ),
    cv.has_at_least_one_key("weight", "body_fat_percentage", "lean_mass"),
)

ADD_WORKOUT_SCHEMA = vol.Schema(
    {
        vol.Required("workout_type"): cv.string,
        vol.Optional("title"): cv.string,
        vol.Required("start"): cv.datetime,
        vol.Required("end"): cv.datetime,
        vol.Optional("energy_kcal"): vol.Coerce(float),
        vol.Optional("distance"): vol.Coerce(float),
        vol.Optional("distance_unit"): cv.string,
        vol.Optional("person_id", default=DEFAULT_PERSON_ID): cv.string,
        vol.Optional("external_id"): cv.string,
        vol.Optional("source"): cv.string,
    }
)


def _repository(hass: HomeAssistant) -> HealthRepository:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Health Assistant is not set up")
    return entries[0].runtime_data.repository


def _database(hass: HomeAssistant) -> HealthDatabase:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Health Assistant is not set up")
    return entries[0].runtime_data.database


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return dt_util.utcnow()
    return dt_util.as_utc(value)


def _provenance(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("source")
    return {"source": source} if source else {}


def _convert(value: float, unit: str | None, metric: MetricType) -> float:
    try:
        return convert(value, unit or canonical_unit(metric), canonical_unit(metric))
    except UnitConversionError as err:
        raise ServiceValidationError(str(err)) from err


async def _async_store_observation(
    hass: HomeAssistant, observation: HealthObservation
) -> None:
    repository = _repository(hass)
    try:
        await hass.async_add_executor_job(repository.upsert_observation, observation)
    except StoreValidationError as err:
        raise ServiceValidationError(str(err)) from err
    async_dispatcher_send(hass, SIGNAL_HEALTH_DATA_UPDATED)


async def _async_add_observation(call: ServiceCall) -> None:
    data = call.data
    metric = MetricType(data["metric"])
    await _async_store_observation(
        call.hass,
        HealthObservation(
            person_id=data["person_id"],
            metric=metric,
            value=_convert(data["value"], data.get("unit"), metric),
            unit=canonical_unit(metric),
            observed_at=_as_utc(data.get("observed_at")),
            provider=PROVIDER_MANUAL,
            external_id=data.get("external_id") or uuid.uuid4().hex,
            ingested_at=dt_util.utcnow(),
            provenance=_provenance(data),
        ),
    )


async def _async_add_body_measurement(call: ServiceCall) -> None:
    data = call.data
    observed_at = _as_utc(data.get("observed_at"))
    base_id = data.get("external_id") or uuid.uuid4().hex
    values = {
        MetricType.WEIGHT: (data.get("weight"), data.get("weight_unit")),
        MetricType.BODY_FAT_PERCENTAGE: (data.get("body_fat_percentage"), None),
        MetricType.LEAN_MASS: (data.get("lean_mass"), data.get("lean_mass_unit")),
    }
    for metric, (value, unit) in values.items():
        if value is None:
            continue
        await _async_store_observation(
            call.hass,
            HealthObservation(
                person_id=data["person_id"],
                metric=metric,
                value=_convert(value, unit, metric),
                unit=canonical_unit(metric),
                observed_at=observed_at,
                provider=PROVIDER_MANUAL,
                external_id=f"{base_id}-{metric.value}",
                ingested_at=dt_util.utcnow(),
                provenance=_provenance(data),
            ),
        )


async def _async_add_workout(call: ServiceCall) -> None:
    data = call.data
    distance = data.get("distance")
    workout = Workout(
        person_id=data["person_id"],
        provider=PROVIDER_MANUAL,
        external_id=data.get("external_id") or uuid.uuid4().hex,
        workout_type=data["workout_type"],
        title=data.get("title"),
        started_at=_as_utc(data["start"]),
        ended_at=_as_utc(data["end"]),
        energy_kcal=data.get("energy_kcal"),
        distance_m=None
        if distance is None
        else _convert(distance, data.get("distance_unit"), MetricType.DISTANCE),
        ingested_at=dt_util.utcnow(),
        provenance=_provenance(data),
    )
    repository = _repository(call.hass)
    try:
        await call.hass.async_add_executor_job(repository.upsert_workout, workout)
    except StoreValidationError as err:
        raise ServiceValidationError(str(err)) from err
    async_dispatcher_send(call.hass, SIGNAL_HEALTH_DATA_UPDATED)


async def _async_create_backup(call: ServiceCall) -> ServiceResponse:
    database = _database(call.hass)
    stamp = dt_util.utcnow().strftime("%Y%m%d%H%M%S")
    destination = backup_directory(call.hass) / f"health-{stamp}.sqlite"
    try:
        await call.hass.async_add_executor_job(database.backup, destination)
    except (StoreError, OSError) as err:
        raise HomeAssistantError(f"backup failed: {err}") from err
    if call.return_response:
        return {"path": str(destination)}
    return None


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_ADD_OBSERVATION):
        return
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_OBSERVATION,
        _async_add_observation,
        schema=ADD_OBSERVATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BODY_MEASUREMENT,
        _async_add_body_measurement,
        schema=ADD_BODY_MEASUREMENT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_WORKOUT,
        _async_add_workout,
        schema=ADD_WORKOUT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_BACKUP,
        _async_create_backup,
        schema=CREATE_BACKUP_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    hass.services.async_remove(DOMAIN, SERVICE_ADD_OBSERVATION)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_BODY_MEASUREMENT)
    hass.services.async_remove(DOMAIN, SERVICE_ADD_WORKOUT)
    hass.services.async_remove(DOMAIN, SERVICE_CREATE_BACKUP)
