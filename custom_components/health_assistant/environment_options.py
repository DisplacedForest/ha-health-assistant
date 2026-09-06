from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import voluptuous as vol
from homeassistant.helpers.selector import (
    AreaSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .environment import CONF_ENVIRONMENT, resolve_mapping
from .store import StoreValidationError
from .store.environment import ENVIRONMENT_UNITS, MAX_MAPPINGS, EnvironmentRepository


class EnvironmentalOptions:
    async def async_step_environment(self, user_input=None):
        mappings = deepcopy(self.config_entry.options.get(CONF_ENVIRONMENT, []))
        errors = {}
        if user_input is not None:
            action = user_input.get("action", "save")
            selected = user_input.get("mapping", "")
            try:
                if action == "remove":
                    if not any(m["mapping_id"] == selected for m in mappings):
                        raise StoreValidationError("Choose a mapping")
                    mappings = [m for m in mappings if m["mapping_id"] != selected]
                elif action == "add":
                    if len(mappings) >= MAX_MAPPINGS:
                        raise StoreValidationError(
                            "Environmental mapping limit reached"
                        )
                    mapping = {
                        "mapping_id": str(uuid4()),
                        "entity_id": user_input.get("entity_id", ""),
                        "metric": user_input.get("metric", ""),
                        "area_id": user_input.get("area_id"),
                        "area_override": bool(user_input.get("area_id")),
                    }
                    mapping = resolve_mapping(self.hass, mapping, validate=True)
                    if any(
                        m.get("source_id") == mapping["source_id"]
                        and m.get("metric") == mapping["metric"]
                        for m in mappings
                    ):
                        raise StoreValidationError("Duplicate environmental mapping")
                    mappings.append(mapping)
                elif action != "save":
                    raise StoreValidationError("Invalid environmental action")
                runtime = self.config_entry.runtime_data
                repository = EnvironmentRepository(runtime.database)
                resolved = []
                for m in mappings:
                    try:
                        resolved.append(resolve_mapping(self.hass, m))
                    except StoreValidationError:
                        continue
                await self.hass.async_add_executor_job(
                    repository.register_all, resolved
                )
                self._options()[CONF_ENVIRONMENT] = mappings
                self._changed_options.add(CONF_ENVIRONMENT)
                self._environment_requested = False
                return await self._finish()
            except StoreValidationError, KeyError, TypeError:
                errors["base"] = "environment_invalid"
        choices = [
            {
                "value": m["mapping_id"],
                "label": f"{m.get('entity_id', '')}: {m.get('metric', '')} ({m.get('area_name', '')})",
            }
            for m in mappings
        ]
        fields = {
            vol.Required("action", default="save"): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "save", "label": "Keep current mappings"},
                        {"value": "add", "label": "Add a sensor"},
                        {"value": "remove", "label": "Stop capturing a sensor"},
                    ],
                    mode="dropdown",
                )
            ),
            vol.Optional("entity_id"): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional("metric"): SelectSelector(
                SelectSelectorConfig(options=list(ENVIRONMENT_UNITS), mode="dropdown")
            ),
            vol.Optional("area_id"): AreaSelector(),
        }
        if choices:
            fields[vol.Optional("mapping")] = SelectSelector(
                SelectSelectorConfig(options=choices, mode="dropdown")
            )
        return self.async_show_form(
            step_id="environment",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={"mapping_count": str(len(mappings))},
        )
