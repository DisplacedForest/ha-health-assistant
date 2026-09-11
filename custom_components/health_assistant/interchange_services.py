from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path

import voluptuous as vol
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store import StoreError, StoreValidationError
from .store.interchange import export_archive, import_archive

SERVICES = ("export_history", "import_history")


@contextmanager
def archive_parent(root: Path, requested: str, create: bool):
    root = root.resolve()
    path = Path(requested)
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError as err:
            raise StoreValidationError(
                "Archive path must be under the Home Assistant config directory"
            ) from err
    if (
        not path.parts
        or any(part in ("..", ".") for part in path.parts)
        or not path.name.endswith(".tar.gz")
    ):
        raise StoreValidationError(
            "Use a config-relative .tar.gz archive path without traversal"
        )
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        for part in path.parts[:-1]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            following = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        yield descriptor, path
    finally:
        os.close(descriptor)


def _operate(database, root, requested, importing, dry_run, bridge=None):
    with archive_parent(root, requested, create=not importing) as (
        descriptor,
        relative,
    ):
        if importing:
            opened = os.open(
                relative.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=descriptor,
            )
            with os.fdopen(opened, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise StoreValidationError("Archive input must be a regular file")
                return import_archive(
                    database,
                    root / relative,
                    dry_run=dry_run,
                    source_file=source,
                    apply_context=bridge.import_context if bridge else None,
                )
        manifest = export_archive(database, root / relative, directory_fd=descriptor)
        return {
            "path": str(relative),
            "format_version": manifest["format_version"],
            "records": {
                name.removesuffix(".jsonl"): metadata["records"]
                for name, metadata in manifest["files"].items()
            },
        }


async def _async_history(call):
    from homeassistant.helpers.dispatcher import async_dispatcher_send

    entries = call.hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Health Assistant is not set up")
    importing = call.service == "import_history"
    dry_run = call.data.get("dry_run", True)
    try:
        result = await call.hass.async_add_executor_job(
            _operate,
            entries[0].runtime_data.database,
            Path(call.hass.config.config_dir),
            call.data["path"],
            importing,
            dry_run,
            entries[0].runtime_data.bridge,
        )
    except StoreValidationError as err:
        raise ServiceValidationError(str(err)) from err
    except (StoreError, OSError, sqlite3.Error) as err:
        raise HomeAssistantError(
            "History operation failed. Check the archive path and available disk space; an interrupted import can be retried."
        ) from err
    finally:
        if importing and not dry_run:
            async_dispatcher_send(call.hass, SIGNAL_HEALTH_DATA_UPDATED)
    return result if call.return_response else None


@callback
def async_setup_interchange_services(hass):
    for service in SERVICES:
        fields = {vol.Required("path"): cv.string}
        if service == "import_history":
            fields[vol.Optional("dry_run", default=True)] = cv.boolean
        async_register_admin_service(
            hass,
            DOMAIN,
            service,
            _async_history,
            schema=vol.Schema(fields),
            supports_response=SupportsResponse.OPTIONAL,
        )


@callback
def async_unload_interchange_services(hass):
    for service in SERVICES:
        hass.services.async_remove(DOMAIN, service)
