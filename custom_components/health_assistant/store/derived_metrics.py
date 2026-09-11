from __future__ import annotations

import math
from datetime import timedelta
from statistics import fmean, stdev

CALCULATION_VERSION = 1


def finite(value):
    if not math.isfinite(value):
        raise ArithmeticError
    return value


def trend(values):
    if len(values) < 3:
        return None, "insufficient_history"
    try:
        origin = values[0][0]
        xs = [(day - origin).days for day, _ in values]
        ys = [value for _, value in values]
        xbar, ybar = fmean(xs), finite(fmean(ys))
        numerator = math.fsum(
            (x - xbar) * (y - ybar) for x, y in zip(xs, ys, strict=True)
        )
        denominator = math.fsum((x - xbar) ** 2 for x in xs)
        return finite(numerator / denominator), None
    except ArithmeticError, ValueError:
        return None, "calculation_unavailable"


def rolling(points, end, days):
    start = end - timedelta(days=days)
    values = [
        (day, point["value"])
        for day, point in sorted(points.items())
        if start <= day < end and point["value"] is not None
    ]
    mean, reason = None, "no_observation"
    if values:
        try:
            mean, reason = finite(fmean(value for _, value in values)), None
        except ArithmeticError, ValueError:
            reason = "calculation_unavailable"
    slope, trend_reason = trend(values)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "mean": mean,
        "n": len(values),
        "possible_days": days,
        "coverage": len(values) / days,
        "mean_reason": reason,
        "trend_slope": slope,
        "trend_reason": trend_reason,
    }


def baseline(points, day):
    start = day - timedelta(days=28)
    values = [
        point["value"]
        for key, point in sorted(points.items())
        if start <= key < day and point["value"] is not None
    ]
    result = {
        "start_date": start.isoformat(),
        "end_date": day.isoformat(),
        "n": len(values),
        "possible_days": 28,
        "coverage": len(values) / 28,
        "mean": None,
        "stddev": None,
        "deviation": None,
        "z": None,
        "baseline_reason": "insufficient_history",
        "z_reason": "insufficient_history",
    }
    if len(values) < 14:
        return result
    try:
        mean, deviation = finite(fmean(values)), finite(stdev(values))
        result.update(mean=mean, stddev=deviation, baseline_reason=None)
        target = points.get(day, {}).get("value")
        if target is None:
            result["z_reason"] = "no_current_value"
        else:
            result["deviation"] = finite(target - mean)
            result["z_reason"] = "constant_baseline" if deviation == 0 else None
            if deviation > 0:
                result["z"] = finite(result["deviation"] / deviation)
    except ArithmeticError, ValueError:
        result.update(
            mean=None,
            stddev=None,
            deviation=None,
            z=None,
            baseline_reason="calculation_unavailable",
            z_reason="calculation_unavailable",
        )
    return result
