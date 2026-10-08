"""
Headless Kit check for the Beckhoff extension on the PLC bridge framework (v4).

Run inside Kit with --exec (run.sh / run.ps1 do that). Environment:
  FIXCHECK_STAGE  stage to open; default stages/beckhoff_test.usda next to this file:
                  a 0.2.x prim /PLC/PLC1 (beckhoff_bridge:*) and a 0.3 prim /PLC/PLC2
                  (bridge:driver = "beckhoff"), both on the same PLC
  FIXCHECK_MODE   "" = live against the PLC in the stage, "inject" = no PLC: an in-memory
                  fake driver is registered under "beckhoff" and answers the reads itself
Prints one line per check and "OK -- all fix checks passed" or "FAIL ...".

What it covers: both extensions start; this extension registers AdsDriver; a
0.2.x script runs unchanged through the deprecated BeckhoffBridge module (with
its warning, on the 0.2.x bus names); legacy and neutral prims both become
runtimes; data at the refresh rate on the bus, on_sample and on_sample_main;
mirror and write-back on both prims; write acknowledgement; disable; and
disabling this extension removes its PLCs, enabling it brings them back.
"""

import asyncio
import os
import sys
import threading
import time
import warnings

import omni.kit.app
import omni.usd

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.abspath(os.environ.get("FIXCHECK_STAGE") or os.path.join(HERE, "stages", "beckhoff_test.usda")).replace("\\", "/")
MODE = os.environ.get("FIXCHECK_MODE", "")
EXT = "loupe.simulation.beckhoff_bridge"
FRAMEWORK = "loupe.simulation.bridge"
LIVE_SEC = 5.0
MAIN_THREAD = threading.current_thread()

fails = []
app = omni.kit.app.get_app()
mgr = app.get_extension_manager()

print("fix check -- Kit {}, Python {}.{}".format(app.get_build_version(), *sys.version_info[:2]))
print("=" * 68)


def _ver(e):
    v = e.get("version", "")
    return ".".join(str(x) for x in v if x != "") if isinstance(v, (tuple, list)) else str(v)


def quit_after(seconds):
    # omni.kit.window.file cancels a headless quit on a dirty stage (the mirror and
    # the write-back dirty it); do not let that, or a failed import, keep Kit alive.
    threading.Thread(target=lambda: (time.sleep(seconds), os._exit(7)), daemon=True).start()


# --- 1. both extensions registered and enabled, clean startup ------------------------
for name in (EXT, FRAMEWORK):
    known = [e for e in mgr.get_extensions() if e.get("name", "") == name]
    for e in known:
        print("  registered   {} {}  enabled={}  path={}".format(
            e.get("name", ""), _ver(e), e.get("enabled", False), e.get("path", "")))
    if not any(e.get("enabled", False) for e in known):
        fails.append("{} not enabled".format(name))

try:
    import plc_bridge  # noqa: E402
    from beckhoff_bridge import AdsDriver  # noqa: E402
    from loupe.simulation.bridge import get_system, on_sample_main, registry  # noqa: E402
    from loupe.simulation.bridge.bus import EVENT_TYPE_DATA_READ, get_stream_name  # noqa: E402
    from plc_bridge import Sample  # noqa: E402
except Exception as e:
    import traceback
    traceback.print_exc()
    print("FAIL -- import: {!r}".format(e), flush=True)
    app.post_quit()
    quit_after(15)
    raise

print("  startup      clean; plc_bridge {}, beckhoff_bridge {}".format(
    os.path.dirname(plc_bridge.__file__), os.path.dirname(sys.modules["beckhoff_bridge"].__file__)))

# --- 2. the driver is registered by this extension, not by the harness ---------------
spec = registry.get("beckhoff")
print("  driver       beckhoff -> {} options={} legacy_namespace={}".format(
    spec.driver_class.__name__ if spec else None, [o.key for o in spec.options] if spec else None,
    spec.legacy_namespace if spec else None))
if spec is None or spec.driver_class is not AdsDriver or spec.legacy_namespace != "beckhoff_bridge":
    fails.append("the extension did not register AdsDriver as 'beckhoff'")


class FakeDriver(plc_bridge.PlcDriver):
    """Inject mode: answers the stage's symbols from memory, no PLC."""

    symbol_separators = "."
    values = {
        "GVL_Moonlight.Command.Blend": 0.5, "GVL_Moonlight.Command.Busy": False, "GVL_Moonlight.Command.Enable": True,
        "GVL_Moonlight.Axes[0].ActualPosition": 15.0, "GVL_Moonlight.Axes[1].ActualPosition": 16.0,
        "GVL_Moonlight.Axes[2].ActualPosition": 17.0, "GVL_Moonlight.Axes[3].ActualPosition": 18.0,
    }

    def __init__(self, ams_net_id):
        self.ams_net_id = ams_net_id
        self.connected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def is_connected(self):
        return self.connected

    def read(self, symbols):
        values = {s: self.values[s] for s in symbols if s in self.values}
        errors = {s: "symbol not found" for s in symbols if s not in self.values}
        return plc_bridge.ReadResult(values, errors)

    def write(self, values):
        self.values.update(values)
        return {}


if MODE == "inject":
    registry.register("beckhoff", FakeDriver, spec.options, legacy_namespace="beckhoff_bridge")
    print("  mode         inject: FakeDriver registered over AdsDriver, no PLC")


async def ticks(n):
    for _ in range(n):
        await app.next_update_async()


async def main():
    ctx = omni.usd.get_context()
    system = get_system()
    print("  components   before stage open: {}".format(system.get_component_names()))

    # --- 3. components follow the stage: one 0.2.x prim, one 0.3 prim -----------------
    await ctx.open_stage_async(STAGE)
    await ticks(10)
    names = system.get_component_names()
    print("  components   after stage open (no UI, no manual call): {}".format(names))
    if "PLC1" not in names or "PLC2" not in names:
        fails.append("expected PLC1 and PLC2 runtimes from the stage, got {}".format(names))
        return
    old, new = system.get_component("PLC1"), system.get_component("PLC2")
    for label, rt in (("PLC1", old), ("PLC2", new)):
        print("  {}         driver={} class={} legacy={} ams={} vars={}".format(
            label, rt.driver_name, type(rt.driver).__name__, rt.legacy, rt.driver.ams_net_id, len(rt.read_variables)))
    if not (old.driver_name == "beckhoff" and old.legacy and new.driver_name == "beckhoff" and not new.legacy):
        fails.append("prim classification wrong")
    if MODE != "inject" and not (isinstance(old.driver, AdsDriver) and isinstance(new.driver, AdsDriver)):
        fails.append("runtimes not built on AdsDriver")
    threads = [t for t in threading.enumerate() if t.name.endswith("-plc")]
    print("  threads      {} worker(s) {}, daemon={}".format(
        len(threads), sorted(t.name for t in threads), [t.daemon for t in threads]))
    if len(threads) != 2 or not all(t.daemon for t in threads):
        fails.append("expected one daemon worker per PLC")

    # --- 4. a 0.2.x script, unchanged ---------------------------------------------------
    # This is the README's 0.2.x example. It imports the deprecated module and
    # gets the 0.2.x bus names and payloads.
    script = {"init": 0, "data": 0, "blend": None}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sys.modules.pop("loupe.simulation.beckhoff_bridge.BeckhoffBridge", None)
        from loupe.simulation.beckhoff_bridge import BeckhoffBridge
    deprecation = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    print("  0.2.x import DeprecationWarning: {}".format(deprecation[0][:96] + "..." if deprecation else None))
    if not deprecation:
        fails.append("importing BeckhoffBridge did not warn")

    beckhoff_bridge = BeckhoffBridge.Manager("PLC1")

    def on_beckhoff_init(event):
        script["init"] += 1
        beckhoff_bridge.add_cyclic_read_variables(["GVL_Moonlight.Command.Blend"])

    def on_message(event):
        script["data"] += 1
        script["blend"] = event.payload["data"]["GVL_Moonlight"]["Command"]["Blend"]

    beckhoff_bridge.register_init_callback(on_beckhoff_init)
    beckhoff_bridge.register_data_callback(on_message)
    try:
        BeckhoffBridge.Manager()
        nameless = "no error"
    except ValueError as e:
        nameless = "ValueError: {}".format(e)
    print("  Manager()    {}".format(nameless))
    if not nameless.startswith("ValueError"):
        fails.append("Manager() without a name did not raise")

    # --- 5. data: legacy bus, neutral bus, on_sample, on_sample_main, latest() -----------
    bus = app.get_message_bus_event_stream()
    counts = {k: 0 for k in ("legacy_bus", "neutral_bus1", "neutral_bus2", "cb1", "cb2", "main1", "main2")}
    main_threads = set()
    status = {"PLC1": [], "PLC2": []}

    def count(key):
        return lambda *_: counts.__setitem__(key, counts[key] + 1)

    subs = [
        bus.create_subscription_to_push_by_type(get_stream_name(BeckhoffBridge.EVENT_TYPE_DATA_READ, "PLC1"), count("legacy_bus")),
        bus.create_subscription_to_push_by_type(get_stream_name(EVENT_TYPE_DATA_READ, "PLC1"), count("neutral_bus1")),
        bus.create_subscription_to_push_by_type(get_stream_name(EVENT_TYPE_DATA_READ, "PLC2"), count("neutral_bus2")),
    ]
    removers = [
        old.plc.on_sample(count("cb1")),
        new.plc.on_sample(count("cb2")),
        on_sample_main("PLC1", lambda s: (count("main1")(), main_threads.add(threading.current_thread() is MAIN_THREAD))),
        on_sample_main("PLC2", lambda s: (count("main2")(), main_threads.add(threading.current_thread() is MAIN_THREAD))),
    ]
    for label, rt in (("PLC1", old), ("PLC2", new)):
        removers.append(rt.plc.on_connection(status[label].append))
        removers.append(rt.plc.on_status(status[label].append))

    frames0 = system.delivery.frames
    old.enable_communication = True
    new.enable_communication = True
    t0 = time.time()
    while time.time() - t0 < LIVE_SEC:
        await app.next_update_async()
    l1, l2 = old.plc.latest(), new.plc.latest()
    print("  data {:.0f}s      PLC1 legacy bus={} neutral bus={} on_sample={} on_sample_main={} latest.seq={}".format(
        LIVE_SEC, counts["legacy_bus"], counts["neutral_bus1"], counts["cb1"], counts["main1"],
        l1.seq if isinstance(l1, Sample) else None))
    print("               PLC2 neutral bus={} on_sample={} on_sample_main={} latest.seq={}".format(
        counts["neutral_bus2"], counts["cb2"], counts["main2"], l2.seq if isinstance(l2, Sample) else None))
    print("  frames       {} app updates in {:.0f}s".format(system.delivery.frames - frames0, LIVE_SEC))
    print("  0.2.x script init calls={} data callbacks={} Blend={}".format(script["init"], script["data"], script["blend"]))
    print("  status       PLC1 {}".format(status["PLC1"][:4]))
    print("  status       PLC2 {}".format(status["PLC2"][:4]))
    for key in ("legacy_bus", "neutral_bus1", "neutral_bus2", "main1", "main2"):
        if counts[key] == 0:
            fails.append("nothing on {}".format(key))
    for key in ("cb1", "cb2"):
        if counts[key] < 0.6 * LIVE_SEC * 50:
            fails.append("{} sample rate well below 50 Hz: {} in {}s".format(key, counts[key], LIVE_SEC))
    if main_threads != {True}:
        fails.append("on_sample_main delivered off the main thread")
    if script["data"] == 0 or script["blend"] is None:
        fails.append("the 0.2.x script's data callback got nothing")
    for label in ("PLC1", "PLC2"):
        if "Connected" not in status[label]:
            fails.append("{} never reported Connected".format(label))

    # --- 6. mirror on both prims ------------------------------------------------------
    stage = ctx.get_stage()
    for label, path in (("PLC1 array", "/PLC/PLC1/GVL_Moonlight/Axes/_0/ActualPosition"),
                        ("PLC2 array", "/PLC/PLC2/GVL_Moonlight/Axes/_2/ActualPosition"),
                        ("PLC2 value", "/PLC/PLC2/GVL_Moonlight/Command/Blend")):
        prim = stage.GetPrimAtPath(path)
        valid = bool(prim and prim.IsValid())
        value = prim.GetAttribute("value").Get() if valid else None
        print("  mirror       {} {} valid={} value={}".format(label, path, valid, value))
        if not valid or value is None:
            fails.append("{} not mirrored".format(label))

    # --- 7. writes: mirror write-back (PLC2), 0.2.x write_variable (PLC1), ack ----------
    writes = {"PLC1": [], "PLC2": []}
    removers.append(old.plc.on_write(writes["PLC1"].append))
    removers.append(new.plc.on_write(writes["PLC2"].append))
    blend = stage.GetPrimAtPath("/PLC/PLC2/GVL_Moonlight/Command/Blend")
    new_value = None
    if blend and blend.IsValid():
        attr = blend.GetAttribute("write:value")
        new_value = (attr.Get() or 0.0) + 1.0
        attr.Set(new_value)
        t0 = time.time()
        while time.time() - t0 < 2.0 and not writes["PLC2"]:
            await app.next_update_async()
        sent = [w for w in writes["PLC2"] if "GVL_Moonlight.Command.Blend" in w.values]
        print("  write-back   PLC2 write:value={} sent={}".format(new_value, sent[-1] if sent else writes["PLC2"]))
        if not sent or sent[-1].error or sent[-1].errors:
            fails.append("PLC2 write:value edit was not written")
    else:
        fails.append("no /PLC/PLC2/GVL_Moonlight/Command/Blend mirror prim to write through")
    script_value = (new_value or 0.0) + 1.0
    beckhoff_bridge.write_variable("GVL_Moonlight.Command.Blend", script_value)
    t0 = time.time()
    while time.time() - t0 < 2.0 and not writes["PLC1"]:
        await app.next_update_async()
    await ticks(10)
    print("  write        0.2.x write_variable({}) -> {} ; script now sees Blend={}".format(
        script_value, writes["PLC1"][-1] if writes["PLC1"] else None, script["blend"]))
    if not writes["PLC1"] or writes["PLC1"][-1].error or writes["PLC1"][-1].errors:
        fails.append("0.2.x write_variable was not written")
    handle = new.queue_write("GVL_Moonlight.Command.Blend", 0.5)
    got = handle.wait(2.0)
    print("  write ack    PLC2 done={} ok={} error={}".format(got, handle.ok, handle.error))
    if not (got and handle.ok):
        fails.append("write not acknowledged")

    # --- 8. disable disconnects ---------------------------------------------------------
    old.enable_communication = False
    new.enable_communication = False
    t0 = time.time()
    while time.time() - t0 < 3.0 and (old.is_connected or new.is_connected):
        await app.next_update_async()
    print("  connected    PLC1={} PLC2={} {:.2f}s after disable".format(old.is_connected, new.is_connected, time.time() - t0))
    if old.is_connected or new.is_connected:
        fails.append("still connected after disable")
    for remove in removers:
        remove()
    subs.clear()
    beckhoff_bridge.cleanup()

    # --- 9. the extension's lifecycle: disable unregisters, enable registers again -------
    if MODE == "inject":
        registry.register("beckhoff", AdsDriver, spec.options, legacy_namespace="beckhoff_bridge")
        await ticks(5)
    mgr.set_extension_enabled_immediate(EXT, False)
    await ticks(5)
    gone = (registry.get("beckhoff"), system.get_component_names(), sorted(system.unresolved.values()))
    mgr.set_extension_enabled_immediate(EXT, True)
    await ticks(5)
    back = (registry.get("beckhoff"), system.get_component_names())
    print("  ext disable  driver={} components={} unresolved={}".format(gone[0], gone[1], gone[2]))
    print("  ext enable   driver={} components={}".format(back[0].driver_class.__name__ if back[0] else None, back[1]))
    if gone[0] is not None or gone[1]:
        fails.append("disabling the extension left the driver or its PLCs behind")
    if back[0] is None or sorted(back[1]) != ["PLC1", "PLC2"]:
        fails.append("enabling the extension again did not bring the PLCs back")

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
    quit_after(15)


asyncio.ensure_future(run())
