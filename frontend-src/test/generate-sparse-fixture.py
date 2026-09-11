import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from custom_components.health_assistant.store import HealthDatabase
from custom_components.health_assistant.store.derived_queries import (
    DerivedQueries,
    encoded,
)
from custom_components.health_assistant.store.recovery import RecoveryRepository
from custom_components.health_assistant.store.recovery_models import (
    normalized_observation,
)
from custom_components.health_assistant.store.recovery_queries import RecoveryQueries
from custom_components.health_assistant.store.sleep import SleepRepository
from custom_components.health_assistant.store.sleep_models import normalized_session
from custom_components.health_assistant.store.sleep_queries import SleepQueries

now = datetime.now(UTC)
today = now.date()
with tempfile.TemporaryDirectory() as temp:
    db = HealthDatabase(Path(temp) / "fixture.sqlite")
    db.open()
    sleep = SleepRepository(db)
    recovery = RecoveryRepository(db)
    for offset in range(35):
        if offset in (4, 9, 17):
            continue
        end = datetime.combine(
            today - timedelta(days=offset), datetime.min.time(), UTC
        ) + timedelta(hours=8)
        start = end - timedelta(hours=8)
        if end > now:
            continue
        times = [
            start + timedelta(minutes=minute) for minute in (0, 30, 180, 270, 390, 480)
        ]
        stages = [
            {
                "start": a.isoformat(),
                "end": b.isoformat(),
                "stage": stage,
                "source_stage": stage,
            }
            for a, b, stage in zip(
                times, times[1:], ("awake_in_bed", "light", "deep", "rem", "light")
            )
        ]
        payload = {
            "started_at": start.isoformat(),
            "ended_at": end.isoformat(),
            "start_zone": "UTC",
            "end_zone": "UTC",
            "start_offset_seconds": 0,
            "end_offset_seconds": 0,
            "reported_totals": {"asleep": (6 * 3600 + (offset % 4) * 900) * 1000000},
            "stages": stages,
            "in_bed_intervals": [
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "source_label": "in bed",
                }
            ],
        }
        sleep.apply_sleep_changes(
            [normalized_session("fixture", "watch", f"night-{offset}", 1, payload, now)]
        )
        for metric, adjustment in (("hrv_sdnn", 0), ("hrv_rmssd", 10)):
            recovery.apply_recovery_changes(
                [
                    normalized_observation(
                        "fixture",
                        "watch",
                        f"{metric}-{offset}",
                        1,
                        {
                            "started_at": start.isoformat(),
                            "ended_at": end.isoformat(),
                            "value": 40 + offset % 5 + adjustment,
                            "unit": "ms",
                            "context": "sleep_summary",
                            "start_zone": "UTC",
                            "end_zone": "UTC",
                            "start_offset_seconds": 0,
                            "end_offset_seconds": 0,
                        },
                        now,
                        metric=metric,
                    )
                ]
            )
    queries = DerivedQueries(db, clock=lambda: now)
    catalogs = {domain: queries.sources(domain) for domain in ("sleep", "recovery")}
    series = {}
    for domain, catalog in catalogs.items():
        for descriptor in catalog["sources"]:
            key = descriptor["series_key"]
            descriptor["display_label"] = "Example watch" + (
                " / " + key["metric"].upper() + " / sleep summary"
                if domain == "recovery"
                else " / sleep"
            )
            series[encoded(key).decode()] = {
                str(days): queries.series(domain, key, today.isoformat(), days, "UTC")
                for days in (7, 28, 90)
            }
    sleep_records = {
        str(row["id"]): SleepQueries(db).session(row["id"])
        for row in db.execute("SELECT id FROM sleep_sessions")
    }
    for value in sleep_records.values():
        value["context_intervals"] = [
            {"start": value["started_at"], "end": value["ended_at"]}
        ]
    recovery_records = {
        str(row["id"]): RecoveryQueries(db).observation(row["id"])
        for row in db.execute("SELECT id FROM recovery_records")
    }
    result = {
        "generated_at": now.isoformat(),
        "end_date": today.isoformat(),
        "catalogs": catalogs,
        "series": series,
        "sleep_records": sleep_records,
        "recovery_records": recovery_records,
    }
    Path("frontend-src/test/fixtures/sparse.json").write_text(
        json.dumps(result, separators=(",", ":")) + "\n"
    )
    db.close()
