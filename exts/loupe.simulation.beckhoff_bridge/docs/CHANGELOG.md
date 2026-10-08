Changelog

[Unreleased]
See MIGRATION.md for upgrading from 0.2.x. A 0.2.x stage and script keep working, with deprecation warnings.
- The extension is now a driver for the framework extension `loupe.simulation.bridge` (Omni-Utils), which it depends on (`0.3.x`). The framework owns the `/PLC` prims, the runtimes, the message bus, the USD mirror and the window (`Loupe / PLC Bridge`); this extension registers `beckhoff_bridge.AdsDriver` with it as driver `beckhoff`, with one option, `AmsNetId`. The window's per-driver fields come from that option schema.
- Neutral prim attributes: `bridge:driver = "beckhoff"`, `bridge:Enable`, `bridge:RefreshRate`, `bridge:Variables` (`string[]`), `beckhoff:AmsNetId`. 0.2.x prims with `beckhoff_bridge:*` attributes are still read, with a warning once per prim.
- Neutral bus names `loupe.simulation.bridge.<KIND>.<plc>`. The 0.2.x names `loupe.simulation.beckhoff_bridge.*` are still pushed and accepted while the framework setting `legacyBusNames` is on (the 0.3 default).
- **Deprecated:** `loupe.simulation.beckhoff_bridge.BeckhoffBridge`. It re-exports `Manager`, `get_system`, `get_stream_name` and the `EVENT_TYPE_*` constants from the framework, with its `Manager` on the 0.2.x bus names, and raises a `DeprecationWarning` (also logged) on import. Off by default in 0.4, removed in 0.5. Import from `loupe.simulation.bridge` instead.
- **Removed:** `Manager()` with no name (deprecated in 0.2.0): it raises `ValueError`. The modules `Runtime`, `Communication`, `ui_builder` and `global_variables`, and the `loupe/simulation/common` submodule; nothing is vendored any more.
- Packaging: the pip requirements are `pyads` and `beckhoff-bridge`; `plc-bridge` comes from the framework, which owns its pin. `tools/build_wheels.py` and `tools/dev_link.py` take the `plc_bridge` checkout with `--plc-bridge` (an Omni-Utils clone). `tools/kit_check` loads the framework from an Omni-Utils `exts/` folder (`--framework`) and checks a 0.2.x prim, a 0.3 prim and an unchanged 0.2.x script side by side; `tools/kit_test.ps1` runs the extension's Kit tests.
- The ADS driver moved out of the extension into the plain-Python `beckhoff_bridge` package at the repo root (`beckhoff_bridge/`), with no Omniverse dependency and its own pytest suite. The extension loads it from there. `loupe.simulation.beckhoff_bridge.Communication` still re-exports `CommunicationDriver` (now an alias of `beckhoff_bridge.AdsDriver`) and `AdsReadError`. First step of `docs/ARCHITECTURE_PLAN.md`.
- The polling (threads, connect and retry, read list, write queue, status reporting) moved into the vendor-neutral, plain-Python `plc_bridge.PlcRuntime` in the Omni-Utils submodule, and `AdsDriver` implements its `PlcDriver` contract. The extension's `Runtime` is now an adapter between that runtime and the message bus. Bus event names, message format and status texts are unchanged, with these exceptions: a read problem (a failed read, a rejected symbol, a name that cannot be represented) is reported once when it changes and `Reading OK` once when it clears, instead of on every scan; a read where every symbol fails is one status, `Error Reading: all N symbol(s) failed: <symbol>: <reason>; ...`; an ADS "symbol not found" for a whole read is one status naming the symbols instead of two; a write the PLC rejects per symbol is reported as `Error Writing: <symbol>: <reason>`.
- One worker thread per PLC instead of a read thread and a write thread: each scan flushes the queued writes and then reads, so the sample after a write reflects it, and a queued write wakes the loop. `Runtime.write_sleep_time` is accepted and ignored. The ADS driver opens one connection instead of two.
- The runtime also offers `on_sample` (a `Sample` with a sequence number, time, flat values and per-symbol errors), `latest()` for consumers that pull once per tick, `on_problem` (structured problems; `on_status` still gets the text) and write acknowledgement (`queue_write` returns a handle; `on_write` gets a result per batch). The message bus API is unchanged.
- ADS requests time out after 1 s instead of pyads' 5 s default, so a PLC that goes away no longer stalls a stage close; a transport-class ADS error (target not found, timeout, port disabled) marks the link lost and the bridge reports `Disconnected` and reconnects by itself.
- Setting the AMS Net Id to the value it already has no longer drops the connection.
- `Runtime` no longer derives from `Runtime_Base`. It gained `read_variables`, `is_connected`, `plc` and `driver`; its private `_ads_connector` is gone.
- Packaging: the extension no longer loads `plc_bridge` and `beckhoff_bridge` through relative `[[python.module]]` paths. They are pip requirements (`pyads`, `plc-bridge>=0.3.0rc1,<0.4`, `beckhoff-bridge>=0.3.0rc1,<0.4`) that Kit installs before the extension starts. Until the packages are on PyPI, `tools/build_wheels.py` bundles their wheels in the extension's `wheels/` folder; a git clone runs `tools/dev_link.py` to use the checkouts directly. The root README records what Kit's pipapi does in each case. The headless check harness lives in `tools/kit_check/` with `run.sh` and `run.ps1` launchers. `beckhoff-bridge` is versioned `0.3.0rc1` and built by CI.

[0.2.1]
- Fix a false `Manager('PLC1'): no PLC prim ... is loaded` warning logged on every stage open. The System built the mirror's `Manager` before registering the component it was creating.

[0.2.0]
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

[0.1.0]
- Created with based functionality to setup a connection and send/receive messages with other extensions.
