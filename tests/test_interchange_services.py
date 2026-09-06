from pathlib import Path

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized

from custom_components.health_assistant.const import DOMAIN


async def setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_history_service_defaults_and_lifecycle(hass, config_entry):
    await setup(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "add_observation",
        {"metric": "weight", "value": 80, "unit": "kg", "external_id": "history"},
        blocking=True,
    )
    result = await hass.services.async_call(
        DOMAIN,
        "export_history",
        {"path": "history/example.tar.gz"},
        blocking=True,
        return_response=True,
    )
    assert result["records"]["source_claims"] == 1
    assert result["path"] == "history/example.tar.gz"
    result = await hass.services.async_call(
        DOMAIN,
        "import_history",
        {"path": "history/example.tar.gz"},
        blocking=True,
        return_response=True,
    )
    assert result["dry_run"] is True
    assert result["expected"]["source_claims"]["unchanged"] == 1
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "export_history")
    assert not hass.services.has_service(DOMAIN, "import_history")


async def test_history_services_require_admin(hass, config_entry, hass_read_only_user):
    await setup(hass, config_entry)
    for service in ("export_history", "import_history"):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                service,
                {"path": "history.tar.gz"},
                blocking=True,
                context=Context(user_id=hass_read_only_user.id),
            )
    assert not Path(hass.config.path("history.tar.gz")).exists()


async def test_archive_paths_cannot_escape_or_follow_symlinks(
    hass, config_entry, tmp_path
):
    await setup(hass, config_entry)
    root = Path(hass.config.config_dir)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    forbidden = (
        "../escape.tar.gz",
        str(root.parent / "escape.tar.gz"),
        "linked/escape.tar.gz",
        "configuration.yaml",
    )
    for path in forbidden:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN, "export_history", {"path": path}, blocking=True
            )
    assert not (outside / "escape.tar.gz").exists()
    assert not (root.parent / "escape.tar.gz").exists()


async def test_import_rejects_symlink_and_non_regular_input(hass, config_entry):
    import os

    await setup(hass, config_entry)
    root = Path(hass.config.config_dir)
    (root / "target.tar.gz").write_text("invalid")
    (root / "linked.tar.gz").symlink_to(root / "target.tar.gz")
    os.mkfifo(root / "pipe.tar.gz")
    for filename in ("linked.tar.gz", "pipe.tar.gz"):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN, "import_history", {"path": filename}, blocking=True
            )
