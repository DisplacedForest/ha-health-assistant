from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN


def database_path(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(".storage", DOMAIN, "health.sqlite"))


def backup_directory(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(".storage", DOMAIN, "backups"))
