from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .derived_metrics import CALCULATION_VERSION, baseline, rolling
from .models import CANONICAL_UNITS, DAILY_ACTIVITY_METRICS, MetricType
from .recovery_queries import normalize_series
from .sleep import session_from_row
from .sleep_models import SleepError, text_value
from .sleep_queries import decode_cursor, encode_cursor, quality

DOMAINS = ("scalar", "sleep", "recovery")
RECOVERY_UNITS = {
    "resting_heart_rate": "bpm",
    "respiratory_rate": "breaths/min",
    "hrv_sdnn": "ms",
    "hrv_rmssd": "ms",
}


class DerivedError(ValueError):
    def __init__(self, code="invalid_derived"):
        super().__init__(code)
        self.code = code


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def domain_value(domain):
    if not isinstance(domain, str) or domain not in DOMAINS:
        raise DerivedError()
    return domain


def series_value(domain, series):
    domain_value(domain)
    if not isinstance(series, dict):
        raise DerivedError()
    try:
        if domain == "recovery":
            return normalize_series(series)
        fields = (
            {"metric", "provider"} if domain == "scalar" else {"provider", "source_id"}
        )
        if set(series) != fields:
            raise DerivedError()
        result = {key: text_value(value) for key, value in series.items()}
        if domain == "scalar":
            result["metric"] = MetricType(result["metric"]).value
        return result
    except (SleepError, ValueError) as err:
        raise DerivedError() from err


def stored(instant, domain):
    value = instant.astimezone(UTC).isoformat(timespec="microseconds")
    return value if domain == "scalar" else value.replace("+00:00", "Z")


def capture_key(domain, series):
    return (domain, series["provider"], series.get("source_id"), series.get("metric"))


def elapsed_microseconds(delta):
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def range_query(domain, series, start, end, as_of):
    table = {
        "scalar": "observations",
        "sleep": "sleep_sessions",
        "recovery": "recovery_records",
    }[domain]
    field = "observed_at" if domain == "scalar" else "ended_at"
    columns = (
        "id,value,unit,observed_at,external_id,ingested_at,possible_duplicate"
        if domain == "scalar"
        else "*"
    )
    conditions = ["person_id='primary'", f"{field}>=?", f"{field}<?", f"{field}<=?"]
    params = [stored(start, domain), stored(end, domain), stored(as_of, domain)]
    conditions += (
        ["status='active'"]
        if domain == "scalar"
        else ["source_state='active'", "locally_excluded=0"]
    )
    for key, value in sorted(series.items()):
        conditions.append(f"{key} IS ?")
        params.append(value)
    index = " INDEXED BY idx_recovery_source_query" if domain == "recovery" else ""
    return f"SELECT {columns} FROM {table}{index} WHERE " + " AND ".join(
        conditions
    ), params


def point_from_row(domain, row, zone, today, rule):
    ending = row["observed_at"] if domain == "scalar" else row["ended_at"]
    ended = datetime.fromisoformat(ending)
    day = ended.astimezone(zone).date()
    basis = "reported"
    if domain == "sleep":
        sleep = quality(session_from_row(row).payload)
        value = sleep["asleep_duration_us"]
        value = value / 1_000_000 if value is not None else None
        unit, basis = "s", sleep["value_basis"]
    else:
        value, unit = row["value"], row["unit"]
    result = {
        "date": day.isoformat(),
        "value": value,
        "unit": unit,
        "selection_rule": rule,
        "value_basis": basis,
        "selected_record_id": row["id"],
        "source_revision": None if domain == "scalar" else str(row["source_revision"]),
        "alternative_count": 0,
        "complete_day": day < today,
        "null_reason": "incomplete_sleep" if value is None else None,
    }
    if domain == "scalar":
        result.update(
            scalar_ingested_at=row["ingested_at"],
            possible_duplicate=bool(row["possible_duplicate"]),
            observed_at=ending,
        )
    else:
        result.update(started_at=row["started_at"], ended_at=ending)
    primary = (
        -elapsed_microseconds(ended - datetime.fromisoformat(row["started_at"]))
        if domain == "sleep"
        else -value
        if rule == "daily_peak"
        else 0
    )
    order = (
        primary,
        -elapsed_microseconds(ended - datetime(1970, 1, 1, tzinfo=UTC)),
        row["external_id"].encode("utf-8"),
        row["id"],
    )
    return day, result, order


class DerivedQueries:
    def __init__(self, database, *, clock=None, capture_states=None):
        self.database = database
        self.clock = clock or (lambda: datetime.now(UTC))
        self.capture_states = capture_states or {}

    def series(self, domain, series_key, end_date, days, timezone):
        series = series_value(domain, series_key)
        if type(days) is not int or days not in (7, 28, 90):
            raise DerivedError()
        try:
            if not isinstance(timezone, str) or not isinstance(end_date, str):
                raise TypeError
            zone, end = ZoneInfo(timezone), date.fromisoformat(end_date)
            if end.isoformat() != end_date:
                raise ValueError
            as_of = self.clock().astimezone(UTC)
            today = as_of.astimezone(zone).date()
            if end > today:
                raise ValueError
            display_start = end - timedelta(days=days - 1)
            rolling_end = end if end == today else end + timedelta(days=1)
            start = min(
                display_start - timedelta(days=28), rolling_end - timedelta(days=90)
            )
            until = datetime.combine(end + timedelta(days=1), time.min, zone)
            since = datetime.combine(start, time.min, zone)
        except (ValueError, TypeError, OverflowError, ZoneInfoNotFoundError) as err:
            raise DerivedError() from err
        rule = (
            "longest_session"
            if domain == "sleep"
            else "daily_peak"
            if domain == "scalar" and series["metric"] in DAILY_ACTIVITY_METRICS
            else "latest_observation"
        )
        unit = (
            "s"
            if domain == "sleep"
            else CANONICAL_UNITS[MetricType(series["metric"])]
            if domain == "scalar"
            else RECOVERY_UNITS[series["metric"]]
        )
        points, orders = {}, {}
        with self.database.transaction():
            for row in self.database.iterate(
                *range_query(domain, series, since, until, as_of)
            ):
                day, point, order = point_from_row(domain, row, zone, today, rule)
                previous = points.get(day)
                alternatives = previous["alternative_count"] + 1 if previous else 0
                if previous is None or order < orders[day]:
                    points[day], orders[day] = point, order
                points[day]["alternative_count"] = alternatives
            display = []
            for offset in range(days):
                day = display_start + timedelta(days=offset)
                display.append(
                    points.get(
                        day,
                        {
                            "date": day.isoformat(),
                            "value": None,
                            "unit": unit,
                            "selection_rule": rule,
                            "value_basis": "missing",
                            "selected_record_id": None,
                            "source_revision": None,
                            "alternative_count": 0,
                            "complete_day": day < today,
                            "null_reason": "no_observation",
                            **(
                                {
                                    "scalar_ingested_at": None,
                                    "possible_duplicate": False,
                                }
                                if domain == "scalar"
                                else {}
                            ),
                        },
                    )
                )
            token = hashlib.sha256(
                encoded(
                    {
                        "version": CALCULATION_VERSION,
                        "domain": domain,
                        "series": series,
                        "timezone": timezone,
                        "start": start.isoformat(),
                        "end": end_date,
                        "points": [point for _, point in sorted(points.items())],
                    }
                )
            ).hexdigest()
            return {
                "calculation_version": CALCULATION_VERSION,
                "timezone": timezone,
                "as_of": stored(as_of, "recovery"),
                "snapshot_token": token,
                "selected_series": series,
                "points": display,
                "rolling": {
                    str(window): rolling(points, rolling_end, window)
                    for window in (7, 28, 90)
                },
                "baseline": baseline(points, end),
            }

    def sources(self, domain, *, limit=50, cursor=None):
        domain_value(domain)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DerivedError()
        page = None
        if cursor is not None:
            try:
                page = decode_cursor(cursor)
            except SleepError as err:
                raise DerivedError("invalid_cursor") from err
            if (
                set(page) != {"domain", "catalog", "offset"}
                or page["domain"] != domain
                or type(page["offset"]) is not int
                or page["offset"] < 0
            ):
                raise DerivedError("invalid_cursor")
        offset = page["offset"] if page else 0
        fields = (
            ["metric", "provider"]
            if domain == "scalar"
            else ["provider", "source_id"]
            if domain == "sleep"
            else [
                "provider",
                "source_id",
                "metric",
                "context",
                "algorithm_id",
                "algorithm_version",
            ]
        )
        table = {
            "scalar": "observations",
            "sleep": "sleep_sessions",
            "recovery": "recovery_records",
        }[domain]
        active = "status='active'" if domain == "scalar" else "locally_excluded=0"
        excluded = "status='excluded'" if domain == "scalar" else "locally_excluded=1"
        condition = "person_id='primary'" + (
            "" if domain == "scalar" else " AND source_state='active'"
        )
        columns = ",".join(fields)
        sql = f"SELECT {columns},sum({active}) AS active_count,sum({excluded}) AS excluded_count FROM {table} WHERE {condition} GROUP BY {columns} ORDER BY {columns}"
        digest, selected, count = hashlib.sha256(), [], 0
        with self.database.transaction():
            for row in self.database.iterate(sql):
                series = {key: row[key] for key in fields}
                identity = encoded(series).decode()
                descriptor = {
                    "series_key": series,
                    "display_label": " / ".join(
                        str(series[key]) for key in fields if series[key] is not None
                    ),
                    "scope": "canonical_winning_provider"
                    if domain == "scalar"
                    else "source_account",
                    "capture_state": self.capture_states.get(
                        identity,
                        self.capture_states.get(capture_key(domain, series), "unknown"),
                    ),
                    "retained_history_available": True,
                    "active_count": row["active_count"],
                    "excluded_count": row["excluded_count"],
                }
                digest.update(encoded(descriptor) + b"\n")
                if offset <= count < offset + limit:
                    selected.append(descriptor)
                count += 1
            catalog = digest.hexdigest()
            if page and page["catalog"] != catalog:
                raise DerivedError("stale_cursor")
            if offset > count:
                raise DerivedError("invalid_cursor")
            return {
                "sources": selected,
                "catalog_token": catalog,
                "next_cursor": encode_cursor(
                    {"domain": domain, "catalog": catalog, "offset": offset + limit}
                )
                if offset + limit < count
                else None,
            }
