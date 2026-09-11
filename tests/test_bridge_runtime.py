from __future__ import annotations

import asyncio
import threading
from functools import partial
from uuid import uuid4

import pytest

from custom_components.health_assistant.bridge_runtime import BridgeRuntime
from custom_components.health_assistant.store.bridge_models import (
    BridgeError,
    canonical,
)
from custom_components.health_assistant.store.interchange import (
    export_archive,
    import_archive,
)
from tests.test_bridge import NOW, native_batch, native_record


def rearm_state(runtime, source_id, *, domains=("scalar",), streams=None):
    status = runtime.registry.status(source_id)
    return {
        "registration_id": source_id,
        "receiver_session_id": runtime.receiver_session_id,
        "domains": {
            item["domain"]: {
                "committed": {
                    key: item[key]
                    for key in (
                        "checkpoint_mode",
                        "latest_batch_id",
                        "latest_request_hash",
                        "checkpoint_id",
                    )
                },
                "pending_request": None,
            }
            for item in status["domains"]
            if item["domain"] in domains
        },
        "streams": streams or {},
    }


async def arm(runtime, source_id, state=None):
    return await runtime.async_rearm(
        "owner", state or rearm_state(runtime, source_id), lambda: None
    )


async def submit(runtime, source_id, grant, value=None, authorized=lambda: None):
    value = value or native_batch(source_id, [native_record(source_id)])
    return await runtime.async_ingest(
        source_id,
        canonical(value),
        "owner",
        grant["receiver_session_id"],
        grant["write_lease"],
        authorized,
    )


async def test_setup_has_no_lease_and_old_setup_grants_fail(hass, bridge):
    repository, source_id = bridge
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    grant = await arm(runtime, source_id)
    assert (await submit(runtime, source_id, grant))["changed"] == 1
    following = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    assert not following.leases
    with pytest.raises(BridgeError, match="session_required"):
        await submit(following, source_id, grant)
    state = rearm_state(following, source_id)
    new_grant = await arm(following, source_id, state)
    assert not (await submit(following, source_id, new_grant))["changed"]


@pytest.mark.parametrize("mode", ["none", "opaque_cas"])
async def test_lost_response_rearm_validates_pending_without_replaying(
    hass, bridge, mode
):
    repository, source_id = bridge
    repository.database.execute(
        "UPDATE bridge_receipts SET checkpoint_mode=? WHERE domain='scalar'", (mode,)
    )
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    state = rearm_state(runtime, source_id)
    batch = native_batch(
        source_id,
        [native_record(source_id)],
        checkpoint={"expected_checkpoint_id": None, "checkpoint_id": "first"}
        if mode == "opaque_cas"
        else None,
    )
    grant = await arm(runtime, source_id)
    assert (await submit(runtime, source_id, grant, batch))["changed"] == 1
    await runtime.async_stop()
    following = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    state["receiver_session_id"] = following.receiver_session_id
    state["domains"]["scalar"]["pending_request"] = batch
    before = [
        tuple(row)
        for row in repository.database.execute("SELECT * FROM bridge_records")
    ]
    grant = await arm(following, source_id, state)
    assert grant["acknowledged"] == {"domains": ["scalar"], "streams": []}
    assert [
        tuple(row)
        for row in repository.database.execute("SELECT * FROM bridge_records")
    ] == before
    assert (await submit(following, source_id, grant, batch))["replayed"]


@pytest.mark.parametrize(
    "change", ["hash", "null_with_history", "wrong_checkpoint", "second_domain"]
)
async def test_rearm_mismatch_never_grants_partial_lease(hass, bridge, change):
    repository, source_id = bridge
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    grant = await arm(runtime, source_id)
    await submit(runtime, source_id, grant)
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    state = rearm_state(runtime, source_id, domains=("scalar", "workout"))
    if change == "hash":
        state["domains"]["scalar"]["committed"]["latest_request_hash"] = "a" * 64
    elif change == "null_with_history":
        repository.database.execute(
            "UPDATE bridge_receipts SET batch_id=NULL,request_hash=NULL WHERE domain='scalar'"
        )
        state = rearm_state(runtime, source_id)
    elif change == "wrong_checkpoint":
        state["domains"]["scalar"]["committed"]["checkpoint_id"] = "bad"
    else:
        state["domains"]["workout"]["committed"].update(
            latest_batch_id=str(uuid4()), latest_request_hash="b" * 64
        )
    with pytest.raises(BridgeError, match="continuity_mismatch"):
        await arm(runtime, source_id, state)
    assert not runtime.leases


async def test_one_active_one_queued_then_busy_and_revoke_checks_both(
    hass, bridge, monkeypatch
):
    repository, source_id = bridge
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    grant = await arm(runtime, source_id)
    started, release = threading.Event(), threading.Event()
    original = runtime.repository.apply_batch

    def blocked(*args):
        with repository.database.transaction():
            started.set()
            assert release.wait(5)
            return original(*args)

    monkeypatch.setattr(runtime.repository, "apply_batch", blocked)
    active = asyncio.create_task(submit(runtime, source_id, grant))
    assert await hass.async_add_executor_job(started.wait, 5)
    queued = asyncio.create_task(submit(runtime, source_id, grant))
    await asyncio.sleep(0)
    with pytest.raises(BridgeError, match="busy"):
        await submit(runtime, source_id, grant)
    revoked = asyncio.create_task(runtime.async_revoke(source_id))
    await asyncio.sleep(0)
    release.set()
    outcomes = await asyncio.gather(active, queued, return_exceptions=True)
    await revoked
    assert all(isinstance(result, BridgeError) for result in outcomes)
    assert not repository.database.execute("SELECT * FROM bridge_records")
    assert not runtime._pending


async def test_body_admission_rejects_third_before_loading(hass, bridge):
    repository, source_id = bridge
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    grant = await arm(runtime, source_id)
    release = asyncio.Event()
    reads = 0

    async def body():
        nonlocal reads
        reads += 1
        await release.wait()
        return canonical(native_batch(source_id, [native_record(source_id)]))

    async def call():
        return await runtime.async_ingest(
            source_id,
            body,
            "owner",
            runtime.receiver_session_id,
            grant["write_lease"],
            lambda: None,
        )

    tasks = [asyncio.create_task(call()) for _ in range(2)]
    await asyncio.sleep(0)
    with pytest.raises(BridgeError, match="busy"):
        await call()
    assert reads == 2
    release.set()
    await asyncio.gather(*tasks)


async def test_preview_keeps_lease_live_apply_invalidates_and_blocks_rearm(
    hass, bridge, tmp_path
):
    repository, source_id = bridge
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    grant = await arm(runtime, source_id)
    await submit(runtime, source_id, grant)
    archive = tmp_path / "portable.tar.gz"
    await hass.async_add_executor_job(export_archive, repository.database, archive)
    await hass.async_add_executor_job(
        partial(
            import_archive,
            repository.database,
            archive,
            apply_context=runtime.import_context,
        )
    )
    assert grant["write_lease"] in runtime.leases
    async with runtime.suspend_import([source_id]):
        with pytest.raises(BridgeError, match="registration_paused"):
            await arm(runtime, source_id)
    assert not runtime.leases
    grant = await arm(runtime, source_id)
    await hass.async_add_executor_job(
        partial(
            import_archive,
            repository.database,
            archive,
            dry_run=False,
            apply_context=runtime.import_context,
        )
    )
    assert grant["write_lease"] not in runtime.leases
    assert repository.registry.get(source_id)["needs_fresh_namespace"] == 0


async def test_wearable_dispatch_requires_local_armed_stream_and_rechecks_retirement(
    hass, bridge
):
    repository, source_id = bridge
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    stream_id = str(uuid4())
    tip = {
        "stream_id": stream_id,
        "source_id": source_id,
        "origin_mode": "local_enrollment",
        "retired": False,
        "sequence": "0",
        "content_hash": None,
        "hash_version": 1,
    }
    calls = []

    def handler(source, batch, now, check):
        check()
        calls.append((source, batch, now))
        return {
            "changed": True,
            "replayed": False,
            "sequence": "1",
            "content_hash": "a" * 64,
        }

    runtime.register_wearable_handler(
        handler, tip=lambda _: tip, validate_pending=lambda *_: None
    )
    state = rearm_state(
        runtime,
        source_id,
        domains=(),
        streams={
            stream_id: {
                "committed": {"sequence": "0", "content_hash": None},
                "pending_batch": None,
            }
        },
    )
    grant = await arm(runtime, source_id, state)
    batch = {
        "version": 1,
        "domain": "wearable",
        "stream_batch": {"stream_id": stream_id},
    }
    assert (await submit(runtime, source_id, grant, batch))["sequence"] == "1"
    tip["retired"] = True
    with pytest.raises(BridgeError, match="registration_paused"):
        await submit(runtime, source_id, grant, batch)
    assert len(calls) == 1
    tip.update(retired=False, origin_mode="imported_history")
    with pytest.raises(BridgeError, match="registration_paused"):
        await arm(runtime, source_id, state)


async def test_auth_revoked_after_waiting_leaves_no_record(hass, bridge):
    repository, source_id = bridge
    runtime = BridgeRuntime(hass, repository.database, clock=lambda: NOW)
    grant = await arm(runtime, source_id)
    current = True

    def authorized():
        if not current:
            raise BridgeError("unauthorized")

    async def body():
        nonlocal current
        current = False
        return canonical(native_batch(source_id, [native_record(source_id)]))

    with pytest.raises(BridgeError, match="unauthorized"):
        await runtime.async_ingest(
            source_id,
            body,
            "owner",
            runtime.receiver_session_id,
            grant["write_lease"],
            authorized,
        )
    assert not repository.database.execute("SELECT * FROM bridge_records")
