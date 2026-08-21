from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    integration = await async_get_integration(hass, DOMAIN)
    return {
        "domain": DOMAIN,
        "version": str(integration.version),
        "entry": {
            "title": entry.title,
            "state": str(entry.state),
            "options": dict(entry.options),
        },
    }
