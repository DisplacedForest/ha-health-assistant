import pytest

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
