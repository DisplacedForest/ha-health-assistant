import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.health_assistant.const import DOMAIN, NAME


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
async def isolated_config_dir(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)


@pytest.fixture
def config_entry():
    return MockConfigEntry(domain=DOMAIN, title=NAME, data={}, unique_id=DOMAIN)


@pytest.fixture
def bridge(tmp_path):
    from datetime import UTC, datetime

    from custom_components.health_assistant.store.bridge import BridgeRepository
    from custom_components.health_assistant.store.bridge_models import DOMAINS
    from custom_components.health_assistant.store.bridge_registry import BridgeRegistry
    from custom_components.health_assistant.store.db import HealthDatabase

    database = HealthDatabase(tmp_path / "bridge.sqlite")
    database.open()
    source = BridgeRegistry(database).enroll(
        {
            "adapter_kind": "synthetic",
            "upstream_store": "apple_health",
            "upstream_scope": "fixture",
            "label": "Fixture",
        },
        "owner",
        dict.fromkeys(DOMAINS, "none"),
        datetime(2026, 9, 11, tzinfo=UTC),
    )
    yield BridgeRepository(database), source["source_id"]
    database.close()
