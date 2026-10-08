# Migration guide

- [0.2.x to 0.3.0](#02x-to-030): the bridge splits into a framework and a driver.
- [0.1.x to 0.2.0](#01x-to-020): the connection moves into the stage.

Coming from 0.1.x, read both, in that order. One thing from the second section
no longer holds: `Manager()` with no name was removed in 0.3.0.

## 0.2.x to 0.3.0

0.3.0 splits the bridge in two. The new framework extension
`loupe.simulation.bridge` (from [Omni-Utils](https://github.com/loupeteam/Omni-Utils))
owns everything a simulation touches: the `/PLC` prims, the polling runtimes,
the message bus, the USD mirror and the window. This extension shrinks to a
driver: it registers the Beckhoff ADS driver with the framework under the name
`beckhoff`. The same stage and the same script can then talk to a B&R PLC by
changing the driver on the prim, with no change to the simulation.

**A 0.2.x stage and script run unchanged.** They log the deprecation warnings
described below. Nothing has to be done for 0.3; do the steps before 0.4.

### What changed

| | 0.2.x | 0.3.0 |
|---|---|---|
| Extensions | `loupe.simulation.beckhoff_bridge` | the same, plus `loupe.simulation.bridge`, which it pulls in as a dependency |
| Menu entry and window | `Loupe / Beckhoff Bridge` | `Loupe / PLC Bridge`, one window for every PLC of every vendor |
| PLC prim | `beckhoff_bridge:AmsNetId`, `:Enable`, `:RefreshRate`, `:Variables` (a comma-separated string) | `bridge:driver = "beckhoff"`, `bridge:Enable`, `bridge:RefreshRate`, `bridge:Variables` (a `string[]`), `beckhoff:AmsNetId` |
| Python import | `from loupe.simulation.beckhoff_bridge import BeckhoffBridge` | `from loupe.simulation.bridge import Manager, get_system, get_plc, on_sample_main` |
| Bus events | `loupe.simulation.beckhoff_bridge.<KIND>.<plc>` | `loupe.simulation.bridge.<KIND>.<plc>`; `STATUS` carries `{"kind", "text", "symbols"}` instead of text |
| Getting data | bus callbacks on the worker thread | also `on_sample_main` (main thread, once per frame), `get_plc(name).on_sample` and `.latest()`; see Omni-Utils `docs/CONSUMING.md` |
| `Manager()` with no name | deprecated, worked | **removed**: raises `ValueError` |
| Git clone | `--recurse-submodules` for `loupe/simulation/common` | no submodule; the framework is its own extension |
| Python packages | inside the extension | `beckhoff-bridge` (this repo's `beckhoff_bridge/`) and `plc-bridge`, pip requirements that Kit installs |

### Step 1: the stage

Rewrite each PLC prim with the neutral attributes:

```usda
# 0.2.x
def Scope "PLC1"
{
    custom string beckhoff_bridge:AmsNetId = "127.0.0.1.1.1"
    custom bool beckhoff_bridge:Enable = true
    custom int beckhoff_bridge:RefreshRate = 20
    custom string beckhoff_bridge:Variables = "MAIN.var1,MAIN.arr[0]"
}

# 0.3.0
def Scope "PLC1"
{
    custom string bridge:driver = "beckhoff"
    custom bool bridge:Enable = true
    custom int bridge:RefreshRate = 20
    custom string[] bridge:Variables = ["MAIN.var1", "MAIN.arr[0]"]
    custom string beckhoff:AmsNetId = "127.0.0.1.1.1"
}
```

Or select the PLC in the window and click `Write To USD`, which writes the
neutral form. A prim with `bridge:driver` is read with the neutral attributes
only. A prim without it that carries `beckhoff_bridge:*` attributes is read the
0.2.x way, with a warning once per prim.

### Step 2: the script

```python
# 0.2.x
from loupe.simulation.beckhoff_bridge import BeckhoffBridge
m = BeckhoffBridge.Manager("PLC1")

# 0.3.0
from loupe.simulation.bridge import Manager
m = Manager("PLC1")
```

Everything else is the same: `register_init_callback`,
`register_data_callback`, `add_cyclic_read_variables`, `write_variable`,
`write_variables`, and the `event.payload["data"]` shape. Two differences on
the neutral names: a status callback gets the structured problem
(`event.payload["status"]["text"]` is the old string), and a `WRITE` event
reports each flushed write batch.

A script that subscribes to the bus itself builds the event name with
`loupe.simulation.bridge.bus` (`EVENT_TYPE_DATA_READ`, `get_stream_name`).
`loupe.simulation.common.RuntimeBase.get_stream_name`, which the 0.2.0 guide
pointed at, is gone with the submodule; `BeckhoffBridge.get_stream_name`
stands in for it while that module exists.

For Kit code that touches the stage or the UI, prefer `on_sample_main`: it
calls back on the main thread once per frame with the newest sample, where the
bus calls back on the PLC's worker thread.

### Step 3: the USD mirror

The mirror (values as prims below the PLC prim, with `write:*` attributes) is
on by default in 0.3 and turns **off by default in 0.4**. A stage that relies
on it should say so now with `custom bool bridge:MirrorToUsd = true` on the PLC
prim. A stage that does not use it can opt out now with `false` and save the
mirror's cost. `bridge:MirrorSymbols` (`string[]`) limits the mirror to a watch
list.

### The deprecation warnings

| Warning | Where it comes from | Fix |
|---|---|---|
| `loupe.simulation.beckhoff_bridge.BeckhoffBridge is deprecated since 0.3.0 ...` | importing `BeckhoffBridge`: a Python `DeprecationWarning` and a line in the Kit log | Step 2 |
| a PLC prim that uses the 0.2.x `beckhoff_bridge:*` attributes | opening a stage with a 0.2.x prim, once per prim | Step 1 |
| `Manager('PLC1'): no PLC prim '/PLC/PLC1' is loaded ...` | a `Manager` for a name the stage does not have (as in 0.2.x) | add the prim, or fix the name |

The 0.2.x bus names (`loupe.simulation.beckhoff_bridge.*`) are pushed and
accepted alongside the neutral ones while the framework setting
`/exts/loupe.simulation.bridge/legacyBusNames` is true. `BeckhoffBridge.Manager`
talks on them while they exist, so a 0.2.x status callback still gets text.

When the old names stop working:

| | 0.3.x | 0.4 | 0.5 |
|---|---|---|---|
| `beckhoff_bridge:*` prim attributes | read, with a warning | off by default, behind a compatibility setting | removed |
| `loupe.simulation.beckhoff_bridge.*` bus names | on (`legacyBusNames = true`) | off by default; `legacyBusNames = true` keeps them | removed |
| `BeckhoffBridge` module | imports, with a warning | off by default, behind a compatibility setting | removed |
| USD mirror | on by default | off by default; `bridge:MirrorToUsd = true` per prim | off by default |

"Off by default" means the old name stops working unless the app turns the
compatibility setting on; with it on, it still warns. Treat 0.4 as the
deadline.

To find what still depends on the old bus names before 0.4, run the app with
`--/exts/loupe.simulation.bridge/legacyBusNames=false`: a script that still
subscribes to the vendor names directly gets no data.

### Removed

- `Manager()` with no name, and the in-memory `PLC1` it created from the 0.1.x
  persistent settings. It raises `ValueError`. Add a `/PLC/PLC1` prim and call
  `Manager("PLC1")`.
- The modules `Runtime`, `Communication`, `ui_builder` and `global_variables`.
  The runtime is the framework's (`get_system().get_component("PLC1")`, or
  `get_plc("PLC1")` for the polling object). The driver is
  `from beckhoff_bridge import AdsDriver` (`CommunicationDriver` is still an
  alias there). The attribute name constants have no replacement; the names are
  in the table above.
- The `loupe/simulation/common` submodule. Code that imported
  `loupe.simulation.common.*` imports from `loupe.simulation.bridge` instead.
  It was never documented as public, but this is a public repo.

## 0.1.x to 0.2.0

0.2.0 moves the PLC connection out of the app's persistent settings and into the USD stage, and lets one stage talk to several PLCs. Existing scripts keep running (see [What still works](#what-still-works)), but the setup you did in the old window has to be redone once, as a prim.

### What changed

| | 0.1.x | 0.2.0 |
|---|---|---|
| Where the connection is configured | `Beckhoff Bridge / Open Bridge Settings` window; `Save` wrote to the app's persistent settings | A prim under `/PLC/` in the stage, e.g. `/PLC/PLC1`, carrying `beckhoff_bridge:*` attributes; saved with the stage |
| Number of PLCs | One | Any number, one prim each |
| Python API | `Manager()` | `Manager("PLC1")`, the name of the prim under `/PLC/` |
| Values read from the PLC | Only delivered to Python callbacks | Also mirrored into the stage as prims below the PLC prim (session layer), with `write:*` attributes for writing back without any Python |
| Menu entry | `Beckhoff Bridge / Open Bridge Settings` | `Loupe / Beckhoff Bridge` |
| Window buttons | `Save` / `Load` (persistent settings) | `Write To USD` / `Update From USD` (the PLC prim) |
| Headless apps | Nothing connected until the window was opened | Runtimes are created at startup and on every stage open |
| Cycle time | 3 ADS calls per scan (4 with writes), 8-20 ms jitter | 1 ADS call per scan, about 1 ms jitter |

### Step 1: put the connection in the stage

Open the stage you use with the PLC, then either:

- **From the window.** `Loupe / Beckhoff Bridge`, type a name in `Add component` (use `PLC1` if your scripts call `Manager()` with no name), click `Add`. Fill in the AMS Net ID, refresh rate and the cyclic read variables, tick `Enable ADS Client`, then click `Write To USD`. Save the stage.

- **By hand in the `.usda`.** Add a prim with these attributes anywhere under `/PLC/`:

  ```usda
  def Scope "PLC"
  {
      def Scope "PLC1"
      {
          custom string beckhoff_bridge:AmsNetId = "127.0.0.1.1.1"
          custom bool beckhoff_bridge:Enable = true
          custom int beckhoff_bridge:RefreshRate = 20
          custom string beckhoff_bridge:Variables = "MAIN.custom_struct.var1,MAIN.custom_struct.var_array[0]"
      }
  }
  ```

The values to carry over are the ones you last saved in the old window. They are still in the app's persistent settings under `/persistent/loupe.simulation.beckhoff_bridge/` as `PLC_AMS_NET_ID`, `REFRESH_RATE` and `ENABLE_COMMUNICATION`; the Kit `Preferences` window shows them, or a script can read them:

```python
import carb.settings
s = carb.settings.get_settings()
print(s.get("/persistent/loupe.simulation.beckhoff_bridge/PLC_AMS_NET_ID"))
```

Variables were never persisted in 0.1.x, so they come from your script's `add_cyclic_read_variables` call; you can leave them there or move them onto the prim.

### Step 2: name the PLC in your scripts

```python
# 0.1.x
beckhoff_bridge = BeckhoffBridge.Manager()

# 0.2.0
beckhoff_bridge = BeckhoffBridge.Manager("PLC1")
```

Everything else in the script stays the same: `register_init_callback`, `register_data_callback`, `add_cyclic_read_variables`, `write_variable`, and the `event.payload["data"]` shape in the data callback are unchanged. `write_variables(dict)` is new for writing several values in one request.

### Step 3 (optional): drop the Python

If a script only existed to copy PLC values onto prims, or to write a value when something in the scene changed, it may not be needed any more. Every variable read from the PLC appears as a prim below the PLC prim, following the variable's structure (`MAIN.custom_struct.var1` becomes `/PLC/PLC1/MAIN/custom_struct/var1`; an array element `MAIN.arr[0]` becomes `/PLC/PLC1/MAIN/arr/_0`), with `value`, `write:value`, `write:pause` and `write:once` attributes. OmniGraph and the property window can read and write those directly. See the README for details.

### What still works

- **`Manager()` with no name.** Deprecated, removal planned for 0.3.0. It addresses `PLC1`. If no `/PLC/PLC1` prim is loaded it creates that runtime in memory from the old persistent settings and logs a warning, so an unchanged 0.1.x script on an unchanged machine still connects. The runtime is not saved with the stage and disappears when the stage closes, until the next `Manager()` call. Do Step 1 to make it permanent.
- **Data callbacks.** Same payload shape; a `meta` key with the PLC name is added.
- **Init callbacks.** Still called once immediately with `None` and again on each init event. Note that an init event's payload no longer carries an empty `data` key.

### What breaks

- **Subscribing to the message bus directly** with the exported `EVENT_TYPE_*` constants, instead of through `Manager`. The constants are now plain strings and the events are per PLC (`loupe.simulation.beckhoff_bridge.DATA_READ.PLC1`). Use `Manager` or `loupe.simulation.common.RuntimeBase.get_stream_name(EVENT_TYPE_DATA_READ, "PLC1")` to build the event id.
- **The old persistent settings are no longer written.** The window edits the PLC prim instead.
- **Kit older than 105.** The shared code uses Python 3.10 syntax.

### Status messages

The `Status` field wording changed. Old and new:

| 0.1.x | 0.2.0 |
|---|---|
| `Disabled` | (no message; the `Enable ADS Client` box is unticked) |
| `Attempting to connect...` | `Connecting` |
| `Connected` | `Connected` |
| `Error reading data from the PLC: ...` | `Error Reading: ...`, followed by `Error Reading One Of: [...]` when a symbol does not exist |
| `Error writing data to the PLC: ...` | `Error Writing: ...` |
| | `Error Connecting: ...`, `Disconnected` (new) |
