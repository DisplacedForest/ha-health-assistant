from __future__ import annotations

import asyncio
import concurrent.futures
import secrets
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from uuid import uuid4

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .signals import SIGNAL_HEALTH_DATA_UPDATED
from .store.bridge import BridgeRepository
from .store.bridge_models import (
    BridgeError,
    canonical,
    counter,
    digest,
    exact,
    normalize_batch,
    parse_body,
    uuid,
)
from .store.bridge_registry import BridgeRegistry
from .store.errors import StoreValidationError


@dataclass(frozen=True, slots=True)
class WriteLease:
    owner_id: str
    source_id: str
    generation: int
    domains: frozenset[str]
    streams: frozenset[str]


class BridgeRuntime:
    def __init__(self, hass, database, *, clock=None):
        self.hass = hass
        self.database = database
        self.registry = BridgeRegistry(database)
        self.repository = BridgeRepository(database)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.receiver_session_id = str(uuid4())
        self.leases = {}
        self._generations = {}
        self._locks = {}
        self._pending = {}
        self._suspended = set()
        self._import_lock = asyncio.Lock()
        self._stopped = False
        self._wearable_handler = self._wearable_tip = self._wearable_pending = None

    def register_wearable_handler(self, handler, *, tip, validate_pending):
        self._wearable_handler = handler
        self._wearable_tip = tip
        self._wearable_pending = validate_pending

    def _invalidate(self, source_id):
        self._generations[source_id] = self._generations.get(source_id, 0) + 1
        self.leases = {
            token: lease
            for token, lease in self.leases.items()
            if lease.source_id != source_id
        }

    def _eligible(self, source_id, session):
        if self._stopped or session != self.receiver_session_id:
            raise BridgeError("session_required")
        if source_id in self._suspended:
            raise BridgeError("registration_paused")

    def _lease(self, source_id, owner_id, session, token, domain, stream_id=None):
        self._eligible(source_id, session)
        lease = self.leases.get(token)
        if (
            lease is None
            or lease.source_id != source_id
            or lease.owner_id != owner_id
            or lease.generation != self._generations.get(source_id, 0)
        ):
            raise BridgeError("session_required")
        if domain == "wearable":
            if stream_id not in lease.streams:
                raise BridgeError("domain_not_allowed")
        elif domain is not None and domain not in lease.domains:
            raise BridgeError("domain_not_allowed")

    def _loop_check(self, callback):
        future = concurrent.futures.Future()

        def invoke():
            try:
                callback()
            except BridgeError as err:
                future.set_exception(err)
            else:
                future.set_result(None)

        self.hass.loop.call_soon_threadsafe(invoke)
        future.result(timeout=30)

    async def async_ingest(self, source_id, body, owner_id, session, token, authorized):
        uuid(source_id)
        self._eligible(source_id, session)
        authorized()
        self._lease(source_id, owner_id, session, token, None)
        if self._pending.get(source_id, 0) >= 2:
            raise BridgeError("busy")
        self._pending[source_id] = self._pending.get(source_id, 0) + 1
        try:
            body = await body() if callable(body) else body
            value = parse_body(body)
            domain = value.get("domain") if isinstance(value, dict) else None
            stream_batch = value.get("stream_batch") if domain == "wearable" else None
            stream_id = (
                stream_batch.get("stream_id")
                if isinstance(stream_batch, dict)
                else None
            )
            if domain == "wearable":
                exact(value, ("version", "domain", "stream_batch"))
                if type(value["version"]) is not int or value["version"] != 1:
                    raise BridgeError()
                uuid(stream_id)
                if self._wearable_handler is None:
                    raise BridgeError("domain_not_available")
            self._lease(source_id, owner_id, session, token, domain, stream_id)

            def current():
                authorized()
                self._lease(source_id, owner_id, session, token, domain, stream_id)

            def check_authorized():
                self._loop_check(current)
                self.registry.require_live(source_id, owner_id)
                if domain == "wearable":
                    tip = self._wearable_tip(stream_id)
                    if (
                        tip["source_id"] != source_id
                        or tip["retired"]
                        or tip["origin_mode"] != "local_enrollment"
                    ):
                        raise BridgeError("registration_paused")

            def apply():
                now = self.clock()
                if domain != "wearable":
                    return self.repository.apply_batch(
                        source_id, value, now, check_authorized
                    )
                with self.database.transaction():
                    check_authorized()
                    result = self._wearable_handler(
                        source_id, stream_batch, now, check_authorized
                    )
                    check_authorized()
                    return result

            async with self._locks.setdefault(source_id, asyncio.Lock()):
                current()
                task = asyncio.ensure_future(self.hass.async_add_executor_job(apply))
                try:
                    result = await asyncio.shield(task)
                except asyncio.CancelledError:
                    await asyncio.shield(task)
                    raise
            if result["changed"]:
                async_dispatcher_send(self.hass, SIGNAL_HEALTH_DATA_UPDATED)
            return result
        except StoreValidationError as err:
            if getattr(err, "code", "invalid_request") in (
                "revision_conflict",
                "batch_conflict",
                "checkpoint_conflict",
                "projection_conflict",
                "sequence_conflict",
            ):
                self._invalidate(source_id)
            raise
        finally:
            self._pending[source_id] -= 1
            if self._pending[source_id] == 0:
                del self._pending[source_id]

    async def async_status(self, source_id, owner_id, authorized):
        authorized()

        def read():
            with self.database.transaction():
                source = self.registry.get(source_id)
                if source["owner_id"] != owner_id:
                    raise BridgeError("registration_not_owned")
                return self.registry.status(source_id)

        result = await self.hass.async_add_executor_job(read)
        authorized()
        return {**result, "receiver_session_id": self.receiver_session_id}

    async def async_revoke(self, source_id):
        uuid(source_id)
        if not any(lease.source_id == source_id for lease in self.leases.values()):
            await self.hass.async_add_executor_job(self.registry.get, source_id)
        self._invalidate(source_id)
        await self.hass.async_add_executor_job(self._drain)

    def _drain(self):
        with self.database.transaction():
            pass

    async def async_stop(self):
        self._stopped = True
        self.leases.clear()
        await self.hass.async_add_executor_job(self._drain)

    @asynccontextmanager
    async def suspend_import(self, source_ids):
        async with self._import_lock:
            for source_id in source_ids:
                self._suspended.add(source_id)
                self._invalidate(source_id)
            try:
                await self.hass.async_add_executor_job(self._drain)
                yield
            finally:
                self._suspended.difference_update(source_ids)

    @contextmanager
    def import_context(self, source_ids):
        context = self.suspend_import(tuple(source_ids))
        asyncio.run_coroutine_threadsafe(context.__aenter__(), self.hass.loop).result()
        try:
            yield
        finally:
            asyncio.run_coroutine_threadsafe(
                context.__aexit__(None, None, None), self.hass.loop
            ).result()

    async def async_rearm(self, owner_id, value, authorized):
        exact(value, ("registration_id", "receiver_session_id", "domains", "streams"))
        source_id = uuid(value["registration_id"])
        session = value["receiver_session_id"]
        self._eligible(source_id, session)
        authorized()
        generation = self._generations.get(source_id, 0)

        def check():
            authorized()
            self._eligible(source_id, session)
            if generation != self._generations.get(source_id, 0):
                raise BridgeError("registration_paused")

        async with self._locks.setdefault(source_id, asyncio.Lock()):
            try:
                acknowledged = await self.hass.async_add_executor_job(
                    partial(
                        self._prepare_rearm,
                        source_id,
                        owner_id,
                        value,
                        lambda: self._loop_check(check),
                    )
                )
            except BridgeError as err:
                if err.code == "continuity_mismatch":
                    self._invalidate(source_id)
                raise
            check()
            token = secrets.token_urlsafe(32)
            self.leases[token] = WriteLease(
                owner_id,
                source_id,
                generation,
                frozenset(value["domains"]),
                frozenset(value["streams"]),
            )
            return {
                "registration_id": source_id,
                "receiver_session_id": session,
                "write_lease": token,
                "acknowledged": acknowledged,
            }

    def _prepare_rearm(self, source_id, owner_id, value, check):
        domains, streams = value["domains"], value["streams"]
        if (
            not isinstance(domains, dict)
            or not isinstance(streams, dict)
            or not domains
            and not streams
            or len(domains) > 4
            or len(streams) > 256
        ):
            raise BridgeError()
        canonical(value)
        with self.database.transaction():
            check()
            self.registry.require_live(source_id, owner_id)
            modes = self.registry.modes(source_id)
            status = {
                item["domain"]: item
                for item in self.registry.status(source_id)["domains"]
            }
            acknowledged = {"domains": [], "streams": []}
            keys = (
                "checkpoint_mode",
                "latest_batch_id",
                "latest_request_hash",
                "checkpoint_id",
            )
            for domain, state in domains.items():
                if domain not in status:
                    raise BridgeError("domain_not_allowed")
                exact(state, ("committed", "pending_request"))
                committed = state["committed"]
                exact(committed, keys)
                self._committed(committed, modes[domain])
                receiver = {key: status[domain][key] for key in keys}
                pending = state["pending_request"]
                if pending is not None:
                    pending = normalize_batch(source_id, pending, modes, self.clock())
                    if (
                        pending.domain != domain
                        or pending.batch_id == committed["latest_batch_id"]
                        or pending.checkpoint is not None
                        and pending.checkpoint["expected_checkpoint_id"]
                        != committed["checkpoint_id"]
                    ):
                        raise BridgeError("continuity_mismatch")
                if committed == receiver and not (
                    receiver["latest_batch_id"] is None
                    and status[domain]["authoritative_records_present"]
                ):
                    continue
                if (
                    pending is not None
                    and pending.batch_id == receiver["latest_batch_id"]
                    and pending.request_hash == receiver["latest_request_hash"]
                    and (
                        pending.checkpoint["checkpoint_id"]
                        if pending.checkpoint
                        else None
                    )
                    == receiver["checkpoint_id"]
                ):
                    acknowledged["domains"].append(domain)
                    continue
                raise BridgeError("continuity_mismatch")
            for stream_id, state in streams.items():
                uuid(stream_id)
                if self._wearable_tip is None:
                    raise BridgeError("domain_not_available")
                exact(state, ("committed", "pending_batch"))
                exact(state["committed"], ("sequence", "content_hash"))
                committed = state["committed"]
                sequence = counter(committed["sequence"])
                if sequence == 0:
                    if committed["content_hash"] is not None:
                        raise BridgeError("continuity_mismatch")
                else:
                    digest(committed["content_hash"])
                tip = self._wearable_tip(stream_id)
                if (
                    tip["source_id"] != source_id
                    or tip["retired"]
                    or tip["origin_mode"] != "local_enrollment"
                ):
                    raise BridgeError("registration_paused")
                pending = state["pending_batch"]
                if pending is not None:
                    pending = self._wearable_pending(source_id, pending, self.clock())
                    if (
                        pending["stream_id"] != stream_id
                        or counter(pending["expected_sequence"]) != sequence
                        or counter(pending["sequence"]) != sequence + 1
                    ):
                        raise BridgeError("continuity_mismatch")
                if (
                    counter(tip["sequence"]) == sequence
                    and tip["content_hash"] == committed["content_hash"]
                ):
                    continue
                if (
                    pending is not None
                    and pending["sequence"] == tip["sequence"]
                    and pending["content_hash"] == tip["content_hash"]
                ):
                    acknowledged["streams"].append(stream_id)
                    continue
                raise BridgeError("continuity_mismatch")
            check()
            return acknowledged

    @staticmethod
    def _committed(value, mode):
        if value["checkpoint_mode"] != mode:
            raise BridgeError("continuity_mismatch")
        batch_id, request_hash = value["latest_batch_id"], value["latest_request_hash"]
        if batch_id is None:
            if request_hash is not None or value["checkpoint_id"] is not None:
                raise BridgeError("continuity_mismatch")
        else:
            uuid(batch_id)
            digest(request_hash)
            if mode == "opaque_cas":
                from .store.bridge_models import checkpoint

                checkpoint(
                    {
                        "expected_checkpoint_id": None,
                        "checkpoint_id": value["checkpoint_id"],
                    },
                    mode,
                )
        if mode == "none" and value["checkpoint_id"] is not None:
            raise BridgeError("continuity_mismatch")
