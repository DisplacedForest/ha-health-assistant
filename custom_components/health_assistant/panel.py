from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

STATIC_URL = f"/{DOMAIN}_panel_files"
SIDEBAR_TITLE = "Health"
SIDEBAR_ICON = "mdi:heart-pulse"
WEBCOMPONENT_NAME = "health-assistant-panel"

_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    if not hass.data.get(_STATIC_REGISTERED):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL,
                    str(Path(__file__).parent / "frontend" / "dist"),
                    cache_headers=False,
                )
            ]
        )
        hass.data[_STATIC_REGISTERED] = True
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=DOMAIN,
        webcomponent_name=WEBCOMPONENT_NAME,
        sidebar_title=SIDEBAR_TITLE,
        sidebar_icon=SIDEBAR_ICON,
        module_url=f"{STATIC_URL}/panel.js",
        embed_iframe=False,
        require_admin=False,
        config={"domain": DOMAIN},
    )


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    frontend.async_remove_panel(hass, DOMAIN)
