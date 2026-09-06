from __future__ import annotations

import json
import math
import unicodedata
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from .store import DEFAULT_PERSON_ID

MAX_WORKOUTS = 100
MAX_DETAIL_BYTES = 262144
MAX_EXERCISES = 100
MAX_SETS = 100
MAX_TOTAL_SETS = 1000
WINDOW_DAYS = 7
SET_FIELDS = ("weight_kg", "reps", "duration_seconds", "distance_m")


def normalize_exercise(name):
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


@lru_cache(maxsize=1)
def exercise_map():
    data = json.loads(Path(__file__).with_name("exercise_map.json").read_text())
    aliases = {
        normalize_exercise(alias): tuple(exercise["regions"])
        for exercise in data["exercises"]
        for alias in exercise["aliases"]
    }
    return data["regions"], aliases


def _valid_text(value):
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def _text(value, limit):
    return value[:limit] if _valid_text(value) else ""


def _set(raw):
    if not isinstance(raw, dict):
        return None
    kind = raw.get("type", "normal")
    if not _valid_text(kind) or not kind.strip() or len(kind) > 32:
        return None
    result = {"type": kind}
    for key in SET_FIELDS:
        value = raw.get(key)
        if value is None:
            continue
        if (
            type(value) not in (int, float)
            or not 0 <= value <= 1e12
            or not math.isfinite(value)
        ):
            return None
        if key == "reps" and value != int(value):
            return None
        result[key] = value
    if not any(
        result.get(key, 0) > 0 for key in ("reps", "duration_seconds", "distance_m")
    ):
        return None
    result["warmup"] = normalize_exercise(kind) in {"warmup", "warm-up", "warm up"}
    return result


def _exercises(raw):
    if raw is None:
        return [], True
    try:
        provenance = json.loads(raw)
    except ValueError, RecursionError:
        return [], True
    if not isinstance(provenance, dict):
        return [], True
    source = provenance.get("exercises", [])
    if not isinstance(source, list):
        return [], True
    _, aliases = exercise_map()
    incomplete = len(source) > MAX_EXERCISES
    exercises = []
    total_sets = 0
    for item in source[:MAX_EXERCISES]:
        if not isinstance(item, dict) or not _valid_text(item.get("name")):
            incomplete = True
            continue
        name = item["name"]
        if item.get("notes") is not None and not _valid_text(item["notes"]):
            incomplete = True
        incomplete |= len(name) > 200 or len(_text(item.get("notes"), 1001)) > 1000
        rows = item.get("sets", [])
        if not name.strip() or not isinstance(rows, list):
            incomplete = True
            continue
        available = min(MAX_SETS, MAX_TOTAL_SETS - total_sets)
        incomplete |= len(rows) > available
        sets = []
        for row in rows[:available]:
            total_sets += 1
            cleaned = _set(row)
            if cleaned is None:
                incomplete = True
            else:
                sets.append(cleaned)
        exercises.append(
            {
                "name": name[:200],
                "notes": _text(item.get("notes"), 1000),
                "regions": aliases.get(normalize_exercise(name), ()),
                "sets": sets,
                "recorded_sets": sum(not row["warmup"] for row in sets),
            }
        )
    return exercises, incomplete


def _summary(row):
    return {
        "id": row["id"],
        "title": _text(row["title"] or row["workout_type"], 240),
        "workout_type": _text(row["workout_type"], 120),
        "provider": _text(row["provider"], 120),
        "source": _text(row["external_id"], 240),
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "duration_seconds": (
            datetime.fromisoformat(row["ended_at"])
            - datetime.fromisoformat(row["started_at"])
        ).total_seconds(),
    }


def _rows(database, where, params, limit):
    return database.execute(
        f"""
        SELECT id, substr(title, 1, 240) AS title,
            substr(workout_type, 1, 120) AS workout_type,
            substr(provider, 1, 120) AS provider,
            substr(external_id, 1, 240) AS external_id,
            started_at, ended_at,
            CASE WHEN length(CAST(provenance AS BLOB)) <= ?
                THEN provenance ELSE NULL END AS detail,
            COUNT(*) OVER () AS total
        FROM workouts
        WHERE person_id = ? AND status = 'active' AND {where}
        ORDER BY ended_at DESC, id DESC LIMIT ?
        """,
        (MAX_DETAIL_BYTES, DEFAULT_PERSON_ID, *params, limit),
    )


def workout_detail(database, workout_id):
    rows = _rows(database, "id = ?", (workout_id,), 1)
    if not rows:
        return None
    row = rows[0]
    exercises, incomplete = _exercises(row["detail"])
    return {**_summary(row), "exercises": exercises, "incomplete": incomplete}


def build_body(database, now=None):
    now = (now or datetime.now(UTC)).astimezone(UTC)
    start = now - timedelta(days=WINDOW_DAYS)
    labels, _ = exercise_map()
    regions = {
        key: {
            "key": key,
            "label": label,
            "score": 0,
            "recorded_sets": 0,
            "workout_ids": [],
        }
        for key, label in labels.items()
    }
    workouts = []
    unmapped = {}
    unknown_count = 0
    without_sets = 0
    incomplete_count = 0
    rows = _rows(
        database,
        "ended_at > ? AND ended_at <= ?",
        (
            start.isoformat(timespec="microseconds"),
            now.isoformat(timespec="microseconds"),
        ),
        MAX_WORKOUTS,
    )
    for row in rows:
        exercises, incomplete = _exercises(row["detail"])
        age = (now - datetime.fromisoformat(row["ended_at"])).total_seconds()
        weight = max(0, 1 - age / timedelta(days=WINDOW_DAYS).total_seconds())
        workout_regions = set()
        recorded_sets = 0
        for exercise in exercises:
            count = exercise["recorded_sets"]
            recorded_sets += count
            if not exercise["regions"]:
                unknown_count += 1
                name = exercise["name"]
                if name in unmapped or len(unmapped) < 20:
                    unmapped[name] = unmapped.get(name, 0) + 1
            for key in exercise["regions"]:
                if not count:
                    continue
                regions[key]["score"] += count * weight
                regions[key]["recorded_sets"] += count
                workout_regions.add(key)
        for key in workout_regions:
            regions[key]["workout_ids"].append(row["id"])
        without_sets += not recorded_sets
        incomplete_count += incomplete
        workouts.append(
            {
                **_summary(row),
                "recorded_sets": recorded_sets,
                "regions": sorted(workout_regions),
                "incomplete": incomplete,
            }
        )
    highest = max((region["score"] for region in regions.values()), default=0)
    for region in regions.values():
        region["heat"] = region["score"] / highest if highest else 0
    total = rows[0]["total"] if rows else 0
    return {
        "generated_at": now.isoformat(),
        "window_days": WINDOW_DAYS,
        "regions": list(regions.values()),
        "workouts": workouts,
        "workout_count": total,
        "workouts_without_sets": without_sets,
        "incomplete_workouts": incomplete_count,
        "truncated": total > MAX_WORKOUTS,
        "unmapped_count": unknown_count,
        "unmapped": [
            {"name": name, "occurrences": count} for name, count in unmapped.items()
        ],
    }
