from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
import tracemalloc
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from custom_components.health_assistant.store.bridge_models import DOMAINS, canonical
from custom_components.health_assistant.store.bridge_registry import BridgeRegistry
from custom_components.health_assistant.store.db import HealthDatabase
from custom_components.health_assistant.store.models import MetricType
from custom_components.health_assistant.store.repository import HealthRepository
from tests.test_bridge import NOW

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures/native_wire_vectors.json").read_text()
)["vectors"]


@pytest.mark.parametrize(
    "vector", VECTORS, ids=[value["input"]["name"] for value in VECTORS]
)
def test_frozen_cross_language_jcs_bytes(vector):
    expected = vector["verified"]
    encoded = expected["canonical_utf8"].encode()
    assert canonical(json.loads(encoded)) == encoded
    assert encoded.hex() == expected["hex"]
    assert hashlib.sha256(encoded).hexdigest() == expected["sha256"]
    if vector["input"]["normalize"] == "none":
        assert canonical(json.loads(vector["input"]["raw_json"])) == encoded


def test_registry_256_full_receipts_actual_page_budget(tmp_path):
    database = HealthDatabase(tmp_path / "registry.sqlite")
    database.open()
    registry = BridgeRegistry(database)
    try:
        fixed = database.execute(
            "SELECT sum(pgsize) FROM dbstat WHERE name IN ('bridge_sources','bridge_receipts')"
        )[0][0]
        metadata = {
            "adapter_kind": "a" * 64,
            "upstream_store": "health_connect",
            "upstream_scope": "s" * 256,
            "label": "n" * 128,
        }
        one = None
        with database.transaction():
            for index in range(256):
                source = registry.enroll(
                    metadata, "o" * 128, dict.fromkeys(DOMAINS, "opaque_cas"), NOW
                )
                for domain in DOMAINS:
                    database.execute(
                        "UPDATE bridge_receipts SET batch_id=?,request_hash=?,checkpoint_id=?,changed=100,unchanged=100,stale=100 WHERE source_id=? AND domain=?",
                        (
                            UUID(str(uuid4())).bytes,
                            b"h" * 32,
                            "x" * 128,
                            source["source_id"],
                            domain,
                        ),
                    )
                if index == 0:
                    one = database.execute(
                        "SELECT sum(pgsize) FROM dbstat WHERE name IN ('bridge_sources','bridge_receipts')"
                    )[0][0]
        allocated = database.execute(
            "SELECT sum(pgsize) FROM dbstat WHERE name IN ('bridge_sources','bridge_receipts')"
        )[0][0]
        assert allocated - fixed <= 256 * 4096
        database.checkpoint()
        backup = tmp_path / "backup.sqlite"
        database.backup(backup)
        print(
            json.dumps(
                {
                    "sources": 256,
                    "receipts": 1024,
                    "fixed_registry_pages_bytes": fixed,
                    "one_source_allocated_bytes": one,
                    "full_registry_allocated_bytes": allocated,
                    "marginal_bytes_per_source": (allocated - fixed) / 256,
                    "backup_bytes": backup.stat().st_size,
                }
            )
        )
    finally:
        database.close()


def test_reconciliation_100000_claims_streams_once_and_propagates_chain(
    tmp_path, monkeypatch
):
    database = HealthDatabase(tmp_path / "large.sqlite")
    database.open()
    repository = HealthRepository(database)
    try:
        with database.transaction():
            database.execute(
                """
                WITH RECURSIVE numbers(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM numbers WHERE n<100000)
                INSERT INTO source_claims(id,person_id,metric,value,unit,observed_at,provider,external_id,ingested_at,provenance,status)
                SELECT n,'primary','weight',80,'kg',strftime('%Y-%m-%dT%H:%M:%f',?+(n-100001)*60,'unixepoch')||'000+00:00',CASE n%2 WHEN 0 THEN 'scale-b' ELSE 'scale-a' END,CAST(n AS TEXT),'2026-09-11T00:00:00.000000+00:00','{}','active' FROM numbers
            """,
                (int(NOW.timestamp()),),
            )
        plan = [
            row[3]
            for row in database.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM source_claims INDEXED BY idx_claims_reconcile WHERE person_id=? AND metric=? ORDER BY observed_at,provider,external_id",
                ("primary", "weight"),
            )
        ]
        assert any("idx_claims_reconcile" in row for row in plan)
        assert not any("TEMP B-TREE" in row for row in plan)
        original_execute, original_iterate = database.execute, database.iterate
        streams, temporary_bytes = 0, 0

        def execute(sql, params=()):
            nonlocal temporary_bytes
            if sql == "DROP TABLE bridge_members":
                temporary_bytes = max(
                    temporary_bytes,
                    original_execute("PRAGMA temp.page_count")[0][0]
                    * original_execute("PRAGMA temp.page_size")[0][0],
                )
            return original_execute(sql, params)

        def iterate(sql, params=()):
            nonlocal streams
            if "INDEXED BY idx_claims_reconcile" in sql:
                streams += 1
            yield from original_iterate(sql, params)

        monkeypatch.setattr(database, "execute", execute)
        monkeypatch.setattr(database, "iterate", iterate)
        started = time.monotonic()
        tracemalloc.start()
        repository.reconcile_metric("primary", MetricType.WEIGHT, streaming=True)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        elapsed = time.monotonic() - started
        assert streams == 1
        assert peak < 8 * 1024 * 1024
        assert database.execute("SELECT count(*) FROM observations")[0][0] == 50000
        assert not database.execute("SELECT 1 FROM observations WHERE id%2=0 LIMIT 1")
        with database.transaction():
            database.execute("DELETE FROM source_claims WHERE id=1")
            repository.reconcile_metric("primary", MetricType.WEIGHT, streaming=True)
        assert streams == 2
        assert database.execute("SELECT count(*) FROM observations")[0][0] == 50000
        assert not database.execute("SELECT 1 FROM observations WHERE id%2=1 LIMIT 1")
        assert not database.execute(
            "SELECT 1 FROM source_claims c LEFT JOIN observations o ON o.id=c.observation_id WHERE o.id IS NULL LIMIT 1"
        )
        maximum_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        wal = Path(str(database.path) + "-wal")
        print(
            json.dumps(
                {
                    "claims": 100000,
                    "ordered_passes_per_reconciliation": 1,
                    "first_pass_seconds_with_tracemalloc": elapsed,
                    "python_peak_bytes": peak,
                    "process_peak_rss_bytes": maximum_rss
                    if sys.platform == "darwin"
                    else maximum_rss * 1024,
                    "temporary_sqlite_bytes": temporary_bytes,
                    "wal_bytes": wal.stat().st_size,
                    "query_plan": plan,
                }
            )
        )
    finally:
        database.close()
