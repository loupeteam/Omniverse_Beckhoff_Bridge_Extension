"""Soak run inside Kit: the bridge against a live PLC for a long time.

Run with kit.exe --exec, in the app that run.ps1 builds from
fixcheck.kit.template (Kit's working directory must not be this repo's root).
Opens SOAK_STAGE (for example stages/beckhoff_test.usda: a 0.2.x prim PLC1 and
a 0.3 prim PLC2), enables both PLCs and, every 10 s, appends one JSON line to
SOAK_LOG: samples per PLC, connection state, the `*-plc` worker threads, the
process working set and private bytes, and the connection and status events
since the last line. Once a minute it queues a write of
GVL_Moonlight.Command.Blend on PLC2. After SOAK_SEC seconds (default 1920) it
disables both PLCs, closes the stage, logs the workers still alive (expected:
none), prints `SOAK DONE ...` and quits (exit code 7, as kit_check.py).

Environment: SOAK_STAGE, SOAK_LOG (required); SOAK_SEC; SOAK_ENABLE=0 to leave
the PLCs disabled (a control run); SOAK_TRACE=1 to trace Python allocations
with tracemalloc from the first minute to the end, into SOAK_LOG + ".trace.txt".

Dropping the PLC is done from outside, for example by switching the local
TwinCAT runtime to Config and back over ADS. docs/RELEASE_0.3.0.md has the
0.3.0 run.
"""

import asyncio
import ctypes
import ctypes.wintypes as wt
import json
import os
import threading
import time

import omni.kit.app
import omni.usd

STAGE = os.environ["SOAK_STAGE"]
LOG = os.environ["SOAK_LOG"]
DURATION = float(os.environ.get("SOAK_SEC", "1920"))
app = omni.kit.app.get_app()


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def rss_mb():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.WorkingSetSize / 2**20, 1), round(c.PagefileUsage / 2**20, 1)


def log(rec):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def quit_after(seconds):
    threading.Thread(target=lambda: (time.sleep(seconds), os._exit(7)), daemon=True).start()


async def main():
    from loupe.simulation.bridge import get_system, on_sample_main

    ctx = omni.usd.get_context()
    await ctx.open_stage_async(STAGE)
    for _ in range(10):
        await app.next_update_async()
    system = get_system()
    rts = {n: system.get_component(n) for n in ("PLC1", "PLC2")}
    counts = {n: 0 for n in rts}
    main_counts = {n: 0 for n in rts}
    events = []
    removers = []
    for n, rt in rts.items():
        removers.append(rt.plc.on_sample(lambda s, n=n: counts.__setitem__(n, counts[n] + 1)))
        removers.append(on_sample_main(n, lambda s, n=n: main_counts.__setitem__(n, main_counts[n] + 1)))
        removers.append(rt.plc.on_connection(lambda c, n=n: events.append((round(time.time(), 3), n, "connection", str(c)))))
        removers.append(rt.plc.on_status(lambda s, n=n: events.append((round(time.time(), 3), n, "status", str(s)[:120]))))
    if os.environ.get("SOAK_ENABLE", "1") == "1":
        for rt in rts.values():
            rt.enable_communication = True
    t0 = time.time()
    log({"t": 0, "start": time.strftime("%Y-%m-%d %H:%M:%S"), "rss_mb": rss_mb(), "threads": threading.active_count()})
    next_log, next_write, seen_events, blend = t0 + 10, t0 + 60, 0, 0.0
    TRACE = os.environ.get("SOAK_TRACE") == "1"
    snap0 = None
    while time.time() - t0 < DURATION:
        await app.next_update_async()
        now = time.time()
        if now >= next_write:
            next_write += 60
            blend = 0.25 if blend != 0.25 else 0.75
            h = rts["PLC2"].plc.queue_write("GVL_Moonlight.Command.Blend", blend)
            events.append((round(now, 3), "PLC2", "write", str(blend)))
        if TRACE and snap0 is None and now - t0 >= 60:
            import tracemalloc
            tracemalloc.start(10)
            snap0 = tracemalloc.take_snapshot()
            snap_t = now
        if now >= next_log:
            next_log += 10
            workers = sorted(t.name for t in threading.enumerate() if t.name.endswith("-plc"))
            rec = {"t": round(now - t0, 1), "rss_mb": rss_mb(), "threads": threading.active_count(),
                   "workers": workers, "samples": dict(counts), "main": dict(main_counts),
                   "connected": {n: rt.is_connected for n, rt in rts.items()},
                   "seq": {n: (rt.plc.latest().seq if rt.plc.latest() else None) for n, rt in rts.items()},
                   "events": events[seen_events:]}
            seen_events = len(events)
            log(rec)
    if TRACE and snap0 is not None:
        import tracemalloc
        snap1 = tracemalloc.take_snapshot()
        with open(LOG + ".trace.txt", "w", encoding="utf-8") as f:
            f.write("traced for {:.0f}s, current {:.1f} MB\n".format(time.time() - snap_t, tracemalloc.get_traced_memory()[0] / 2**20))
            for st in snap1.compare_to(snap0, "traceback")[:12]:
                f.write("{} KiB, +{} blocks\n".format(st.size_diff // 1024, st.count_diff))
                for line in st.traceback.format()[-12:]:
                    f.write("    " + line + "\n")
        tracemalloc.stop()
    for rt in rts.values():
        rt.enable_communication = False
    for _ in range(60):
        await app.next_update_async()
    await asyncio.sleep(2)
    idle = sorted(t.name for t in threading.enumerate() if t.name.endswith("-plc") and t.is_alive())
    # Disabled runtimes keep an idle worker by design; closing the stage removes
    # the components, and that must end every worker.
    await ctx.new_stage_async()
    for _ in range(30):
        await app.next_update_async()
    await asyncio.sleep(3)
    workers = sorted(t.name for t in threading.enumerate() if t.name.endswith("-plc") and t.is_alive())
    log({"idle_workers_while_disabled": idle, "components_after_new_stage": system.get_component_names()})
    log({"t": round(time.time() - t0, 1), "end": True, "rss_mb": rss_mb(), "threads": threading.active_count(),
         "workers_after_disable": workers, "samples": dict(counts), "events": events[seen_events:]})
    for r in removers:
        r()
    print("SOAK DONE samples={} workers_after_disable={}".format(counts, workers), flush=True)


async def run():
    try:
        await main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        log({"exception": repr(e)})
        print("SOAK FAIL {!r}".format(e), flush=True)
    finally:
        app.post_quit()
        quit_after(20)


asyncio.ensure_future(run())
