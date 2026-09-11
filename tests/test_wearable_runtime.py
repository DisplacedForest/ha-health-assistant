import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from custom_components.health_assistant.wearable_runtime import WearableRuntime


async def test_runtime_registers_handlers_and_removes_maintenance_timer(hass):
    bridge = SimpleNamespace(register_wearable_handler=Mock())
    runtime = WearableRuntime(hass, None, bridge)
    result = {"changed_streams": 0, "degraded_streams": 0}
    unsubscribe = Mock()
    with (
        patch.object(runtime.repository, "maintain", return_value=result) as maintain,
        patch(
            "custom_components.health_assistant.wearable_runtime.async_track_time_interval",
            return_value=unsubscribe,
        ) as timer,
    ):
        await runtime.async_start()
        bridge.register_wearable_handler.assert_called_once_with(
            runtime.repository.apply_batch,
            tip=runtime.repository.tip,
            validate_pending=runtime.repository.validate_pending,
        )
        assert timer.call_args.args[2].total_seconds() == 3600
        assert runtime.last_maintenance == result
        await runtime.async_stop()
        unsubscribe.assert_called_once()
        await runtime.async_maintain()
        assert maintain.call_count == 1


async def test_stop_drains_inflight_maintenance_and_coalesces_calls(hass):
    runtime = WearableRuntime(hass, None, SimpleNamespace())
    entered = asyncio.Event()
    release = threading.Event()
    calls = 0

    def maintain(_now):
        nonlocal calls
        calls += 1
        hass.loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return {"changed_streams": 0, "degraded_streams": 0}

    with patch.object(runtime.repository, "maintain", new=maintain):
        first = asyncio.create_task(runtime.async_maintain())
        await asyncio.wait_for(entered.wait(), 2)
        second = asyncio.create_task(runtime.async_maintain())
        await asyncio.sleep(0)
        stop = asyncio.create_task(runtime.async_stop())
        await asyncio.sleep(0)
        assert not stop.done()
        release.set()
        await asyncio.gather(first, second, stop)
        assert calls == 1
        assert runtime._task is None


async def test_canceled_waiter_keeps_worker_tracked_until_drained(hass):
    runtime = WearableRuntime(hass, None, SimpleNamespace())
    entered = asyncio.Event()
    release = threading.Event()

    def maintain(_now):
        hass.loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return {"changed_streams": 0, "degraded_streams": 0}

    with patch.object(runtime.repository, "maintain", new=maintain):
        waiter = asyncio.create_task(runtime.async_maintain())
        await asyncio.wait_for(entered.wait(), 2)
        waiter.cancel()
        await asyncio.sleep(0)
        assert runtime._task is not None
        stop = asyncio.create_task(runtime.async_stop())
        await asyncio.sleep(0)
        assert not stop.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        await stop
        assert runtime._task is None


async def test_stop_during_start_does_not_leave_a_timer(hass):
    runtime = WearableRuntime(
        hass, None, SimpleNamespace(register_wearable_handler=Mock())
    )
    entered = asyncio.Event()
    release = threading.Event()

    def maintain(_now):
        hass.loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return {"changed_streams": 0, "degraded_streams": 0}

    with (
        patch.object(runtime.repository, "maintain", new=maintain),
        patch(
            "custom_components.health_assistant.wearable_runtime.async_track_time_interval"
        ) as timer,
    ):
        start = asyncio.create_task(runtime.async_start())
        await asyncio.wait_for(entered.wait(), 2)
        stop = asyncio.create_task(runtime.async_stop())
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(start, stop)
        timer.assert_not_called()
