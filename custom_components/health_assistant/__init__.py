from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .coordinator import HealthSummaryCoordinator
from .ingest import EntityIngestion
from .services import async_setup_services, async_unload_services
from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store import HealthDatabase, HealthRepository, StoreError, StoreVersionError

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass(slots=True)
class HealthAssistantData:
    database: HealthDatabase
    repository: HealthRepository
    ingestion: EntityIngestion
    coordinator: HealthSummaryCoordinator


type HealthAssistantConfigEntry = ConfigEntry[HealthAssistantData]


def database_path(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(".storage", DOMAIN, "health.sqlite"))


async def async_setup_entry(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> bool:
    database = HealthDatabase(database_path(hass))
    try:
        await hass.async_add_executor_job(database.open)
    except StoreVersionError as err:
        raise ConfigEntryError(str(err)) from err
    except (StoreError, OSError) as err:
        raise ConfigEntryNotReady(str(err)) from err
    repository = HealthRepository(database)
    ingestion = EntityIngestion(hass, entry, repository)
    coordinator = HealthSummaryCoordinator(hass, entry, repository)
    entry.runtime_data = HealthAssistantData(
        database=database,
        repository=repository,
        ingestion=ingestion,
        coordinator=coordinator,
    )
    await coordinator.async_config_entry_first_refresh()

    async def _async_data_updated() -> None:
        await coordinator.async_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(ingestion.async_stop)
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_HEALTH_DATA_UPDATED, _async_data_updated)
    )
    async_setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await ingestion.async_start()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        async_unload_services(hass)
        await hass.async_add_executor_job(entry.runtime_data.database.close)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
