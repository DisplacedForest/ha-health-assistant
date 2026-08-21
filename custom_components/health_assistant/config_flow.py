from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_MAPPINGS, DOMAIN, NAME
from .store import MetricType


def _options_schema(options: dict[str, Any]) -> vol.Schema:
    mappings = options.get(CONF_MAPPINGS, {})
    return vol.Schema(
        {
            vol.Optional(
                metric.value, default=list(mappings.get(metric.value, []))
            ): EntitySelector(EntitySelectorConfig(domain="sensor", multiple=True))
            for metric in MetricType
        }
    )


class HealthAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
        return self.async_create_entry(title=NAME, data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HealthAssistantOptionsFlow()


class HealthAssistantOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=_options_schema(dict(self.config_entry.options)),
            )
        mappings = {
            metric: entity_ids
            for metric, entity_ids in user_input.items()
            if entity_ids
        }
        return self.async_create_entry(data={CONF_MAPPINGS: mappings})
