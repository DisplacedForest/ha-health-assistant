import importlib
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "install_dev.sh"


def run_install(config_dir):
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "HA_CONFIG_DIR": str(config_dir),
            "HOME": str(config_dir),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        check=True,
    )


def test_install_dev_rewrites_domain(tmp_path):
    run_install(tmp_path)
    dest = tmp_path / "custom_components" / "health_assistant_dev"

    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["domain"] == "health_assistant_dev"
    assert manifest["name"] == "Health Assistant (Dev)"

    const = (dest / "const.py").read_text()
    assert 'DOMAIN = "health_assistant_dev"' in const
    assert 'NAME = "Health Assistant (Dev)"' in const

    translations = json.loads((dest / "translations" / "en.json").read_text())
    assert "Health Assistant (Dev)" in translations["config"]["step"]["user"]["title"]

    assert (dest / "services.yaml").exists()
    for path in dest.rglob("*"):
        if path.suffix in {".py", ".json", ".yaml"}:
            text = (
                path.read_text()
                .replace("health_assistant_dev", "")
                .replace("health_assistant.sparse_record", "")
                .replace("health_assistant.sparse_batch", "")
                .replace("health_assistant.wearable_batch", "")
                .replace("health_assistant.wearable_snapshot.v1", "")
            )
            assert "health_assistant" not in text
            assert "Health Assistant (Dev) (Dev)" not in path.read_text()

    assert not list(dest.rglob("__pycache__"))
    assert not list(dest.rglob("*.pyc"))


def test_install_dev_is_idempotent(tmp_path):
    run_install(tmp_path)
    marker = tmp_path / "custom_components" / "health_assistant_dev" / "stale.py"
    marker.write_text("x = 1\n")
    run_install(tmp_path)
    assert not marker.exists()
    manifest = json.loads(
        (
            tmp_path / "custom_components" / "health_assistant_dev" / "manifest.json"
        ).read_text()
    )
    assert manifest["domain"] == "health_assistant_dev"


def test_installed_dev_preserves_sparse_hashes_and_archive_interoperability(
    tmp_path, monkeypatch
):
    from custom_components.health_assistant.store import HealthDatabase
    from custom_components.health_assistant.store.interchange import import_archive
    from custom_components.health_assistant.store.recovery import archive_observation
    from custom_components.health_assistant.store.recovery_models import (
        normalized_observation,
    )
    from custom_components.health_assistant.store.sleep import archive_session
    from custom_components.health_assistant.store.sleep_models import normalized_session

    run_install(tmp_path)
    store_path = tmp_path / "custom_components/health_assistant_dev/store"
    package = "installed_health_store_fixture"
    spec = importlib.util.spec_from_file_location(
        package,
        store_path / "__init__.py",
        submodule_search_locations=[str(store_path)],
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, package, module)
    installed_db = target = None
    try:
        spec.loader.exec_module(module)
        recovery = importlib.import_module(f"{package}.recovery")
        sleep = importlib.import_module(f"{package}.sleep")
        interchange = importlib.import_module(f"{package}.interchange")
        now = datetime(2026, 9, 7, 12, tzinfo=UTC)
        payload = {
            "started_at": "2026-09-07T00:00:00Z",
            "ended_at": "2026-09-07T01:00:00Z",
        }
        normal_sleep = normalized_session(
            "fixture", "account", "sleep", 1, payload, now
        )
        normal_recovery = normalized_observation(
            "fixture",
            "account",
            "recovery",
            1,
            {**payload, "value": 50, "unit": "ms"},
            now,
            metric="hrv_sdnn",
        )
        installed_sleep = sleep.parse_archive_session(
            archive_session(normal_sleep), now
        )
        installed_recovery = recovery.parse_archive_observation(
            archive_observation(normal_recovery), now
        )
        assert installed_sleep.payload_hash == normal_sleep.payload_hash
        assert installed_recovery.payload_hash == normal_recovery.payload_hash
        installed_db = module.HealthDatabase(tmp_path / "dev.sqlite")
        installed_db.open()
        module.SleepRepository(installed_db, clock=lambda: now).apply_sleep_changes(
            [installed_sleep]
        )
        module.RecoveryRepository(
            installed_db, clock=lambda: now
        ).apply_recovery_changes([installed_recovery])
        archive = tmp_path / "dev-history.tar.gz"
        interchange.export_archive(installed_db, archive)
        target = HealthDatabase(tmp_path / "normal.sqlite")
        target.open()
        result = import_archive(target, archive, dry_run=False)
        assert result["applied"]["sleep_sessions"]["create"] == 1
        assert result["applied"]["recovery_records"]["create"] == 1
        assert (
            target.execute("SELECT payload_hash FROM sleep_sessions")[0][0]
            == normal_sleep.payload_hash
        )
        assert (
            target.execute("SELECT payload_hash FROM recovery_records")[0][0]
            == normal_recovery.payload_hash
        )
    finally:
        if installed_db is not None:
            installed_db.close()
        if target is not None:
            target.close()
        for key in list(sys.modules):
            if key.startswith(f"{package}."):
                sys.modules.pop(key)
