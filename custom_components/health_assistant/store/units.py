from __future__ import annotations

from .errors import UnitConversionError
from .models import CANONICAL_UNITS, MetricType

_FACTORS_TO_CANONICAL: dict[tuple[str, str], float] = {
    ("g", "kg"): 0.001,
    ("lb", "kg"): 0.45359237,
    ("st", "kg"): 6.35029318,
    ("cm", "m"): 0.01,
    ("ft", "m"): 0.3048,
    ("km", "m"): 1000.0,
    ("mi", "m"): 1609.344,
    ("kj", "kcal"): 1.0 / 4.184,
    ("min", "s"): 60.0,
    ("h", "s"): 3600.0,
}

_ALIASES: dict[str, str] = {
    "kg": "kg",
    "g": "g",
    "lb": "lb",
    "lbs": "lb",
    "st": "st",
    "m": "m",
    "cm": "cm",
    "ft": "ft",
    "km": "km",
    "mi": "mi",
    "kcal": "kcal",
    "kj": "kj",
    "s": "s",
    "min": "min",
    "h": "h",
    "%": "%",
    "count": "count",
    "steps": "count",
}


def canonical_unit(metric: MetricType) -> str:
    return CANONICAL_UNITS[metric]


def convert(value: float, from_unit: str, to_unit: str) -> float:
    source = _ALIASES.get(from_unit.strip().lower(), from_unit.strip().lower())
    target = _ALIASES.get(to_unit.strip().lower(), to_unit.strip().lower())
    if source == target:
        return value
    factor = _FACTORS_TO_CANONICAL.get((source, target))
    if factor is not None:
        return value * factor
    inverse = _FACTORS_TO_CANONICAL.get((target, source))
    if inverse is not None:
        return value / inverse
    raise UnitConversionError(f"no conversion from {from_unit!r} to {to_unit!r}")


def normalize(value: float, unit: str, metric: MetricType) -> float:
    return convert(value, unit, canonical_unit(metric))
