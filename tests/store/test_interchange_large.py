import tracemalloc

from custom_components.health_assistant.store import HealthDatabase
from custom_components.health_assistant.store.environment import EnvironmentRepository
from custom_components.health_assistant.store.interchange import (
    export_archive,
    import_archive,
)


def test_two_year_history_streams_with_bounded_python_memory(
    database, tmp_path, record_property
):
    stream = EnvironmentRepository(database).register(
        {
            "mapping_id": "bedroom",
            "source_id": "sensor.bedroom",
            "entity_id": "sensor.bedroom",
            "metric": "temperature",
            "area_id": "bedroom",
            "area_name": "Bedroom",
        }
    )
    start = 1725580800000
    count = 0
    with database.transaction():
        for day in range(730):
            resolution = 3600 if day < 640 else 300
            for offset in range(0, 86400000, resolution * 1000):
                timestamp = start + day * 86400000 + offset
                width = resolution * 1000
                database.execute(
                    "INSERT INTO environment_buckets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        stream["id"],
                        timestamp,
                        resolution,
                        1,
                        20,
                        20,
                        20,
                        20 * width,
                        width,
                        timestamp,
                        timestamp,
                        timestamp + width,
                    ),
                )
                count += 1
    assert count == 41280
    archive = tmp_path / "history.tar.gz"
    target = HealthDatabase(tmp_path / "target.sqlite")
    target.open()
    try:
        tracemalloc.start()
        manifest = export_archive(database, archive)
        export_peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.reset_peak()
        result = import_archive(target, archive, dry_run=False)
        import_peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        assert manifest["files"]["environment_buckets.jsonl"]["records"] == count
        assert result["applied"]["environment_buckets"]["create"] == count
        assert target.execute("SELECT count(*) FROM environment_buckets")[0][0] == count
        assert export_peak < 16 * 1024 * 1024
        assert import_peak < 16 * 1024 * 1024
        record_property("export_peak_bytes", export_peak)
        record_property("import_peak_bytes", import_peak)
        record_property("archive_bytes", archive.stat().st_size)
    finally:
        tracemalloc.stop()
        target.close()
