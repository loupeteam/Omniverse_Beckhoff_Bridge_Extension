# Changelog

## [0.3.0] - Unreleased
See MIGRATION.md for upgrading from 0.2.x. A 0.2.x stage and script keep working, with deprecation warnings.

Architecture
- The extension is now a driver for the framework extension `loupe.simulation.bridge` (Omni-Utils), which it depends on (`0.3.x`). The framework owns the `/PLC` prims, the runtimes, the message bus, the USD mirror and the window (`Loupe / PLC Bridge`). This extension registers `beckhoff_bridge.AdsDriver` with it as driver `beckhoff`, with one option, `AmsNetId`; the window's Beckhoff fields come from that option schema.
- The ADS driver is the plain-Python `beckhoff_bridge` package at the repo root, with no Omniverse dependency and its own pytest suite. It implements the `plc_bridge.PlcDriver` contract and opens one ADS connection per PLC. `CommunicationDriver` is an alias of `AdsDriver` there.
- The `loupe/simulation/common` submodule is gone; nothing is vendored any more.

Prims and bus
- Neutral prim attributes: `bridge:driver = "beckhoff"`, `bridge:Enable`, `bridge:RefreshRate`, `bridge:Variables` (`string[]`), `bridge:MirrorToUsd`, `beckhoff:AmsNetId`. 0.2.x prims with `beckhoff_bridge:*` attributes are still read, with a warning once per prim.
- Neutral bus names `loupe.simulation.bridge.<KIND>.<plc>`; `STATUS` carries `{"kind", "text", "symbols"}`. The 0.2.x names `loupe.simulation.beckhoff_bridge.*` are still pushed and accepted, with the 0.2.x payloads, while the framework setting `legacyBusNames` is on (the 0.3 default).

Behaviour (from the shared `plc_bridge` runtime)
- One worker thread per PLC: each scan flushes queued writes, then reads, so the sample after a write reflects it; a queued write wakes the loop.
- Besides the bus: `on_sample_main` (newest sample on the main thread once per frame), `on_sample` and `latest()` (a `Sample` with sequence number, time, flat values, per-symbol errors), structured problems, and write acknowledgement (`queue_write` returns a handle).
- A read problem is reported once when it changes and `Reading OK` once when it clears, instead of on every scan. A symbol the PLC rejects is reported as `Error Reading: <symbol>: <reason>`, never delivered as a value; a write it rejects as `Error Writing: <symbol>: <reason>`.
- ADS requests time out after 1 s instead of 5 s, so a PLC that goes away no longer stalls a stage close; a transport-class ADS error marks the link lost, and the bridge reports `Disconnected` and reconnects by itself.
- Setting the AMS Net Id to the value it already has no longer drops the connection.
- A symbol the PLC does not know (ADS 1808) no longer fails the whole sum read or write: it is reported as `Error Reading: <symbol>: symbol not found` (or rejected on write) and the other symbols keep flowing. Unknown names are looked up again every 10 s and after a reconnect.
- On startup the extension logs an error when the installed `beckhoff-bridge` is not the version it pins (Kit's pip installer checks imports, never versions), naming the stale pip folder to delete.

Deprecated (import with a `DeprecationWarning`, also logged; still present in 0.4, removed in 0.5)
- `loupe.simulation.beckhoff_bridge.BeckhoffBridge`: re-exports `Manager`, `get_system`, `get_stream_name` and the `EVENT_TYPE_*` constants from the framework, its `Manager` on the 0.2.x bus names. Import from `loupe.simulation.bridge`.
- `loupe.simulation.beckhoff_bridge.Communication`: re-exports `CommunicationDriver` and `AdsReadError`. Import from `beckhoff_bridge`.
- `loupe.simulation.beckhoff_bridge.global_variables`: the 0.2.x attribute name constants.

Removed
- `Manager()` with no name (deprecated in 0.2.0): it raises `ValueError`.
- The modules `Runtime` and `ui_builder`; the framework provides both.

Packaging and tools
- Pip requirements `pyads` and `beckhoff-bridge` (`>=0.3.0,<0.4`), installed by Kit's pipapi; `plc-bridge` comes with the framework, which owns its pin. Until the packages are on PyPI, `tools/build_wheels.py` bundles the wheels in the extension's `wheels/` folder, and `tools/dev_link.py` installs the checkouts into Kit's Python for a git clone. Both take the `plc_bridge` checkout with `--plc-bridge`. `beckhoff-bridge` 0.3.0 is built by CI.
- `tools/kit_check/` runs the extension and the framework headless and checks a 0.2.x prim, a 0.3 prim and an unchanged 0.2.x script side by side, live or with injected data. `tools/kit_test.ps1` runs the extension's Kit tests.

## [0.2.1]
- Fix a false `Manager('PLC1'): no PLC prim ... is loaded` warning logged on every stage open. The System built the mirror's `Manager` before registering the component it was creating.

## [0.2.0]
See MIGRATION.md for upgrading from 0.1.x.
- Support multiple PLCs. Each PLC is a prim under `/PLC/` carrying `beckhoff_bridge:*` attributes, so connection settings are saved in the stage instead of in persistent app settings.
- Mirror the values read from the PLC into the stage as prims in the session layer, with `write:*` attributes for writing back. Array elements are mirrored as `_<index>` child prims.
- Create the runtimes at extension startup and on stage open/close, so the bridge works without opening the window (headless).
- Cycle time reduced from (3 + write) ADS calls per scan to 1, and jitter reduced from 8-20 ms to about 1 ms.
- Worker threads are daemons with a bounded join, so a runtime can no longer keep the app from exiting.
- Declare the `omni.timeline`, `omni.usd` and `omni.kit.menu.utils` dependencies; drop the unused `omni.physx` dependency.
- Fix read errors other than `pyads.ADSError` being masked by an `AttributeError` in the handler.
- Fix options that could not be set to `False`/`0`.
- `BeckhoffBridge.Manager` now addresses one PLC by the name of its prim under `/PLC/` (`Manager("PLC1")`). A warning is logged when a `Manager` is created for a PLC that is not loaded.
- **Deprecated:** calling `Manager()` with no name (the 0.1.x form). It still works: it addresses `PLC1` and, if no `/PLC/PLC1` prim is loaded, creates that runtime in memory from the 0.1.x persistent settings (`PLC_AMS_NET_ID`, `REFRESH_RATE`, `ENABLE_COMMUNICATION`) with a warning. Nothing is written to the stage file, and the runtime is gone when the stage closes until the next `Manager()` call. Add a `/PLC/PLC1` prim to make it permanent. This path will be removed in 0.3.0.
- Close both ADS connections on disconnect; previously the write connection leaked on every reconnect.
- A symbol whose ADS read fails is no longer delivered as data (pyads returns the error text as the value); it is reported in the status as `Error Reading: <symbol>: <reason>` once, and `Reading OK` when it recovers. The USD mirror retries a symbol it had given up on and recovers by itself.
- Shared runtime, system and USD code moved to the `loupe/simulation/common` submodule (loupeteam/Omni-Utils).

## [0.1.0]
- Created with based functionality to setup a connection and send/receive messages with other extensions.
