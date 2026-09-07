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
DOMAINS = LEGACY_DOMAINS + ("sleep_sessions",)
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
COMPATIBILITY = MappingProxyType(
    {
        (1, 6): LEGACY_FIELDS,
        (2, 7): MappingProxyType({**LEGACY_FIELDS, "sleep_sessions": SLEEP_FIELDS}),
    }
)
