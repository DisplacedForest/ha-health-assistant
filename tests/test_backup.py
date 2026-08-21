import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from custom_components.health_assistant import backup_directory, database_path
from custom_components.health_assistant.backup import (
    async_post_backup,
    async_pre_backup,
)
from custom_components.health_assistant.const import DOMAIN
from custom_components.health_assistant.store import HealthObservation, MetricType

OBSERVED = datetime(2026, 8, 20, 7, 30, tzinfo=UTC)


def _observation(external_id: str, value: float) -> HealthObservation:
    return HealthObservation(
        person_id="primary",
        metric=MetricType.WEIGHT,
        value=value,
        unit="kg",
        observed_at=OBSERVED,
        provider="test_scale",
        external_id=external_id,
        ingested_at=OBSERVED,
    )


async def _setup(hass, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_create_backup_service(hass, config_entry):
    await _setup(hass, config_entry)
    repository = config_entry.runtime_data.repository
    await hass.async_add_executor_job(
        repository.upsert_observation, _observation("reading-1", 82.5)
    )

    response = await hass.services.async_call(
        DOMAIN, "create_backup", blocking=True, return_response=True
    )

    path = Path(response["path"])
    assert path.parent == backup_directory(hass)
    assert path.exists()
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT value FROM observations").fetchall()
    finally:
        conn.close()
    assert rows == [(82.5,)]


async def test_backup_restore_round_trip(hass, config_entry):
    await _setup(hass, config_entry)
    repository = config_entry.runtime_data.repository
    await hass.async_add_executor_job(
        repository.upsert_observation, _observation("reading-1", 82.5)
    )

    response = await hass.services.async_call(
        DOMAIN, "create_backup", blocking=True, return_response=True
    )
    backup_path = Path(response["path"])

    await hass.async_add_executor_job(
        repository.upsert_observation, _observation("reading-2", 83.1)
    )

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(shutil.copyfile, backup_path, database_path(hass))
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    repository = config_entry.runtime_data.repository
    rows = await hass.async_add_executor_job(
        repository.get_observations, "primary", MetricType.WEIGHT
    )
    assert [row.external_id for row in rows] == ["reading-1"]


async def test_native_backup_hooks(hass, config_entry):
    await _setup(hass, config_entry)
    await async_pre_backup(hass)
    await async_post_backup(hass)
