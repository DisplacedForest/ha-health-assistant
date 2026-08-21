from custom_components.health_assistant.const import DOMAIN
from custom_components.health_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_returns_metadata_only(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["domain"] == DOMAIN
    assert diagnostics["version"] == "0.1.0"
    assert diagnostics["entry"]["options"] == {}
    assert set(diagnostics) == {"domain", "version", "entry"}
