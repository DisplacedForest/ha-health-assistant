from datetime import timedelta

import pytest

from custom_components.health_assistant.providers import ProviderRegistry
from custom_components.health_assistant.store import HealthDatabase, HealthRepository


@pytest.fixture
def database(tmp_path):
    db = HealthDatabase(tmp_path / "health.sqlite")
    db.open()
    yield db
    db.close()


@pytest.fixture
def repository(database):
    return HealthRepository(database)


@pytest.fixture
def registry(hass, repository):
    return ProviderRegistry(hass, repository, sync_timeout=0.5)


@pytest.fixture
def short_interval():
    return timedelta(seconds=30)
