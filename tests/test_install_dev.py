import json
import subprocess
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

    for path in dest.rglob("*"):
        if path.suffix in {".py", ".json"}:
            text = path.read_text().replace("health_assistant_dev", "")
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
