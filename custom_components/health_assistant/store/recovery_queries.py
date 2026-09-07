from __future__ import annotations

import hashlib

from .recovery import RecoveryRepository, observation_from_row
from .recovery_models import (
    CONTEXTS,
    RecoveryError,
    canonical,
    checked,
    integer,
    metric_value,
    sparse,
    stamp,
    text_value,
)
from .sleep_queries import decode_cursor, encode_cursor

SERIES_FIELDS = (
    "provider",
    "source_id",
    "metric",
    "context",
    "algorithm_id",
    "algorithm_version",
)


def normalize_series(series):
    checked(sparse.fields, series, SERIES_FIELDS, SERIES_FIELDS)
    result = {key: text_value(series[key]) for key in ("provider", "source_id")}
    result["metric"] = metric_value(series["metric"])
    context = series["context"]
    if not isinstance(context, str) or context not in CONTEXTS:
        raise RecoveryError()
    result["context"] = context
    for key in ("algorithm_id", "algorithm_version"):
        result[key] = text_value(series[key], 128, nullable=True)
    return result


def summary(observation):
    result = {
        "id": observation.id,
        "person_id": observation.person_id,
        "provider": observation.provider,
        "source_id": observation.source_id,
        "source_label": observation.provider,
        "external_id": observation.external_id,
        "metric": observation.metric,
        "source_revision": str(observation.source_revision),
        "payload_hash": observation.payload_hash,
        "hash_version": 1,
        "status": observation.effective_status,
        "locally_excluded": observation.locally_excluded,
    }
    if observation.payload is not None:
        result.update(
            {
                key: value
                for key, value in observation.payload.items()
                if key != "provenance"
            }
        )
    return result


class RecoveryQueries:
    def __init__(self, database):
        self.database = database

    def observations(
        self, start, end, *, series, excluded=False, limit=50, cursor=None
    ):
        start, end = stamp(start), stamp(end)
        if (
            not 0 < checked(sparse.elapsed_us, start, end) <= 366 * 86400 * 1_000_000
            or type(excluded) is not bool
        ):
            raise RecoveryError()
        integer(limit, 1, 100)
        series = normalize_series(series)
        fingerprint = hashlib.sha256(
            canonical(
                {"start": start, "end": end, "series": series, "excluded": excluded}
            )
        ).hexdigest()
        with self.database.transaction():
            generation = str(RecoveryRepository(self.database).generation())
            conditions = [
                "person_id='primary'",
                "source_state='active'",
                "locally_excluded=?",
                "ended_at>=?",
                "ended_at<?",
            ]
            args = [int(excluded), start, end]
            for key in SERIES_FIELDS:
                conditions.append(f"{key} IS ?")
                args.append(series[key])
            if cursor is not None:
                page = checked(decode_cursor, cursor)
                if (
                    set(page) != {"query", "generation", "end", "id"}
                    or page["query"] != fingerprint
                ):
                    raise RecoveryError("invalid_cursor")
                if page["generation"] != generation:
                    raise RecoveryError("stale_cursor")
                conditions.append("(ended_at,id)<(?,?)")
                args += [
                    stamp(page["end"]),
                    integer(page["id"], 1, 9223372036854775807),
                ]
            rows = self.database.execute(
                "SELECT * FROM recovery_records WHERE "
                + " AND ".join(conditions)
                + " ORDER BY ended_at DESC,id DESC LIMIT ?",
                (*args, limit + 1),
            )
            next_cursor = (
                encode_cursor(
                    {
                        "query": fingerprint,
                        "generation": generation,
                        "end": rows[limit - 1]["ended_at"],
                        "id": rows[limit - 1]["id"],
                    }
                )
                if len(rows) > limit
                else None
            )
            return {
                "observations": [
                    summary(observation_from_row(row)) for row in rows[:limit]
                ],
                "generation": generation,
                "next_cursor": next_cursor,
            }

    def observation(self, record_id):
        integer(record_id, 1, 9223372036854775807)
        rows = self.database.execute(
            "SELECT * FROM recovery_records WHERE person_id='primary' AND id=?",
            (record_id,),
        )
        if not rows:
            raise RecoveryError("not_found")
        observation = observation_from_row(rows[0])
        result = summary(observation)
        if observation.payload is not None:
            result["provenance"] = observation.payload["provenance"]
        return result
