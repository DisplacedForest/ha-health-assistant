from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from awesomeversion import AwesomeVersion
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_SOURCE_MAPPINGS, DOMAIN
from .coordinator import HealthSummaryCoordinator
from .environment import CONF_ENVIRONMENT, EnvironmentalCapture
from .panel import async_register_panel, async_remove_panel
from .paths import backup_directory, database_path
from .providers import EntityProvider, ManualProvider, ProviderRegistry
from .providers.curated_entity import CuratedEntityProvider
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
    registry: ProviderRegistry
    coordinator: HealthSummaryCoordinator
    environment: EnvironmentalCapture


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
    if AwesomeVersion(HA_VERSION) < AwesomeVersion("2026.8.0"):
        raise ConfigEntryError(
            "Health Assistant requires Home Assistant 2026.8.0 or later. Upgrade Home Assistant before setup."
        )
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
    registry = ProviderRegistry(hass, repository)
    registry.register(EntityProvider(hass, entry))
    registry.register(ManualProvider())
    for key, binding in entry.options.get(CONF_SOURCE_MAPPINGS, {}).items():
        registry.register(CuratedEntityProvider(hass, key, binding))
    coordinator = HealthSummaryCoordinator(hass, entry, repository)
    environment = EnvironmentalCapture(
        hass, database, entry.options.get(CONF_ENVIRONMENT, []), entry.entry_id
    )
    entry.runtime_data = HealthAssistantData(
        database=database,
        repository=repository,
        registry=registry,
        coordinator=coordinator,
        environment=environment,
    )
    await coordinator.async_config_entry_first_refresh()

    async def _async_data_updated() -> None:
        await coordinator.async_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_HEALTH_DATA_UPDATED, _async_data_updated)
    )
    async_setup_services(hass)
    async_register_websocket_api(hass)
    await async_register_panel(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await registry.async_start()
    await environment.async_start()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.environment.async_stop()
        await entry.runtime_data.registry.async_stop()
        async_remove_panel(hass)
        async_unload_services(hass)
        await hass.async_add_executor_job(entry.runtime_data.database.close)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
