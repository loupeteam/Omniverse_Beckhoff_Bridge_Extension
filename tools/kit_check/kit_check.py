"""
Headless Kit check for the Beckhoff bridge (v3, rebuilt for plc_bridge v2).

Run inside Kit with --exec. Environment:
  FIXCHECK_STAGE  stage to open (PLC prims under /PLC)
  FIXCHECK_MODE   "" = live against the PLC in the stage, "inject" = synthetic DATA_READ
Prints one line per check and "OK -- all fix checks passed" or "FAIL ...".
"""

import asyncio
import os
import sys
import threading
import time

import carb.events
import omni.kit.app
import omni.usd
from pxr import Sdf, Usd

STAGE = os.environ.get("FIXCHECK_STAGE")
MODE = os.environ.get("FIXCHECK_MODE", "")
EXT = "loupe.simulation.beckhoff_bridge"
LIVE_SEC = 5.0

fails = []
app = omni.kit.app.get_app()
mgr = app.get_extension_manager()

print("fix check -- Kit {}, Python {}.{}".format(app.get_build_version(), *sys.version_info[:2]))
print("=" * 68)


def _ver(e):
    v = e.get("version", "")
    return ".".join(str(x) for x in v if x != "") if isinstance(v, (tuple, list)) else str(v)


# --- 1. registered, enabled, clean startup -------------------------------------------
known = [e for e in mgr.get_extensions() if e.get("name", "") == EXT]
for e in known:
    print("  registered   {} {}  enabled={}  path={}".format(
        e.get("name", ""), _ver(e), e.get("enabled", False), e.get("path", "")))
if not any(e.get("enabled", False) for e in known):
    fails.append("extension not enabled")

from loupe.simulation.beckhoff_bridge.BeckhoffBridge import (  # noqa: E402
    EVENT_TYPE_DATA_READ, EVENT_TYPE_DATA_WRITE_REQ, Manager, get_system)
from loupe.simulation.common.RuntimeBase import get_stream_name  # noqa: E402
from plc_bridge import Sample  # noqa: E402

print("  startup      clean")


async def main():
    ctx = omni.usd.get_context()
    system = get_system()
    print("  components   before stage open: {}".format(system.get_component_names()))

    # --- 2. components follow the stage ---------------------------------------------
    await ctx.open_stage_async(STAGE)
    for _ in range(10):
        await app.next_update_async()
    names = system.get_component_names()
    print("  components   after stage open (no UI, no manual call): {}".format(names))
    if "PLC1" not in names:
        fails.append("PLC1 runtime not created from the stage")
        return
    rt = system.get_component("PLC1")

    # --- 3. runtime shape -------------------------------------------------------------
    threads = [t for t in threading.enumerate() if t.name == rt.name + "-plc"]
    print("  threads      {} worker(s), daemon={}".format(len(threads), [t.daemon for t in threads]))
    if len(threads) != 1 or not threads[0].daemon:
        fails.append("expected one daemon worker per PLC")
    print("  read names   {}".format(len(rt.read_variables)))
    before = rt.read_variables
    rt.options = {"beckhoff_bridge:RefreshRate": 25}
    ok1 = rt.refresh_rate == 25 and rt.read_variables == before
    rt.options = {"beckhoff_bridge:Variables": " A.b ,C.d" + chr(13) + ","}
    ok2 = rt.read_variables == ["A.b", "C.d"]
    rt.set_read_variables(before)
    rt.refresh_rate = 20
    print("  options set  partial_ok={} replace_ok={}".format(ok1, ok2))
    if not (ok1 and ok2):
        fails.append("Runtime.options setter broken")
    rt.write_sleep_time = 0.002
    print("  write_sleep  property ok={}".format(rt.write_sleep_time == 0.002 and rt.plc.write_sleep == 0.002))

    # --- 4. data flows: bus, on_sample, latest() ---------------------------------------
    bus = app.get_message_bus_event_stream()
    samples = {"bus": 0, "cb": 0, "keys": None}
    status = []
    sub = bus.create_subscription_to_push_by_type(
        get_stream_name(EVENT_TYPE_DATA_READ, "PLC1"),
        lambda ev: (samples.__setitem__("bus", samples["bus"] + 1),
                    samples.__setitem__("keys", list(ev.payload["data"].keys()))))
    remove = rt.plc.on_sample(lambda s: samples.__setitem__("cb", samples["cb"] + 1))
    rt.plc.on_connection(status.append)
    rt.plc.on_status(status.append)

    if MODE == "inject":
        print("  mode         injecting synthetic DATA_READ events (no PLC)")
        for i in range(6):
            bus.push(event_type=get_stream_name(EVENT_TYPE_DATA_READ, "PLC1"), payload={
                "meta": {"name": "PLC1"},
                "data": {"GVL_Moonlight": {"Axes": [{"ActualPosition": 15.0 + i}], "Command": {"Blend": 0.5}}}})
            await app.next_update_async()
    else:
        rt.enable_communication = True
        t0 = time.time()
        while time.time() - t0 < LIVE_SEC:
            await app.next_update_async()
    latest = rt.plc.latest()
    print("  live         bus={} on_sample={} in {:.1f}s, keys={}, latest.seq={}".format(
        samples["bus"], samples["cb"], LIVE_SEC, samples["keys"],
        latest.seq if isinstance(latest, Sample) else None))
    print("  status       {}".format(status[:6]))
    if MODE != "inject":
        if samples["bus"] == 0:
            fails.append("no DATA_READ reached the bus")
        if samples["cb"] == 0 or latest is None:
            fails.append("no sample reached on_sample / latest()")
        if samples["bus"] < 0.6 * LIVE_SEC * 50:
            fails.append("sample rate well below 50 Hz: {} in {}s".format(samples["bus"], LIVE_SEC))
        if "Connected" not in status:
            fails.append("never reported Connected")

    # --- 5. mirror and write-back ----------------------------------------------------
    stage = ctx.get_stage()
    mirror = [p.GetPath().pathString for p in stage.Traverse()
              if p.GetPath().pathString.startswith("/PLC/PLC1/") and p.GetName() == "GVL_Moonlight"]
    print("  mirror prims {}".format(mirror))
    prim = stage.GetPrimAtPath("/PLC/PLC1/GVL_Moonlight/Axes/_0/ActualPosition")
    value = prim.GetAttribute("value").Get() if prim and prim.IsValid() else None
    print("  array prim   valid={} value={}".format(bool(prim and prim.IsValid()), value))
    if not (prim and prim.IsValid()) or value is None:
        fails.append("array element prim not mirrored")

    requests = []
    reqsub = bus.create_subscription_to_push_by_type(
        get_stream_name(EVENT_TYPE_DATA_WRITE_REQ, "PLC1"),
        lambda ev: requests.append([(v["name"], v["value"]) for v in ev.payload["variables"]]))
    blend = stage.GetPrimAtPath("/PLC/PLC1/GVL_Moonlight/Command/Blend")
    if blend and blend.IsValid():
        attr = blend.GetAttribute("write:value")
        new_value = (attr.Get() or 0.0) + 1.0
        attr.Set(new_value)
        for _ in range(5):
            await app.next_update_async()
        print("  write-back   value={} requests={}".format(new_value, requests))
        if not requests or requests[-1] != [("GVL_Moonlight.Command.Blend", new_value)]:
            fails.append("write:value edit did not become a write request")
        if MODE != "inject":
            handle = rt.plc.queue_write("GVL_Moonlight.Command.Blend", new_value)
            got = handle.wait(2.0)
            print("  write ack    done={} ok={} error={}".format(got, handle.ok, handle.error))
            if not (got and handle.ok):
                fails.append("live write not acknowledged")
    else:
        print("  write-back   skipped: no Command/Blend prim")

    # --- 6. disable -------------------------------------------------------------------
    rt.enable_communication = False
    for _ in range(30):
        await app.next_update_async()
    print("  connected    {} after disable".format(rt.is_connected))
    if rt.is_connected:
        fails.append("still connected after disable")
    remove()
    sub = None
    reqsub = None

    print("-" * 68)
    if fails:
        print("FAIL -- " + "; ".join(fails))
    else:
        print("OK -- all fix checks passed")
    print("=" * 68)


async def run():
    try:
        await main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("FAIL -- exception: {!r}".format(e))
    sys.stdout.flush()
    print("posting quit at {}".format(time.time()), flush=True)
    app.post_quit()
    # omni.kit.window.file cancels a headless quit on a dirty stage (the mirror
    # dirties it); do not let that keep the process alive.
    threading.Thread(target=lambda: (time.sleep(15), os._exit(7)), daemon=True).start()


asyncio.ensure_future(run())
