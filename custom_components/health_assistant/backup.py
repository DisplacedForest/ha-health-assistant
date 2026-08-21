from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_pre_backup(hass: HomeAssistant) -> None:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        await hass.async_add_executor_job(entry.runtime_data.database.checkpoint)


async def async_post_backup(hass: HomeAssistant) -> None:
    return None
