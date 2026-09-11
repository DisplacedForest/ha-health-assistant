from types import MappingProxyType

OBSERVATION_FIELDS = {
    "id",
    "person_id",
    "metric",
    "value",
    "unit",
    "observed_at",
    "provider",
    "external_id",
    "ingested_at",
    "provenance",
    "status",
}
FIELDS = {
    "observations": OBSERVATION_FIELDS | {"possible_duplicate"},
    "source_claims": OBSERVATION_FIELDS | {"observation_id"},
    "workouts": {
        "id",
        "person_id",
        "provider",
        "external_id",
        "workout_type",
        "title",
        "started_at",
        "ended_at",
        "energy_kcal",
        "distance_m",
        "ingested_at",
        "provenance",
        "status",
    },
    "metric_priorities": {"metric", "context", "rank", "provider"},
    "environment_streams": {
        "id",
        "public_id",
        "mapping_id",
        "source_id",
        "entity_id",
        "metric",
        "area_id",
        "area_name",
        "unit",
    },
    "environment_buckets": {
        "stream_id",
        "start_ms",
        "resolution_s",
        "sample_count",
        "sample_sum",
        "minimum",
        "maximum",
        "weighted_sum",
        "covered_ms",
        "first_report_ms",
        "last_report_ms",
        "updated_ms",
    },
    "environment_maintenance": {
        "id",
        "last_success_ms",
        "duration_ms",
        "rolled_up",
        "deleted",
        "failed",
    },
}


LEGACY_FIELDS = MappingProxyType(
    {key: frozenset(value) for key, value in FIELDS.items()}
)
LEGACY_DOMAINS = (
    "observations",
    "source_claims",
    "workouts",
    "metric_priorities",
    "environment_streams",
    "environment_buckets",
    "environment_maintenance",
)
DOMAINS = LEGACY_DOMAINS + (
    "sleep_sessions",
    "recovery_records",
    "bridge_sources",
    "bridge_records",
)
SLEEP_FIELDS = frozenset(
    (
        "person_id",
        "provider",
        "source_id",
        "external_id",
        "source_revision",
        "payload_hash",
        "hash_version",
        "record_type",
        "operation",
        "payload",
        "locally_excluded",
    )
)
RECOVERY_FIELDS = frozenset(SLEEP_FIELDS)
BRIDGE_SOURCE_FIELDS = frozenset(
    (
        "source_id",
        "person_id",
        "adapter_kind",
        "upstream_store",
        "upstream_scope",
        "created_at",
        "label",
    )
)
BRIDGE_RECORD_FIELDS = frozenset(
    (
        "source_id",
        "domain",
        "external_id",
        "record_type",
        "source_revision",
        "hash_version",
        "payload_hash",
        "source_state",
        "locally_excluded",
        "first_ingested_at",
        "last_ingested_at",
        "payload",
    )
)
COMPATIBILITY = MappingProxyType(
    {
        (1, 6): LEGACY_FIELDS,
        (2, 7): MappingProxyType({**LEGACY_FIELDS, "sleep_sessions": SLEEP_FIELDS}),
        (2, 8): MappingProxyType(
            {
                **LEGACY_FIELDS,
                "sleep_sessions": SLEEP_FIELDS,
                "recovery_records": RECOVERY_FIELDS,
            }
        ),
        (2, 9): MappingProxyType(
            {
                **LEGACY_FIELDS,
                "sleep_sessions": SLEEP_FIELDS,
                "recovery_records": RECOVERY_FIELDS,
                "bridge_sources": BRIDGE_SOURCE_FIELDS,
                "bridge_records": BRIDGE_RECORD_FIELDS,
            }
        ),
    }
)
