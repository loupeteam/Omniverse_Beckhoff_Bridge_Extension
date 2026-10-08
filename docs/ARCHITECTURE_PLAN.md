# Architecture plan: vendor-neutral PLC bridge

Status: **in progress on the `rc/0.3.0` branches; nothing merged to `main`.** Written
2026-09-11 after the 0.2.1 release; decisions and review added 2026-10-06; status
updated 2026-10-08. It records the direction
agreed in discussion.

| Piece | State |
|---|---|
| `beckhoff_bridge` library | Merged into `rc/0.3.0` (this repo) |
| `plc_bridge` contract and runtime | Merged into Omni-Utils `rc/0.3.0` |
| Framework extension `loupe.simulation.bridge`, driver registry | Merged into Omni-Utils `rc/0.3.0` (542179c) |
| USD mirror as an opt-in component | Merged with the framework extension (default on in 0.3) |
| B&R driver written to the contract | `br_bridge` merged into the B&R repo's `rc/0.3.0` |
| Thin Beckhoff extension, no submodule | In review: PR #22 into `rc/0.3.0` (Phase 4) |

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

**`beckhoff_bridge`.** The pyads driver, `AdsDriver`, implementing the contract.

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

## Driver interface decisions

Settled 2026-09-21 by reading both existing drivers: the ADS one here and the
B&R one (`websockets_driver.py`, OMJSON over a websocket). They already had the
same shape. The three real differences, and how the contract absorbs them:

| Difference | Decision |
|---|---|
| B&R is `async`, ADS is synchronous | The contract is **synchronous**. The runtime calls it from its own threads; a driver on an async transport owns its event loop. Forcing ADS into `async` would buy nothing. |
| B&R symbols are `Program:struct.member`; its parser copy split on `:` and `.` | The driver declares `symbol_separators`. Drivers return **flat** symbol to value, and the shared runtime does the nesting, so both vendors produce the same data shape from one parser instead of two copies. |
| Only ADS reports per-symbol failures | `ReadResult` has `values` and `errors`. A driver that cannot tell leaves `errors` empty. A failed request raises. |

Also fixed by the contract: the read list belongs to the runtime and is passed
with each `read`; `read` and `write` may be called from two threads at once and
the driver makes that safe (ADS uses two connections; a single websocket would
use a lock).

## Decisions (2026-10-06)

Answers to the three questions the architecture review asked before the next
step.

**1. Who consumes PLC data.** Python callbacks, mostly. Pull per tick is not
ruled out and is the likely optimisation for a slow app: at 15 fps with a 20 ms
PLC period a callback consumer handles three samples per frame for nothing. So:

- `PlcRuntime` keeps worker-thread callbacks (every sample, for anyone who
  needs every packet) and gains `latest()` (the newest sample, for pull).
- The framework extension offers a per-frame, main-thread callback that
  delivers the newest sample once per app update. This is the documented
  default for Kit code. It drops intermediate samples; edge detection on short
  pulses uses the worker callback or the sample's sequence number.
- OmniGraph nodes and the mirror are decided later, once a project needs
  no-code access at all.

**2. Vendor-named surfaces are a one-release alias**, like the `Manager()`
deprecation: bus events `loupe.simulation.beckhoff_bridge.*`, prim attributes
`beckhoff_bridge:*`, and the import of `Manager` / `get_system` from the vendor
module. 0.3 emits and accepts both neutral and vendor names and warns on the
old; 0.4 keeps the old behind a setting, default off; 0.5 removes them. The
neutral names must exist in 0.3 because the B&R driver cannot ship against
`beckhoff_bridge:*` attributes.

**3. Distribution is the public Omniverse registry, and git clone stays
valid.** Loupe may host a registry later, likely for private packages and
betas; nothing depends on it. Consequences:

- The libraries go to PyPI (`plc-bridge`, `beckhoff-bridge`, later
  `br-bridge`) and the extension manifests list them as pip requirements, as
  they list pyads today. The relative `[[python.module]] path` entries are
  development-only and go away.
- The framework extension owns the exact `plc-bridge` pin; vendor extensions
  pin only their own library. Kit installs each extension's pip requirements
  into one site-packages and does not resolve conflicts, so one owner.
- For a git clone, a bootstrap script links the local library sources into the
  extension folder. To verify first: whether Kit's pip installer skips a
  requirement that is already importable, so the dev link and the pip install
  do not fight.

## Architecture review (2026-10-06)

Points accepted from the review, in the order they will be done. The order is
changed from the original plan: the libraries are published and the B&R driver
is written before the framework extension, so the registry API, option schema,
bus namespace and sample type are designed against two vendors, not one.

1. **Publish `plc_bridge`** as its own package (own repo or a library monorepo
   with the vendor drivers), so the B&R library needs no submodule and
   `pip install beckhoff-bridge` works outside Kit.
2. **Write `br_bridge`** to the contract, plain Python, against the existing
   OMJSON websocket driver. Fold what it teaches into the contract while
   nothing pins it:
   - one worker per PLC (write then read each period, wake on `queue_write`)
     instead of separate read and write threads: most of the runtime's
     lifecycle machinery and the two ADS connections exist only for the
     second thread, and a single websocket has to serialise anyway;
   - a sample object (`seq`, monotonic time, flat values, errors) as the
     primary data event, with the nested dict derived from it;
   - a structured problem event instead of prose status, the text derived;
   - write acknowledgement (a handle or a per-symbol write-result event);
   - an optional `describe(symbols)` for type info, used by the mirror when
     present; a seam for push subscriptions, not built;
   - struct reads either as a read-spec in the contract or dropped;
   - "in one call" rather than "in one request": drivers may batch.
3. **Framework extension** (`loupe.simulation.bridge`): driver registry (driver
   class, option schema, defaults, optional settings panel); neutral prim
   schema `bridge:driver`, `bridge:Enable`, `bridge:RefreshRate`,
   `bridge:Variables` (a string array), `bridge:MirrorToUsd`, with vendor
   keys in a vendor namespace (`beckhoff:AmsNetId`, `br:Host`); PLC prims
   identified by a marker, `/PLC/<name>` a convention; neutral bus namespace
   with the bus as one listener among others; `latest()` and the per-frame
   callback; the mirror as a registered component with a watch list; an
   app-level setting so a committed stage with Enable true cannot connect to
   hardware by surprise; a `secret` option kind that references a setting or
   environment variable and is never stored on a prim.
4. **Vendor extensions** shrink to manifest plus driver registration. Mirror
   default flips to off one release later.

Not carried into the framework: `Runtime_Base` (dies when the B&R extension
moves), the no-name `Manager()` shim, main-thread delivery inside `plc_bridge`
(it stays Kit-side).

Kept, per the review: the contract below Kit with no dependencies; errors as
data, never as values; synchronous, bounded, daemon threads with a bounded
`stop()`; flat symbol names as the canonical identity; one parser with
per-driver separators; the session-layer mirror never dirtying the stage;
prim-based multi-PLC config that works headless; the thin adapter exposing the
library object; the lifecycle tests as external guarantees.

## Open questions

- Whether the framework extension should also carry the vendor-neutral parts of
  the UI (connection status, variable list) and let vendors add a settings panel.
- Whether any customer stage or script outside Loupe depends on the vendor-named
  surfaces. If one does, decision 2 becomes "emit both for longer".

## Related

- `docs/MIGRATION.md` in the extension: 0.1.x to 0.2.x changes.
- Omni-Utils issues and PRs from the 0.2.x work describe the mirror constraints
  (session layer, `_<index>` array prims, `write:*` declared without a value).
