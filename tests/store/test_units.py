import pytest

from custom_components.health_assistant.store import MetricType, UnitConversionError
from custom_components.health_assistant.store.units import (
    canonical_unit,
    convert,
    normalize,
)


def test_exact_factors():
    assert convert(1.0, "lb", "kg") == 0.45359237
    assert convert(1.0, "st", "kg") == 6.35029318
    assert convert(1.0, "mi", "m") == 1609.344
    assert convert(1.0, "km", "m") == 1000.0
    assert convert(1.0, "kj", "kcal") == 1.0 / 4.184
    assert convert(2.0, "min", "s") == 120.0


def test_identity_and_aliases():
    assert convert(80.5, "kg", "kg") == 80.5
    assert convert(1.0, "lbs", "kg") == 0.45359237
    assert convert(100.0, "steps", "count") == 100.0
    assert convert(1.0, " KM ", "m") == 1000.0


def test_inverse_conversion():
    assert convert(1000.0, "m", "km") == 1.0
    assert convert(0.45359237, "kg", "lb") == pytest.approx(1.0)


def test_unknown_unit_raises():
    with pytest.raises(UnitConversionError):
        convert(1.0, "furlong", "m")
    with pytest.raises(UnitConversionError):
        convert(1.0, "kg", "m")


def test_normalize_targets_canonical_unit():
    assert canonical_unit(MetricType.WEIGHT) == "kg"
    assert normalize(180.0, "lb", MetricType.WEIGHT) == 180.0 * 0.45359237
    assert normalize(5.0, "km", MetricType.DISTANCE) == 5000.0
    assert normalize(22.5, "%", MetricType.BODY_FAT_PERCENTAGE) == 22.5


def test_normalize_is_deterministic():
    first = normalize(163.4, "lb", MetricType.WEIGHT)
    second = normalize(163.4, "lb", MetricType.WEIGHT)
    assert first == second
