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
