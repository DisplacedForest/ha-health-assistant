from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CONF_MAPPINGS, DOMAIN
from .providers import ProviderRegistry
from .store import HealthDatabase, MetricType
from .store.schema import SCHEMA_VERSION


def _collect_provider_facts(registry: ProviderRegistry) -> dict[str, Any]:
    facts = {}
    for key, provider in sorted(registry.providers.items()):
        capabilities = provider.capabilities
        status = registry.status(key)
        facts[key] = {
            "capabilities": {
                "metrics": sorted(metric.value for metric in capabilities.metrics),
                "workouts": capabilities.workouts,
                "can_import": capabilities.can_import,
                "can_export": capabilities.can_export,
            },
            "degraded": status.degraded,
            "last_success": (
                status.last_success.isoformat() if status.last_success else None
            ),
            "last_error": "provider_error" if status.last_error is not None else None,
        }
    return facts


def _collect_database_facts(database: HealthDatabase) -> dict[str, Any]:
    stored_version = database.execute("SELECT version FROM schema_info")
    journal_mode = database.execute("PRAGMA journal_mode")
    observation_counts = database.execute(
        "SELECT metric, COUNT(*) AS n FROM observations GROUP BY metric"
    )
    claim_counts = database.execute(
        "SELECT metric, COUNT(*) AS n FROM source_claims GROUP BY metric"
    )
    workout_count = database.execute("SELECT COUNT(*) AS n FROM workouts")
    observation_providers = database.execute(
        "SELECT provider, COUNT(*) AS n FROM source_claims GROUP BY provider"
    )
    workout_providers = database.execute(
        "SELECT provider, COUNT(*) AS n FROM workouts GROUP BY provider"
    )
    path = database.path
    return {
        "schema_version": int(stored_version[0][0]) if stored_version else None,
        "supported_schema_version": SCHEMA_VERSION,
        "file_exists": path.exists(),
        "file_size_bytes": path.stat().st_size if path.exists() else None,
        "journal_mode": str(journal_mode[0][0]) if journal_mode else None,
        "environment": {
            "stream_count": database.execute(
                "SELECT COUNT(*) FROM environment_streams"
            )[0][0],
            "bucket_count": database.execute(
                "SELECT COUNT(*) FROM environment_buckets"
            )[0][0],
            "maintenance": dict(
                database.execute(
                    "SELECT last_success_ms, duration_ms, rolled_up, deleted, failed FROM environment_maintenance WHERE id=1"
                )[0]
            ),
        },
        "observation_counts": {
            str(row["metric"]): int(row["n"]) for row in observation_counts
        },
        "claim_counts": {str(row["metric"]): int(row["n"]) for row in claim_counts},
        "workout_count": int(workout_count[0]["n"]),
        "observation_providers": {
            str(row["provider"]): int(row["n"]) for row in observation_providers
        },
        "workout_providers": {
            str(row["provider"]): int(row["n"]) for row in workout_providers
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    integration = await async_get_integration(hass, DOMAIN)
    mappings = entry.options.get(CONF_MAPPINGS, {})
    mapping_counts = {
        metric.value: len(mappings.get(metric.value, [])) for metric in MetricType
    }
    database_facts = await hass.async_add_executor_job(
        _collect_database_facts, entry.runtime_data.database
    )
    database_facts["environment"].update(entry.runtime_data.environment.diagnostics())
    return {
        "domain": DOMAIN,
        "version": str(integration.version),
        "entry_state": str(entry.state),
        "mapped_entity_counts": mapping_counts,
        "database": database_facts,
        "providers": _collect_provider_facts(entry.runtime_data.registry),
    }
