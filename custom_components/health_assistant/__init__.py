from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN
from .store import HealthDatabase, HealthRepository, StoreError, StoreVersionError

PLATFORMS: list[Platform] = []


@dataclass(slots=True)
class HealthAssistantData:
    database: HealthDatabase
    repository: HealthRepository


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
    entry.runtime_data = HealthAssistantData(
        database=database, repository=HealthRepository(database)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.async_add_executor_job(entry.runtime_data.database.close)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: HealthAssistantConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
