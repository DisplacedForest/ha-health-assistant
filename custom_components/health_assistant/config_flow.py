from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_MAPPINGS,
    CONF_SOURCE_MAPPINGS,
    DOMAIN,
    NAME,
    PROVIDER_HA_ENTITY,
    PROVIDER_MANUAL,
)
from .paths import database_path
from .providers.manual import ManualProvider
from .sources import SOURCE_NAMES, SourceOffer, discover_sources
from .store import HealthDatabase, HealthRepository, MetricType, StoreError

KEEP_SOURCE = "keep_current"


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


class SourceFlow:
    _pending_options: dict[str, Any] | None = None
    _priorities: dict[MetricType, str] | None = None
    _selections: dict[MetricType, str] | None = None

    def _entry(self):
        return self.config_entry if isinstance(self, OptionsFlow) else None

    def _options(self) -> dict:
        if self._pending_options is None:
            entry = self._entry()
            self._pending_options = deepcopy(dict(entry.options)) if entry else {}
            self._changed_options: set[str] = set()
        return self._pending_options

    def _offers(self) -> list[SourceOffer]:
        offers = discover_sources(self.hass)
        entry = self._entry()
        providers = [ManualProvider()]
        if entry is not None and getattr(entry, "runtime_data", None) is not None:
            providers = list(entry.runtime_data.registry.providers.values())
        external = [
            provider
            for provider in providers
            if provider.key not in SOURCE_NAMES
            and provider.key not in (PROVIDER_HA_ENTITY, PROVIDER_MANUAL)
        ]
        if offers or external or self._options().get(CONF_SOURCE_MAPPINGS):
            for provider in providers:
                if (
                    provider.key not in SOURCE_NAMES
                    and provider.capabilities.can_import
                    and provider.capabilities.metrics
                ):
                    offers.append(
                        SourceOffer(
                            key=provider.key,
                            label=provider.display_name,
                            metrics=provider.capabilities.metrics,
                        )
                    )
        present = {offer.key for offer in offers}
        for key in self._options().get(CONF_SOURCE_MAPPINGS, {}):
            if key not in present:
                offers.append(
                    SourceOffer(
                        key=key,
                        label=SOURCE_NAMES.get(key, key),
                        warnings=[
                            "Configured integration is missing. Existing history is kept."
                        ],
                    )
                )
        return offers

    async def _repository_action(self, action):
        entry = self._entry()
        if entry is not None and getattr(entry, "runtime_data", None) is not None:
            return await self.hass.async_add_executor_job(
                action, entry.runtime_data.repository
            )

        def run():
            database = HealthDatabase(database_path(self.hass))
            try:
                database.open()
                return action(HealthRepository(database))
            finally:
                database.close()

        return await self.hass.async_add_executor_job(run)

    async def async_step_sources(self, user_input=None) -> ConfigFlowResult:
        offers = self._offers()
        errors = {}
        if user_input is not None:
            selected = {}
            selections = {}
            profiles = {}
            bindings = deepcopy(self._options().get(CONF_SOURCE_MAPPINGS, {}))
            by_choice = {offer.choice: offer for offer in offers}
            for metric in MetricType:
                choice = user_input.get(metric.value, KEEP_SOURCE)
                if choice == KEEP_SOURCE:
                    continue
                offer = by_choice.get(choice)
                if offer is None or metric not in offer.metrics:
                    errors[metric.value] = "source_unavailable"
                    continue
                if offer.config_entry_id is not None:
                    if (
                        offer.key in profiles
                        and profiles[offer.key] != offer.config_entry_id
                    ):
                        errors["base"] = "different_profiles"
                        continue
                    profiles[offer.key] = offer.config_entry_id
                    binding = bindings.get(offer.key)
                    if (
                        binding is None
                        or binding["config_entry_id"] != offer.config_entry_id
                    ):
                        if not user_input.get("confirm_person", False):
                            errors["base"] = "confirm_person"
                            continue
                        binding = {
                            "config_entry_id": offer.config_entry_id,
                            "entities": {},
                        }
                        bindings[offer.key] = binding
                    binding["entities"][metric.value] = offer.entities[metric]
                selected[metric] = offer.key
                selections[metric] = offer.choice
            if not errors:
                if bindings != self._options().get(CONF_SOURCE_MAPPINGS, {}):
                    self._options()[CONF_SOURCE_MAPPINGS] = bindings
                    self._changed_options.add(CONF_SOURCE_MAPPINGS)
                self._priorities = selected
                self._selections = selections
                if user_input.get("manual_mapping", False):
                    return await self.async_step_manual()
                return await self._finish()

        def read_priorities(repository):
            return {metric: repository.get_priority(metric) for metric in MetricType}

        try:
            priorities = await self._repository_action(read_priorities)
        except StoreError, OSError:
            return self.async_abort(reason="store_unavailable")
        offers = self._offers()
        fields = {}
        for metric in MetricType:
            choices = [{"value": KEEP_SOURCE, "label": "Keep current sources"}]
            available = [offer for offer in offers if metric in offer.metrics]
            choices.extend(
                {"value": offer.choice, "label": offer.label} for offer in available
            )
            current = priorities[metric][0] if priorities[metric] else None
            binding = self._options().get(CONF_SOURCE_MAPPINGS, {}).get(current, {})
            default = next(
                (
                    offer.choice
                    for offer in available
                    if offer.key == current
                    and (
                        offer.config_entry_id is None
                        or offer.config_entry_id == binding.get("config_entry_id")
                    )
                ),
                KEEP_SOURCE,
            )
            fields[vol.Optional(metric.value, default=default)] = SelectSelector(
                SelectSelectorConfig(options=choices, mode="dropdown")
            )
        fields[vol.Optional("confirm_person", default=False)] = BooleanSelector()
        fields[vol.Optional("manual_mapping", default=False)] = BooleanSelector()
        details = []
        registry = er.async_get(self.hass)
        for offer in offers:
            mapped = [
                f"{metric.value.replace('_', ' ')}: {registry.async_get(ref).entity_id}"
                for metric, ref in offer.entities.items()
            ]
            details.append(
                f"{offer.label}: " + "; ".join(mapped + offer.warnings or ["Available"])
            )
        return self.async_show_form(
            step_id="sources",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                "source_details": "\n\n".join(details)
                or "No supported sources detected. Use manual mapping."
            },
        )

    async def async_step_manual(self, user_input=None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="manual", data_schema=_options_schema(self._options())
            )
        self._options()[CONF_MAPPINGS] = {
            metric: entities for metric, entities in user_input.items() if entities
        }
        self._changed_options.add(CONF_MAPPINGS)
        return await self._finish()

    async def _finish(self) -> ConfigFlowResult:
        if self._selections:
            offers = {offer.choice: offer for offer in self._offers()}
            for metric, choice in self._selections.items():
                offer = offers.get(choice)
                if offer is None or metric not in offer.metrics:
                    return self.async_abort(reason="source_changed")
                if offer.config_entry_id is not None:
                    binding = (
                        self._options().get(CONF_SOURCE_MAPPINGS, {}).get(offer.key, {})
                    )
                    if binding.get(
                        "config_entry_id"
                    ) != offer.config_entry_id or binding.get("entities", {}).get(
                        metric.value
                    ) != offer.entities.get(metric):
                        return self.async_abort(reason="source_changed")
        if self._priorities:

            def save(repository):
                for metric, provider in self._priorities.items():
                    current = repository.get_priority(metric)
                    repository.set_priority(
                        metric, [provider] + [key for key in current if key != provider]
                    )

            try:
                await self._repository_action(save)
            except StoreError, OSError:
                return self.async_abort(reason="store_unavailable")
        if isinstance(self, OptionsFlow):
            options = deepcopy(dict(self.config_entry.options))
            options.update({key: self._options()[key] for key in self._changed_options})
            return self.async_create_entry(data=options)
        return self.async_create_entry(title=NAME, data={}, options=self._options())


class HealthAssistantConfigFlow(SourceFlow, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
        if self._offers():
            return await self.async_step_sources()
        return self.async_create_entry(title=NAME, data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HealthAssistantOptionsFlow()


class HealthAssistantOptionsFlow(SourceFlow, OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._offers() or self._options().get(CONF_SOURCE_MAPPINGS):
            return await self.async_step_sources(user_input)
        if user_input is None:
            return self.async_show_form(
                step_id="init", data_schema=_options_schema(self._options())
            )
        return await self.async_step_manual(user_input)
