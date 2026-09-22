Changelog

[Unreleased]
- The ADS driver moved out of the extension into the plain-Python `beckhoff_bridge` package at the repo root (`beckhoff_bridge/`), with no Omniverse dependency and its own pytest suite. The extension loads it from there. `loupe.simulation.beckhoff_bridge.Communication` still re-exports `CommunicationDriver` (now an alias of `beckhoff_bridge.AdsDriver`) and `AdsReadError`. First step of `docs/ARCHITECTURE_PLAN.md`.
- The polling (threads, connect and retry, read list, write queue, status reporting) moved into the vendor-neutral, plain-Python `plc_bridge.PlcRuntime` in the Omni-Utils submodule, and `AdsDriver` implements its `PlcDriver` contract. The extension's `Runtime` is now an adapter between that runtime and the message bus. Bus event names, message format and status texts are unchanged, with these exceptions: a read problem (a failed read, a rejected symbol, a name that cannot be represented) is reported once when it changes and `Reading OK` once when it clears, instead of on every scan; a read where every symbol fails is one status, `Error Reading: all N symbol(s) failed: <symbol>: <reason>; ...`; an ADS "symbol not found" for a whole read is one status naming the symbols instead of two; a write the PLC rejects per symbol is reported as `Error Writing: <symbol>: <reason>`.
- ADS requests time out after 1 s instead of pyads' 5 s default, so a PLC that goes away no longer stalls a stage close; a transport-class ADS error (target not found, timeout, port disabled) marks the link lost and the bridge reports `Disconnected` and reconnects by itself.
- Setting the AMS Net Id to the value it already has no longer drops the connection.
- `Runtime` no longer derives from `Runtime_Base`. It gained `read_variables`, `is_connected`, `plc` and `driver`; its private `_ads_connector` is gone.

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
