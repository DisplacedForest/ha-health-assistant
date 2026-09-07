from __future__ import annotations

import base64
import hashlib
import json

from .sleep import SleepRepository, session_from_row
from .sleep_models import (
    ASLEEP,
    STAGES,
    SleepError,
    canonical,
    elapsed_us,
    integer,
    stamp,
    text_value,
)


def quality(payload):
    elapsed = elapsed_us(payload["started_at"], payload["ended_at"])
    durations = dict.fromkeys(STAGES, 0)
    for interval in payload["stages"]:
        durations[interval["stage"]] += elapsed_us(interval["start"], interval["end"])
    coverage = sum(durations.values())
    known = sum(durations[key] for key in ASLEEP)
    complete = coverage == elapsed and durations["unknown"] == 0
    derived = {
        **{key: durations[key] for key in ASLEEP},
        "asleep": known,
        "awake": sum(durations[key] for key in ("awake", "awake_in_bed", "out_of_bed")),
        "in_bed": sum(
            elapsed_us(item["start"], item["end"])
            for item in payload["in_bed_intervals"]
        ),
    }
    disagreement = complete and any(
        value is not None and value != derived[key]
        for key, value in payload["reported_totals"].items()
        if key != "in_bed"
    )
    if (
        derived["in_bed"] == elapsed
        and payload["reported_totals"]["in_bed"] is not None
        and payload["reported_totals"]["in_bed"] != derived["in_bed"]
    ):
        disagreement = True
    context_disagreement = False
    context = payload["in_bed_intervals"]
    index = 0
    for interval in payload["stages"]:
        if interval["stage"] != "out_of_bed":
            continue
        while index < len(context) and context[index]["end"] <= interval["start"]:
            index += 1
        if index < len(context) and context[index]["start"] < interval["end"]:
            context_disagreement = True
            break
    reported = payload["reported_totals"]["asleep"]
    return {
        "elapsed_us": elapsed,
        "interval_totals": derived,
        "stage_coverage_us": coverage,
        "unknown_stage_us": durations["unknown"],
        "uncovered_us": elapsed - coverage,
        "complete_stage_coverage": complete,
        "summary_interval_disagreement": disagreement,
        "context_disagreement": context_disagreement,
        "asleep_duration_us": reported
        if reported is not None
        else known
        if complete
        else None,
        "value_basis": "reported"
        if reported is not None
        else "derived_complete"
        if complete
        else "missing",
    }


def summary(session):
    result = {
        "id": session.id,
        "person_id": session.person_id,
        "provider": session.provider,
        "source_id": session.source_id,
        "external_id": session.external_id,
        "source_revision": str(session.source_revision),
        "payload_hash": session.payload_hash,
        "hash_version": 1,
        "status": session.effective_status,
        "locally_excluded": session.locally_excluded,
    }
    if session.payload is not None:
        result.update(
            {
                key: session.payload[key]
                for key in (
                    "started_at",
                    "ended_at",
                    "start_offset_seconds",
                    "end_offset_seconds",
                    "start_zone",
                    "end_zone",
                    "reported_totals",
                )
            }
        )
        result.update(quality(session.payload))
    return result


def encode_cursor(value):
    return base64.urlsafe_b64encode(canonical(value)).decode().rstrip("=")


def decode_cursor(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise SleepError("invalid_cursor")
    try:
        data = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
        result = json.loads(data)
        if not isinstance(result, dict) or encode_cursor(result) != value:
            raise ValueError
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError) as err:
        raise SleepError("invalid_cursor") from err


class SleepQueries:
    def __init__(self, database):
        self.database = database

    def sessions(
        self,
        start,
        end,
        *,
        source=None,
        date_basis="overlap",
        excluded=False,
        limit=50,
        cursor=None,
    ):
        start, end = stamp(start), stamp(end)
        if (
            not 0 < elapsed_us(start, end) <= 366 * 86400 * 1_000_000
            or date_basis not in ("overlap", "ended_at")
            or type(excluded) is not bool
        ):
            raise SleepError()
        integer(limit, 1, 100)
        if source is not None:
            if not isinstance(source, (tuple, list)) or len(source) != 2:
                raise SleepError()
            source = [text_value(item) for item in source]
        fingerprint = hashlib.sha256(
            canonical(
                {
                    "start": start,
                    "end": end,
                    "source": source,
                    "date_basis": date_basis,
                    "excluded": excluded,
                }
            )
        ).hexdigest()
        with self.database.transaction():
            generation = str(SleepRepository(self.database).generation())
            conditions = [
                "person_id='primary'",
                "source_state='active'",
                "locally_excluded=?",
            ]
            args = [int(excluded)]
            if date_basis == "overlap":
                conditions += ["started_at<?", "ended_at>?"]
                args += [end, start]
            else:
                conditions += ["ended_at>=?", "ended_at<?"]
                args += [start, end]
            if source:
                conditions += ["provider=?", "source_id=?"]
                args += source
            if cursor is not None:
                page = decode_cursor(cursor)
                if (
                    set(page) != {"query", "generation", "end", "id"}
                    or page["query"] != fingerprint
                ):
                    raise SleepError("invalid_cursor")
                if page["generation"] != generation:
                    raise SleepError("stale_cursor")
                conditions.append("(ended_at,id)<(?,?)")
                args += [
                    stamp(page["end"]),
                    integer(page["id"], 1, 9223372036854775807),
                ]
            rows = self.database.execute(
                "SELECT * FROM sleep_sessions WHERE "
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
                "sessions": [summary(session_from_row(row)) for row in rows[:limit]],
                "generation": generation,
                "next_cursor": next_cursor,
            }

    def session(self, session_id, *, kind="stages", limit=128, cursor=None):
        integer(session_id, 1, 9223372036854775807)
        integer(limit, 1, 256)
        if kind not in ("stages", "in_bed_intervals"):
            raise SleepError()
        with self.database.transaction():
            rows = self.database.execute(
                "SELECT * FROM sleep_sessions WHERE person_id='primary' AND id=?",
                (session_id,),
            )
            if not rows:
                raise SleepError("not_found")
            session = session_from_row(rows[0])
            offset = 0
            if cursor is not None:
                page = decode_cursor(cursor)
                if (
                    set(page) != {"id", "revision", "hash", "kind", "offset"}
                    or page["id"] != session_id
                    or page["kind"] != kind
                ):
                    raise SleepError("invalid_cursor")
                if (
                    page["revision"] != str(session.source_revision)
                    or page["hash"] != session.payload_hash
                ):
                    raise SleepError("stale_cursor")
                offset = integer(page["offset"], 0, 4096)
            result = summary(session)
            if session.payload is None:
                return result
            intervals = session.payload[kind]
            if offset > len(intervals):
                raise SleepError("invalid_cursor")
            result.update(
                {
                    "provenance": session.payload["provenance"],
                    "interval_kind": kind,
                    "intervals": intervals[offset : offset + limit],
                    "interval_count": len(intervals),
                    "next_cursor": encode_cursor(
                        {
                            "id": session_id,
                            "revision": str(session.source_revision),
                            "hash": session.payload_hash,
                            "kind": kind,
                            "offset": offset + limit,
                        }
                    )
                    if offset + limit < len(intervals)
                    else None,
                }
            )
            return result
