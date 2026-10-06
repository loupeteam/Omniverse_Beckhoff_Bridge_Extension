# Implementation plan: 0.3.0 across the three repos

Status: **for review.** Written 2026-10-06. Companion to
[ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md), which holds the design and the
decisions; this file holds the work, in phases, each scoped so that one
sub-agent can take it with this document and the repos alone.

Repos:

| Short name | Repo | Role after 0.3.0 |
|---|---|---|
| **BK** | `loupeteam/Omniverse_Beckhoff_Bridge_Extension` | `beckhoff_bridge` library + thin Beckhoff Kit extension |
| **BR** | `loupeteam/Omniverse_BnR_Bridge_Extension` | `br_bridge` library + thin B&R Kit extension |
| **OU** | `loupeteam/Omni-Utils` | `plc_bridge` library + the framework Kit extension `loupe.simulation.bridge` |

Branches: every repo has an `rc/0.3.0` branch. Phase work goes in a branch
per phase, PR into `rc/0.3.0`, review there; `rc/0.3.0` to `main` only on
Scott's call. Nothing below merges to `main`.

Where things stand (2026-10-06):

| Done, on branches | PR |
|---|---|
| `beckhoff_bridge` library; BK extension `Runtime` adapter over `PlcRuntime` | BK #19 → rc |
| `plc_bridge` contract and runtime, nine review rounds | OU #10 → rc |
| contract v2: one worker, `Sample`, `latest()`, `Problem`, write handles | OU #11 (stacked on #10) |
| `AdsDriver` on v2, one connection | BK #20 (stacked on #19) |
| `br_bridge` library, mock OMJSON tests | BR #15 → main |

Rules for every phase:

- Plain-Python packages import nothing from `omni` or `carb`. A test in each
  package asserts it.
- Every PR has: tests that run under plain `pytest` where the code is plain
  Python; a headless Kit harness run (`tools/kit_check/`) where Kit code
  changed; a changelog entry; the migration guide updated if anything a user
  touches changed.
- Vendor-named surfaces (`beckhoff_bridge:*` attributes, bus names, imports
  from the vendor module) keep working through 0.3.x with a deprecation
  warning; neutral names are the documented ones. See decision 2 in the
  architecture plan.
- No sub-agent merges, retargets, or creates branches on GitHub; it pushes a
  branch and opens a draft PR with the verification it ran in the
  description.

---

## Phase 0: unblock (Scott, half a day)

Nothing a sub-agent can do; everything later waits on it.

| # | Task | Who |
|---|---|---|
| 0.1 | Create `rc/0.3.0` in BK (from `main`), OU (from `feature/usd-operations`), BR (from `main`). Retarget BK #19 and OU #10 at them and merge. Retarget BK #20 and OU #11 at `rc/0.3.0`; retarget BR #15 at `rc/0.3.0`. | Scott |
| 0.2 | Renew the TwinCAT trial licence on the Moonlight machine (XAE: System, License), redeploy the Moonlight project (`python make.py download`), confirm with `python tools/plc_probe.py`. | Scott |
| 0.3 | Decide where `plc_bridge` lives long term: stay in OU, or its own repo `loupeteam/plc-bridge`. The plan below assumes **stays in OU** (fewest moving parts; revisit when a third consumer appears). | Scott |
| 0.4 | PyPI: create the `loupe` org or account and give the CI a publishing token for `plc-bridge`, `beckhoff-bridge`, `br-bridge`. Until then, Phase 1 bundles wheels instead. | Scott |

Acceptance: three `rc/0.3.0` branches exist with #10, #19 merged; a live
Moonlight read works (`plc_probe.py` resolves 9 symbols).

---

## Phase 1: libraries stand on their own (OU, BK, BR; one sub-agent, 1 to 2 days)

Goal: `pip install plc-bridge beckhoff-bridge br-bridge` works, with or
without PyPI, and the Kit extensions stop reaching outside their folders.

| # | Repo | Task |
|---|---|---|
| 1.1 | OU | Move `plc_bridge/` to the repo root (it sits under the submodule-visible tree today, which is the same place; just confirm) and add a GitHub Actions workflow: pytest on 3.10 and 3.12, build a wheel, upload it as an artifact; publish to PyPI on a tag `plc-bridge-v*` when the token exists. |
| 1.2 | BK, BR | Same workflow for `beckhoff_bridge/` and `br_bridge/`. Their `pyproject.toml` pin `plc-bridge>=0.3,<0.4`. |
| 1.3 | BK | Replace the two `[[python.module]] path = ...` entries in `exts/loupe.simulation.beckhoff_bridge/config/extension.toml` with pip requirements (`pyads`, `plc-bridge`, `beckhoff-bridge`). Until PyPI exists, point `[python.pipapi] archiveDirs` at a `wheels/` folder inside the extension that a `tools/build_wheels.py` script fills from the local checkouts. |
| 1.4 | BK | `tools/dev_link.py`: for a git clone, install the local library checkouts editable into Kit's Python (`kit/python/python.exe -m pip install -e ...`), so a developer runs from source without a wheel build. Document both paths in the root README. Verify first what Kit's pipapi does when a requirement is already importable; record the answer in the README. |
| 1.5 | BK | Move the headless harness into the repo: `tools/kit_check/{kit_check.py, run.sh, run.ps1, fixcheck.kit.template, stages/mirror_test.usda}`. The template takes the ext folder and the Moonlight build path from environment variables. The current script lives in the session scratchpad (`kit_fix_check.py` v3); copy it, do not rewrite it. |
| 1.6 | OU | Version bump `plc-bridge` to `0.3.0rc1`; `beckhoff-bridge`, `br-bridge` to `0.3.0rc1`. |

Acceptance:

- `pip install ./plc_bridge ./beckhoff_bridge ./br_bridge` in a clean venv, then
  `pytest` in each: all green (102 / 45 / 11 as of today).
- The BK extension starts in Kit from a clean clone after `tools/dev_link.py`,
  and from the registry layout (wheels bundled) without it. The harness
  passes in inject mode and live.
- `git grep "path = \"../../"` in BK and BR returns nothing.

Sub-agent brief: "Make the three libraries installable on their own and the
Beckhoff extension load them as pip requirements; move the harness into
`tools/kit_check`. Phase 1 of docs/IMPLEMENTATION_PLAN.md."

---

## Phase 2: B&R extension on the shared runtime (BR; one sub-agent, 1 to 2 days)

Goal: the B&R Kit extension does what the Beckhoff one does today: `/PLC`
prims, a `Runtime` adapter over `PlcRuntime(BrDriver)`, the bus for
compatibility, verified against ARsim.

| # | Task |
|---|---|
| 2.1 | Add the OU submodule at `exts/loupe.simulation.br_bridge/loupe/simulation/common` pinned to `rc/0.3.0`, the way BK has it today (temporary: Phase 4 removes both submodules). |
| 2.2 | `Runtime.py` adapter copied from BK and reduced to the B&R options: `br_bridge:Host`, `br_bridge:Port`, `br_bridge:Enable`, `br_bridge:RefreshRate`, `br_bridge:Variables`. `global_variables.py` defines them. `extension.py` creates the `System("/PLC/", defaults, Runtime, Manager)` on startup and follows stage open/close, as BK's does. |
| 2.3 | `BrBridge.py`: `Manager(name)` and `get_system()` with the same shape as BK's `BeckhoffBridge.py`, bus names `loupe.simulation.br_bridge.<KIND>.<plc>`. Keep the no-name `Manager()` form working with a deprecation warning, as BK does, since 0.1.0 users have it. |
| 2.4 | Delete `websockets_driver.py` and its Kit tests; the parser tests become `br_bridge/tests/test_symbols_legacy.py` against `plc_bridge.nest_symbol` with separators `":."` (same move BK made). |
| 2.5 | UI: `ui_builder.py` fields for host, port, enable, refresh, variables, on `SystemUI`. |
| 2.6 | Live test against ARsim: an Automation Studio project with `jsonWebSocketServer` exists under `test/AS Project`; bring it up in ARsim (the `bnr-build` skill knows how), run the harness (`tools/kit_check` copied from BK, stage with a `/PLC/PLC1` prim pointing at `127.0.0.1:8000`). |
| 2.7 | Changelog, README, migration note from 0.1.0 (prim config instead of persistent settings; same story as BK's `MIGRATION.md`). Version `0.3.0rc1`. |

Acceptance: harness live against ARsim reads at the refresh rate, mirror and
write-back pass, `Manager()` without a name still works with a warning;
`pytest` in `br_bridge` green.

Sub-agent brief: "Port the B&R Kit extension onto `plc_bridge.PlcRuntime` and
`br_bridge.BrDriver`, mirroring the Beckhoff extension's structure. Phase 2
of docs/IMPLEMENTATION_PLAN.md in the Beckhoff repo."

---

## Phase 3: the framework extension (OU; one sub-agent, 3 to 5 days)

Goal: one Kit extension, `loupe.simulation.bridge`, owns everything a
simulation touches, with vendor code behind a registry. This is the step the
architecture review asked to design against two drivers, which Phases 1 and 2
provide.

| # | Task |
|---|---|
| 3.1 | New extension `exts/loupe.simulation.bridge/` in OU. `extension.toml`: depends on `omni.usd`, `omni.kit.menu.utils`, `omni.timeline`; pip requirement `plc-bridge==<exact>`. Move `System.py`, `SystemUI.py`, `UsdManager.py`, `BridgeManager.py` under `loupe/simulation/bridge/`. `RuntimeBase.py` is not moved; it dies with the submodules in Phase 4. |
| 3.2 | **Driver registry.** `registry.register(name, driver_class, option_schema, defaults, ui_panel=None)`; `registry.get(name)`. Option schema: list of `Option(key, kind, default, label, secret=False)` with kinds `str`, `int`, `float`, `bool`, `str_list`. A `secret` option is never written to a prim: its prim value is a reference (`env:NAME` or `setting:/path`) that the framework resolves. |
| 3.3 | **Neutral prim schema.** `bridge:driver` (string), `bridge:Enable`, `bridge:RefreshRate`, `bridge:Variables` (`string[]`), `bridge:MirrorToUsd`, plus the driver's options under its namespace (`beckhoff:AmsNetId`, `br:Host`, `br:Port`). A PLC prim is recognised by `bridge:driver` present. Legacy rule: a prim with `beckhoff_bridge:AmsNetId` and no `bridge:driver` is treated as `driver = "beckhoff"` with its legacy attributes read, and a deprecation warning once per prim. Same for `br_bridge:*`. `/PLC/<name>` stays the documented convention; prim path is the identity. |
| 3.4 | **Component runtime.** `Component` = `PlcRuntime(driver, name, options)` + the Kit glue: options in/out of the prim, `cleanup()`. The framework's `Runtime` adapter replaces the vendor ones. |
| 3.5 | **Delivery.** `get_plc(name) -> PlcRuntime` and `get_system()` move here. New `on_sample_main(name, cb)`: subscribes to `on_sample`, keeps the newest, delivers once per `omni.kit.app` update on the main thread. Document that it drops intermediate samples and that `Sample.seq` detects gaps. |
| 3.6 | **Bus as a listener.** `BusAdapter(plc, namespaces)` subscribes to the runtime events and pushes `loupe.simulation.bridge.<KIND>.<plc>`; with a setting `/exts/loupe.simulation.bridge/legacyBusNames` (default true in 0.3) it also pushes the vendor name (`loupe.simulation.beckhoff_bridge.*` or `..br_bridge.*`) and accepts requests on both. The structured `Problem` goes on the bus as `{"kind", "text", "symbols"}` under `STATUS`, with the text as the 0.2.x payload for the legacy name. |
| 3.7 | **Mirror as a component.** `UsdManager.RuntimeUsd` becomes a registered component created when `bridge:MirrorToUsd` is true (default **true** in 0.3), reading `Sample` via `on_sample_main` instead of the bus, with an optional `bridge:MirrorSymbols` (`string[]`) watch list; empty means all. It uses `Sample.values` (flat) directly; `flatten_obj` goes away. |
| 3.8 | **Safety setting.** `/exts/loupe.simulation.bridge/autoConnect` (default true). When false, prims with `bridge:Enable = true` are created disabled and the UI shows why. |
| 3.9 | **UI.** `SystemUI` carries the vendor-neutral panel (component list, enable, refresh, variables, status, connection); a driver's `ui_panel` callback adds its options below. |
| 3.10 | Tests: Kit tests for prim discovery (neutral and legacy), registry, `on_sample_main` coalescing, bus adapter emitting both names, mirror watch list. Harness run with a `bridge:driver = "beckhoff"` prim and with a legacy `beckhoff_bridge:*` prim. |
| 3.11 | OU `README.md`, `CHANGELOG.md` for the extension, and a `docs/CONSUMING.md`: callbacks vs `latest()` vs `on_sample_main` vs bus, with the thread rules. |

Acceptance: a stage with one legacy Beckhoff prim and one neutral B&R prim
opens with both PLCs running under one `System`; a 0.2.x script using
`Manager("PLC1")` on the legacy bus name still receives data; `on_sample_main`
delivers on the main thread at the frame rate; harness live passes.

Sub-agent brief: "Build `loupe.simulation.bridge` in Omni-Utils per Phase 3 of
docs/IMPLEMENTATION_PLAN.md in the Beckhoff repo, registering the Beckhoff and
B&R drivers from their libraries for the tests."

---

## Phase 4: vendor extensions become thin; submodules go (BK, BR; one sub-agent each, 1 day each)

| # | Repo | Task |
|---|---|---|
| 4.1 | BK | `extension.toml`: depend on `loupe.simulation.bridge` (version range `[0.3, 0.4)`), pip `pyads`, `beckhoff-bridge`. `extension.py` registers `AdsDriver` with the option schema (`AmsNetId` string) and an optional UI panel. Delete `Runtime.py`, `System`/UI usage, `Communication.py`, `ui_builder.py`. |
| 4.2 | BK | `BeckhoffBridge.py` stays as a **compatibility module**: `Manager`, `get_system`, the event-name constants, re-exported from the framework with a deprecation warning at import. `Manager()` no-name shim removed (announced for 0.3.0). |
| 4.3 | BK | Remove the submodule `loupe/simulation/common` and `.gitmodules`. Root README licence list updated. |
| 4.4 | BR | Same three steps for the B&R extension against `BrDriver`. |
| 4.5 | BK, BR | `docs/MIGRATION.md`: 0.2.x to 0.3.0 for BK (neutral names, how to opt out of the mirror, what the deprecation warnings mean and when they turn into errors); 0.1.0 to 0.3.0 for BR. |
| 4.6 | BK, BR | Harness run (BK live against TwinCAT, BR live against ARsim), both legacy and neutral prims. |

Acceptance: each vendor extension is under 200 lines of Python; no
`loupe/simulation/common` folder in either repo; a 0.2.x BK stage and script
run unchanged with warnings; the Moonlight sandbox runs against the three
extensions from `rc/0.3.0`.

---

## Phase 5: release candidate (all; Scott plus one sub-agent, 1 day)

| # | Task |
|---|---|
| 5.1 | Version `0.3.0` everywhere; changelogs consolidated; `ARCHITECTURE_PLAN.md` status table updated. |
| 5.2 | Verification matrix, recorded in `docs/RELEASE_0.3.0.md`: pytest for three libraries; Kit harness for BK live, BR live, mixed stage, legacy stage; a Moonlight soak of 30 minutes with the PLC dropped and restored once (reconnect, no zombie threads, memory flat). |
| 5.3 | Architecture review by a sub-agent on `rc/0.3.0` of all three repos against `ARCHITECTURE_PLAN.md`; findings fixed on rc. |
| 5.4 | Scott: merge `rc/0.3.0` to `main` in OU, then BK, then BR; tag `v0.3.0`; GitHub releases with the migration guide linked; publish wheels. |

Deferred to 0.4: mirror default off; `legacyBusNames` default off; OmniGraph
read/write nodes if a project asks for no-code access; `describe()` for type
info; push subscriptions.

---

## Dependencies between phases

```
Phase 0 ─┬─> Phase 1 ─┬─> Phase 3 ─> Phase 4 (BK) ─┐
         │            │                            ├─> Phase 5
         └─> Phase 2 ─┘            Phase 4 (BR) ───┘
```

Phase 1 and Phase 2 can run in parallel once Phase 0 is done. Phase 3 needs
both (it registers both drivers). Phase 4 BK and BR can run in parallel.

## Open items the phases do not decide

- Whether `plc_bridge` moves to its own repo (0.3; assumed no).
- Whether any customer outside Loupe depends on the vendor-named surfaces,
  which would extend the deprecation period past 0.4.
- Whether the mirror survives 0.4 or OmniGraph nodes replace it.
