from datetime import UTC, datetime
from unittest.mock import patch

from custom_components.health_assistant.store.derived_queries import DerivedQueries
from custom_components.health_assistant.store.models import (
    HealthObservation,
    MetricType,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


async def test_derived_read_api_matches_repository_and_rejects_unknown_fields(
    hass, hass_ws_client, hass_read_only_access_token, config_entry
):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    database = config_entry.runtime_data.database
    repository = config_entry.runtime_data.repository
    value = HealthObservation(
        "primary",
        MetricType.WEIGHT,
        70,
        "kg",
        datetime(2026, 9, 6, 8, tzinfo=UTC),
        "fixture",
        "reading",
        NOW,
    )
    await hass.async_add_executor_job(repository.upsert_observation, value)
    query = {
        "domain": "scalar",
        "series_key": {"metric": "weight", "provider": "fixture"},
        "end_date": "2026-09-06",
        "days": 7,
        "timezone": "UTC",
    }
    expected = await hass.async_add_executor_job(
        lambda: DerivedQueries(database, clock=lambda: NOW).series(**query)
    )
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    with patch(
        "custom_components.health_assistant.derived_websocket.DerivedQueries",
        side_effect=lambda db, **kwargs: DerivedQueries(
            db, clock=lambda: NOW, **kwargs
        ),
    ):
        await client.send_json(
            {"id": 1, "type": "health_assistant/derived_series", **query}
        )
        result = await client.receive_json()
    assert result["success"] and result["result"] == expected
    assert result["result"]["points"][-1]["value"] == 70
    for index, extra in enumerate(
        (
            {"days": True},
            {"timezone": "not/valid"},
            {"series_key": {"provider": "fixture"}},
            {"unexpected": True},
            {"as_of": NOW.isoformat()},
        ),
        2,
    ):
        await client.send_json(
            {"id": index, "type": "health_assistant/derived_series", **query, **extra}
        )
        assert not (await client.receive_json())["success"]
    await client.send_json(
        {"id": 7, "type": "health_assistant/derived_sources", "domain": "scalar"}
    )
    catalog = await client.receive_json()
    assert catalog["success"] and catalog["result"]["sources"][0]["active_count"] == 1
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await client.send_json(
        {"id": 8, "type": "health_assistant/derived_series", **query}
    )
    assert (await client.receive_json())["error"]["code"] == "not_loaded"
