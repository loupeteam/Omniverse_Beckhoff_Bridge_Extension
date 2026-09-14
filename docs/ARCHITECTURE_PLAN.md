# Architecture plan: vendor-neutral PLC bridge

Status: **proposal, not scheduled.** Written 2026-09-11 after the 0.2.1 release.
Nothing here is implemented. It records the direction agreed in discussion so the
later refactor starts from a shared picture.

## Goal

Loupe builds simulations that must run against different PLC vendors. The same
machine gets tested on Beckhoff hardware one week and B&R the next. A simulation
should not change when the hardware does. Only the communication layer should.

## Where 0.2.x falls short

- The shared code (system, `Manager` API, UI, USD mirror) lives in the
  `loupeteam/Omni-Utils` repo and is vendored into each vendor extension as a git
  submodule pinned to a feature branch. Every shared fix is two PRs and a pin bump.
- Each vendor extension loads its own copy of that shared code. A stage that uses
  two vendors runs two systems and two UIs scanning the same `/PLC` prims.
- Vendor code and Omniverse code are mixed. The ADS driver cannot be tested or
  used outside Kit, and the shared code cannot be reused without Kit.
- The USD value mirror is built for every PLC by the core runtime, so its cost
  and its bugs land on every user, including those who only use the Python API.

## Target layering

Four pieces, from the bottom up.

### 1. Libraries (plain Python)

No `omni` or `carb` imports anywhere in this layer; installable with pip.

**`plc_bridge`, the shared contract.** Vendor-neutral. Holds:

- The abstract driver interface every vendor implements: `connect`,
  `disconnect`, `read(symbols) -> dict`, `write(symbol, value)`, and per-symbol
  errors reported as data, never as a value.
- The polling runtime that is already vendor-agnostic: read and write threads,
  refresh rate, variable list, callbacks. This is today's `RuntimeBase` with the
  carb bus publish replaced by a plain callback.

The contract lives here, below Kit, so that two vendor libraries can be swapped
without the framework extension present.

**`beckhoff_bridge`.** The pyads driver. Today's `Communication.py` and
`Runtime.py` already meet the no-Kit bar.

**`br_bridge`.** The B&R driver. Not a library yet; written to the contract from
the start.

Library-level swap, no Kit involved:

```python
from plc_bridge import PlcRuntime
from beckhoff_bridge import AdsDriver      # or: from br_bridge import BrDriver

plc = PlcRuntime(AdsDriver("10.20.30.40.1.1"), refresh_ms=20)
plc.set_read_variables(["GVL.Axes[0].ActualPosition"])
plc.on_data(lambda data: ...)
plc.start()
```

Only the driver import and its constructor arguments change.

### 2. Bridge framework (Kit extension)

Omni-Utils promoted from a submodule to a real extension, for example
`loupe.simulation.bridge`. Loaded once regardless of how many vendors are
enabled. Owns everything a simulation touches:

- `/PLC/<name>` prim discovery and the option attributes on those prims.
- The `Manager` API and the carb message bus event names.
- Polling threads and main-thread delivery.
- The UI window.
- The driver registry: vendor extensions register a driver class under a name.
- The USD value mirror, as an optional component (see below).

Depends on `plc_bridge` and adds the Kit parts on top. Has no vendor code and
no pyads dependency.

### 3. Vendor extensions (thin Kit extensions)

`loupe.simulation.beckhoff_bridge` keeps its name so existing apps still enable
it. It shrinks to: a pip requirement on its library, a dependency on the
framework extension, and an `on_startup` that registers the driver. Same for B&R.

### 4. Simulations

Depend on the framework extension only. Declare PLCs as prims. Consume data via
`Manager` callbacks or the mirror attributes. Never import vendor code.

## The USD mirror

Split out of the core into an opt-in component of the framework (or a separate
extension). It subscribes to the same bus events any user would, so its output
is unchanged. Plan:

1. First framework release: mirror present, default **on**, changelog note.
2. Following release: default **off**, enabled per PLC prim with the existing
   `bridge:MirrorToUsd` attribute.
3. Consider mirroring a chosen watch list of symbols instead of every symbol read.

Rationale: nothing inside the extension consumes the mirror; the UI, harness and
`Manager` API all use the bus. Most 0.2.x bugs lived in the mirror path.

## Repository layout

Framework repo (today's Omni-Utils):

```
exts/loupe.simulation.bridge/        # framework extension, released and versioned
```

Framework repo also hosts the shared library:

```
plc_bridge/                          # shared contract + runtime, pyproject.toml, pytest
```

Vendor repo (this one):

```
beckhoff_bridge/                     # library, pyproject.toml, pytest tests, pyads + plc_bridge
exts/loupe.simulation.beckhoff_bridge/   # thin vendor extension
```

Vendor extensions depend on the framework with a version range in
`extension.toml`, the normal Kit mechanism. No submodule.

## Backward compatibility

Kept as is:

- Extension name `loupe.simulation.beckhoff_bridge`.
- `/PLC/<name>` prims and their attributes.
- `Manager("PLC1")`, callbacks, `write_variable`, bus event names.
- Mirror prim and attribute layout, while the mirror is enabled.

Planned breaks:

- `Manager()` with no name: deprecated in 0.2.0, removed in 0.3.0 as already
  announced.
- Mirror default off, one release after the split.
- Code that imported `loupe.simulation.common` internals directly has to import
  from the framework instead. Never documented as public, but this is a public
  repo, so call it out in the migration guide.

## Swapping vendors under this plan

1. Enable the other vendor's extension in the app (or both).
2. On the PLC prim, change the driver attribute from `beckhoff` to `br` and set
   that vendor's connection attributes.
3. Reopen the stage.

The simulation code, the `Manager` calls, the bus subscriptions and the mirror
paths are untouched. Symbol names are the one thing that may differ between
vendors; that is a property of the PLC programs, not of the bridge.

## Open questions

- Exact driver interface in `plc_bridge`: sync vs. async reads, batch size, how
  struct and array symbols are described so the runtime can flatten them the
  same way for every vendor. ADS and the B&R protocol answer these differently;
  settle this first, before either library is written to it.
- Whether the framework extension should also carry the vendor-neutral parts of
  the UI (connection status, variable list) and let vendors add a settings panel.
- Whether vendor libraries publish to PyPI or stay in-repo and are added to the
  Python path by the vendor extension manifest. In-repo is simpler to start.
- Where the 0.1.x legacy shim (`Manager()` without a name) dies: it should not
  survive into the framework.

## Related

- `docs/MIGRATION.md` in the extension: 0.1.x to 0.2.x changes.
- Omni-Utils issues and PRs from the 0.2.x work describe the mirror constraints
  (session layer, `_<index>` array prims, `write:*` declared without a value).
