from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from .models import (
    BODY_MEASUREMENT_METRICS,
    DAILY_ACTIVITY_METRICS,
    MetricType,
    SourceClaim,
)


class MetricClass(StrEnum):
    BODY_MEASUREMENT = "body_measurement"
    DAILY_ACTIVITY = "daily_activity"


@dataclass(frozen=True, slots=True)
class ValueTolerance:
    absolute: float
    relative: float


@dataclass(frozen=True, slots=True)
class ReconciliationRule:
    merge_window: timedelta | None
    suspicious_window: timedelta | None
    value_tolerance: ValueTolerance | None = None


RECONCILIATION_RULES: dict[MetricClass, ReconciliationRule] = {
    MetricClass.BODY_MEASUREMENT: ReconciliationRule(
        merge_window=timedelta(minutes=2),
        suspicious_window=timedelta(minutes=30),
        value_tolerance=ValueTolerance(absolute=0.5, relative=0.01),
    ),
    MetricClass.DAILY_ACTIVITY: ReconciliationRule(
        merge_window=None,
        suspicious_window=None,
    ),
}


def values_close(left: float, right: float, tolerance: ValueTolerance | None) -> bool:
    if tolerance is None:
        return True
    delta = abs(left - right)
    if delta <= tolerance.absolute:
        return True
    return delta <= tolerance.relative * max(abs(left), abs(right))


def metric_class(metric: MetricType) -> MetricClass:
    if metric in BODY_MEASUREMENT_METRICS:
        return MetricClass.BODY_MEASUREMENT
    if metric in DAILY_ACTIVITY_METRICS:
        return MetricClass.DAILY_ACTIVITY
    raise ValueError(f"metric {metric!r} has no reconciliation class")


def rule_for(metric: MetricType) -> ReconciliationRule:
    return RECONCILIATION_RULES[metric_class(metric)]


def claim_sort_key(claim: SourceClaim) -> tuple:
    return (claim.observed_at, claim.provider, claim.external_id)


def group_claims(
    claims: list[SourceClaim], rule: ReconciliationRule
) -> list[list[SourceClaim]]:
    ordered = sorted(claims, key=claim_sort_key)
    groups: list[list[SourceClaim]] = []
    for claim in ordered:
        if groups and rule.merge_window is not None:
            group = groups[-1]
            anchor = group[0]
            providers = {member.provider for member in group}
            if (
                claim.observed_at - anchor.observed_at <= rule.merge_window
                and claim.provider not in providers
                and all(
                    values_close(claim.value, member.value, rule.value_tolerance)
                    for member in group
                )
            ):
                group.append(claim)
                continue
        groups.append([claim])
    return groups


def provider_rank(provider: str, priority: list[str]) -> int:
    try:
        return priority.index(provider)
    except ValueError:
        return len(priority)


def supplying_claim(group: list[SourceClaim], priority: list[str]) -> SourceClaim:
    ordered = sorted(group, key=claim_sort_key)
    return min(ordered, key=lambda claim: provider_rank(claim.provider, priority))


def suspicious_group_indexes(
    groups: list[list[SourceClaim]], rule: ReconciliationRule
) -> set[int]:
    flagged: set[int] = set()
    if rule.suspicious_window is None:
        return flagged
    for left in range(len(groups)):
        for right in range(left + 1, len(groups)):
            delta = groups[right][0].observed_at - groups[left][0].observed_at
            if delta > rule.suspicious_window:
                break
            left_providers = {claim.provider for claim in groups[left]}
            right_providers = {claim.provider for claim in groups[right]}
            if left_providers - right_providers and right_providers - left_providers:
                flagged.add(left)
                flagged.add(right)
    return flagged
