from datetime import UTC, datetime

from homeassistant.config_entries import ConfigEntryState

from custom_components.health_assistant import database_path
from custom_components.health_assistant.store import HealthObservation, MetricType

OBSERVED = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)


async def test_setup_entry(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert database_path(hass).exists()


async def test_unload_entry(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert database_path(hass).exists()


async def test_reload_entry(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED


async def test_data_survives_reload(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    repository = config_entry.runtime_data.repository
    stored = await hass.async_add_executor_job(
        repository.upsert_observation,
        HealthObservation(
            person_id="primary",
            metric=MetricType.WEIGHT,
            value=82.5,
            unit="kg",
            observed_at=OBSERVED,
            provider="test_scale",
            external_id="reading-1",
            ingested_at=OBSERVED,
        ),
    )

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    repository = config_entry.runtime_data.repository
    rows = await hass.async_add_executor_job(
        repository.get_observations, "primary", MetricType.WEIGHT
    )
    assert rows == [stored]
