from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .coordinator import HealthSummaryCoordinator
from .ingest import EntityIngestion
from .panel import async_register_panel, async_remove_panel
from .paths import backup_directory, database_path
from .services import async_setup_services, async_unload_services
from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store import (
    HealthDatabase,
    HealthRepository,
    StoreCorruptError,
    StoreError,
    StoreVersionError,
)
from .websocket_api import async_register_websocket_api

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass(slots=True)
class HealthAssistantData:
    database: HealthDatabase
    repository: HealthRepository
    ingestion: EntityIngestion
    coordinator: HealthSummaryCoordinator


type HealthAssistantConfigEntry = ConfigEntry[HealthAssistantData]


__all__ = ["backup_directory", "database_path"]

ISSUE_DATABASE_CORRUPT = "database_corrupt"
ISSUE_DATABASE_UNSUPPORTED = "database_unsupported_version"


def _raise_database_issue(
    hass: HomeAssistant, issue_id: str, path: Path, err: Exception
) -> None:
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=issue_id,
        translation_placeholders={"path": str(path), "error": str(err)},
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> bool:
    database = HealthDatabase(database_path(hass))
    try:
        await hass.async_add_executor_job(database.open)
    except StoreVersionError as err:
        _raise_database_issue(hass, ISSUE_DATABASE_UNSUPPORTED, database.path, err)
        raise ConfigEntryError(str(err)) from err
    except StoreCorruptError as err:
        _raise_database_issue(hass, ISSUE_DATABASE_CORRUPT, database.path, err)
        raise ConfigEntryError(str(err)) from err
    except (StoreError, OSError) as err:
        raise ConfigEntryNotReady(str(err)) from err
    ir.async_delete_issue(hass, DOMAIN, ISSUE_DATABASE_CORRUPT)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_DATABASE_UNSUPPORTED)
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
    async_register_websocket_api(hass)
    await async_register_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await ingestion.async_start()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        async_remove_panel(hass)
        async_unload_services(hass)
        await hass.async_add_executor_job(entry.runtime_data.database.close)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
