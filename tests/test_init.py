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


async def test_corrupt_database_fails_setup_and_preserves_file(hass, config_entry):
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import issue_registry as ir

    path = database_path(hass)
    path.parent.mkdir(parents=True, exist_ok=True)
    garbage = b"this is not a sqlite database " * 64
    path.write_bytes(garbage)

    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert path.read_bytes() == garbage
    registry = ir.async_get(hass)
    assert registry.async_get_issue("health_assistant", "database_corrupt") is not None


async def test_future_schema_database_fails_setup_and_preserves_data(
    hass, config_entry
):
    import sqlite3

    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import issue_registry as ir

    path = database_path(hass)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_info (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_info (version) VALUES (99)")
    conn.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, value REAL)")
    conn.execute("INSERT INTO observations (value) VALUES (82.5)")
    conn.commit()
    conn.close()

    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT version FROM schema_info").fetchone() == (99,)
        assert conn.execute("SELECT value FROM observations").fetchone() == (82.5,)
    finally:
        conn.close()
    registry = ir.async_get(hass)
    assert (
        registry.async_get_issue("health_assistant", "database_unsupported_version")
        is not None
    )
