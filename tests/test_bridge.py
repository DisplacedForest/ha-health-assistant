from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from custom_components.health_assistant.store.bridge_models import (
    BridgeError,
    canonical,
    normalize_payload,
    parse_body,
    provider,
)
from custom_components.health_assistant.store.bridge_registry import (
    registry_count,
)
from custom_components.health_assistant.store.models import (
    HealthObservation,
    MetricType,
)
from custom_components.health_assistant.store.schema import MIGRATIONS, apply_migrations

NOW = datetime(2026, 9, 11, tzinfo=UTC)


def native_record(
    source_id,
    external_id="weight",
    revision=1,
    value=80,
    *,
    domain="scalar",
    record_type="weight",
    payload=None,
    delete=False,
):
    if not delete:
        payload = normalize_payload(
            domain,
            record_type,
            payload
            or {
                "value": value,
                "unit": "kg",
                "observed_at": "2026-09-10T00:00:00Z",
                "provenance": {},
            },
            NOW,
        )
    projection = {
        "hash_scope": "health_assistant.sparse_record",
        "hash_version": 1,
        "domain": domain,
        "identity": {
            "person_id": "primary",
            "provider": provider(source_id),
            "source_id": source_id,
            "external_id": external_id,
        },
        "record_type": record_type,
        "operation": "delete" if delete else "upsert",
        "payload": payload,
    }
    return {
        "external_id": external_id,
        "record_type": record_type,
        "source_revision": str(revision),
        "operation": projection["operation"],
        "hash_version": 1,
        "payload_hash": hashlib.sha256(canonical(projection)).hexdigest(),
        "payload": payload,
    }


def native_batch(
    source_id, records, *, domain="scalar", checkpoint=None, batch_id=None
):
    batch_id = batch_id or str(uuid4())
    projection = {
        "hash_scope": "health_assistant.sparse_batch",
        "hash_version": 1,
        "registration_id": source_id,
        "domain": domain,
        "batch_id": batch_id,
        "checkpoint": checkpoint,
        "records": [
            {
                key: value
                for key, value in record.items()
                if key not in ("hash_version", "payload")
            }
            for record in sorted(
                records, key=lambda record: record["external_id"].encode("utf-16-be")
            )
        ],
    }
    return {
        "version": 1,
        "domain": domain,
        "batch_id": batch_id,
        "hash_version": 1,
        "request_hash": hashlib.sha256(canonical(projection)).hexdigest(),
        "records": records,
        "checkpoint": checkpoint,
    }


def ingest(repository, source_id, records, **kwargs):
    return repository.apply_batch(
        source_id, native_batch(source_id, records, **kwargs), NOW, lambda: None
    )


def test_revision_ownership_correction_delete_and_replay(bridge):
    repository, source_id = bridge
    initial = native_batch(source_id, [native_record(source_id)])
    assert repository.apply_batch(source_id, initial, NOW, lambda: None)["changed"] == 1
    original = repository.database.execute("SELECT * FROM source_claims")[0]
    repository.health.set_observation_excluded(
        "primary", original["observation_id"], True
    )
    corrected = native_record(
        source_id,
        revision=2,
        payload={
            "value": 81,
            "unit": "kg",
            "observed_at": "2026-09-08T00:00:00Z",
            "provenance": {},
        },
    )
    assert ingest(repository, source_id, [corrected])["changed"] == 1
    projection = repository.database.execute("SELECT * FROM source_claims")[0]
    assert projection["id"] == original["id"]
    assert projection["status"] == "excluded"
    assert projection["observed_at"].startswith("2026-09-08")
    assert (
        ingest(repository, source_id, [native_record(source_id)])["counts"]["stale"]
        == 1
    )
    deletion = native_batch(
        source_id, [native_record(source_id, revision=3, delete=True)]
    )
    assert (
        repository.apply_batch(source_id, deletion, NOW, lambda: None)["changed"] == 1
    )
    assert repository.apply_batch(source_id, deletion, NOW, lambda: None) == {
        "replayed": True,
        "changed": 0,
        "counts": {"changed": 1, "unchanged": 0, "stale": 0},
    }
    assert not repository.database.execute("SELECT * FROM observations")
    assert not repository.database.execute("SELECT * FROM source_claims")
    assert (
        repository.database.execute("SELECT locally_excluded FROM bridge_records")[0][0]
        == 1
    )
    assert (
        ingest(repository, source_id, [native_record(source_id, revision=4)])["changed"]
        == 1
    )
    assert (
        repository.database.execute("SELECT status FROM source_claims")[0][0]
        == "excluded"
    )


def test_equal_revision_conflict_rolls_back_entire_batch(bridge):
    repository, source_id = bridge
    ingest(repository, source_id, [native_record(source_id)])
    with pytest.raises(BridgeError, match="revision_conflict"):
        ingest(
            repository,
            source_id,
            [native_record(source_id, "a-new"), native_record(source_id, value=90)],
        )
    assert repository.database.execute("SELECT COUNT(*) FROM bridge_records")[0][0] == 1


def test_current_authorization_rollback_before_commit(bridge):
    repository, source_id = bridge
    checks = 0

    def authorized():
        nonlocal checks
        checks += 1
        if checks == 2:
            raise BridgeError("registration_paused")

    with pytest.raises(BridgeError, match="registration_paused"):
        repository.apply_batch(
            source_id,
            native_batch(source_id, [native_record(source_id)]),
            NOW,
            authorized,
        )
    assert not repository.database.execute("SELECT * FROM bridge_records")
    assert not repository.database.execute("SELECT * FROM source_claims")
    assert not repository.database.execute("SELECT * FROM observations")
    assert (
        repository.registry.status(source_id)["domains"][1]["latest_batch_id"] is None
    )


def test_opaque_receipt_precedes_checkpoint_compare(bridge):
    repository, source_id = bridge
    repository.database.execute(
        "UPDATE bridge_receipts SET checkpoint_mode='opaque_cas' WHERE domain='scalar'"
    )
    batch = native_batch(
        source_id,
        [],
        checkpoint={"expected_checkpoint_id": None, "checkpoint_id": "one"},
    )
    assert repository.apply_batch(source_id, batch, NOW, lambda: None)["changed"] == 0
    assert repository.apply_batch(source_id, batch, NOW, lambda: None)["replayed"]
    with pytest.raises(BridgeError, match="checkpoint_conflict"):
        ingest(
            repository,
            source_id,
            [],
            checkpoint={"expected_checkpoint_id": None, "checkpoint_id": "two"},
        )


def test_reserved_namespace_cannot_enter_legacy_writer(bridge):
    repository, source_id = bridge
    observation = HealthObservation(
        person_id="primary",
        metric=MetricType.WEIGHT,
        value=80,
        unit="kg",
        observed_at=NOW,
        provider=provider(source_id),
        external_id="fixture",
        ingested_at=NOW,
    )
    with pytest.raises(BridgeError, match="reserved_provider"):
        repository.health.upsert_observation(observation)


def test_schema_collision_preserves_original(tmp_path):
    connection = sqlite3.connect(tmp_path / "legacy.sqlite")
    apply_migrations(connection, MIGRATIONS[:8], 8)
    connection.execute(
        "INSERT INTO provider_state VALUES(?,?,?)",
        (f"bridge:{uuid4()}", "{}", NOW.isoformat()),
    )
    connection.commit()
    with pytest.raises(Exception, match="namespace_collision"):
        apply_migrations(connection)
    assert connection.execute("SELECT version FROM schema_info").fetchone()[0] == 8
    assert not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='bridge_sources'"
    ).fetchone()
    connection.close()


@pytest.mark.parametrize(
    "body",
    [
        b'{"domain":"scalar","domain":"sleep"}',
        b'{"n":NaN}',
        b'{"n":"\\ud800"}',
        b"[" * 13 + b"]" * 13,
        b"\xff",
    ],
)
def test_invalid_wire_bounded(body):
    with pytest.raises(BridgeError):
        parse_body(body)


def test_registry_capacity_shared_and_import_read_only(bridge):
    repository, source_id = bridge
    source = repository.registry.get(source_id)
    descriptor = {
        key: source[key]
        for key in (
            "source_id",
            "person_id",
            "adapter_kind",
            "upstream_store",
            "upstream_scope",
            "created_at",
            "label",
        )
    }
    descriptor["source_id"] = str(uuid4())
    repository.registry.import_source(descriptor)
    assert registry_count(repository.database) == 2
    with pytest.raises(BridgeError, match="registration_paused"):
        repository.registry.require_live(descriptor["source_id"], "owner")
    repository.database.execute(
        "CREATE TABLE wearable_streams(stream_id TEXT,source_id TEXT)"
    )
    with repository.database.transaction():
        for _ in range(254):
            repository.database.execute(
                "INSERT INTO wearable_streams VALUES(?,?)", (str(uuid4()), source_id)
            )
    descriptor["source_id"] = str(uuid4())
    with pytest.raises(BridgeError, match="registry_capacity"):
        repository.registry.import_source(descriptor)
    assert registry_count(repository.database) == 256


def test_streaming_reconciliation_matches_reference(bridge):
    repository, _source_id = bridge
    for index in range(101):
        repository.health.upsert_observation(
            HealthObservation(
                person_id="primary",
                metric=MetricType.WEIGHT,
                value=80 + index % 3 / 10,
                unit="kg",
                observed_at=NOW - timedelta(minutes=index),
                provider=f"fixture-{index % 4}",
                external_id=str(index),
                ingested_at=NOW,
            )
        )
    repository.health.reconcile_metric("primary", MetricType.WEIGHT)
    before = [
        tuple(row)
        for row in repository.database.execute("SELECT * FROM observations ORDER BY id")
    ]
    repository.health.reconcile_metric("primary", MetricType.WEIGHT, streaming=True)
    assert [
        tuple(row)
        for row in repository.database.execute("SELECT * FROM observations ORDER BY id")
    ] == before


@pytest.mark.parametrize(
    "domain,record_type,payload,table",
    [
        (
            "workout",
            "workout",
            {
                "workout_type": "walk",
                "started_at": "2026-09-10T00:00:00Z",
                "ended_at": "2026-09-10T00:00:00Z",
                "provenance": {},
            },
            "workouts",
        ),
        (
            "sleep",
            "sleep_session",
            {
                "started_at": "2026-09-10T00:00:00Z",
                "ended_at": "2026-09-10T08:00:00Z",
                "provenance": {},
            },
            "sleep_sessions",
        ),
        (
            "recovery",
            "hrv_sdnn",
            {
                "value": 50,
                "unit": "ms",
                "started_at": "2026-09-10T00:00:00Z",
                "ended_at": "2026-09-10T00:00:00Z",
                "provenance": {},
            },
            "recovery_records",
        ),
    ],
)
def test_native_domain_delete_before_create_resurrection_and_replay(
    bridge, domain, record_type, payload, table
):
    repository, source_id = bridge
    deletion = native_record(
        source_id, domain=domain, record_type=record_type, delete=True
    )
    assert ingest(repository, source_id, [deletion], domain=domain)["changed"] == 1
    active = native_record(
        source_id, revision=2, domain=domain, record_type=record_type, payload=payload
    )
    assert ingest(repository, source_id, [active], domain=domain)["changed"] == 1
    assert (
        ingest(repository, source_id, [deletion], domain=domain)["counts"]["stale"] == 1
    )
    assert (
        ingest(repository, source_id, [active], domain=domain)["counts"]["unchanged"]
        == 1
    )
    assert repository.database.execute(f"SELECT count(*) FROM {table}")[0][0] == 1


@pytest.mark.parametrize("value", [True, "80", float("inf"), float("nan")])
def test_native_quantities_reject_non_binary64_numbers(value):
    with pytest.raises(BridgeError):
        normalize_payload(
            "scalar",
            "weight",
            {
                "value": value,
                "unit": "kg",
                "observed_at": "2026-09-10T00:00:00Z",
                "provenance": {},
            },
            NOW,
        )


def test_original_wire_limit_and_escaped_domain():
    body = b'{"\\u0064omain": "sl\\u0065ep", "padding":"' + b"x" * 1024 * 1024 + b'"}'
    assert parse_body(body)["domain"] == "sleep"
    with pytest.raises(BridgeError, match="size_limit"):
        parse_body(body.replace(b"sl\\u0065ep", b"scalar"))
    with pytest.raises(BridgeError):
        parse_body(b'{"invalid\\x":"value"}')


def test_equal_identity_type_conflict_even_when_stale_and_deleted(bridge):
    repository, source_id = bridge
    ingest(repository, source_id, [native_record(source_id, revision=5, delete=True)])
    wrong = native_record(source_id, record_type="lean_mass", delete=True)
    with pytest.raises(BridgeError, match="identity_conflict"):
        ingest(repository, source_id, [wrong])


def test_provenance_units_and_negative_values_preserve_legacy_domain():
    result = normalize_payload(
        "scalar",
        "weight",
        {
            "value": -1,
            "unit": "kg",
            "observed_at": "2026-09-10T00:00:00Z",
            "provenance": {"raw_value": -1000, "raw_unit": "g"},
        },
        NOW,
    )
    assert result["value"] == -1 and result["provenance"]["raw_value"] == -1000
    with pytest.raises(BridgeError, match="raw_quantity_mismatch"):
        normalize_payload(
            "scalar",
            "weight",
            {
                "value": 1,
                "unit": "kg",
                "observed_at": "2026-09-10T00:00:00Z",
                "provenance": {"raw_value": 2, "raw_unit": "lb"},
            },
            NOW,
        )
