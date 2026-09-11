# Migrating from 0.1.x to 0.2.0

0.2.0 moves the PLC connection out of the app's persistent settings and into the USD stage, and lets one stage talk to several PLCs. Existing scripts keep running (see [What still works](#what-still-works)), but the setup you did in the old window has to be redone once, as a prim.

## What changed

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

## Step 1: put the connection in the stage

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

## Step 2: name the PLC in your scripts

```python
# 0.1.x
beckhoff_bridge = BeckhoffBridge.Manager()

# 0.2.0
beckhoff_bridge = BeckhoffBridge.Manager("PLC1")
```

Everything else in the script stays the same: `register_init_callback`, `register_data_callback`, `add_cyclic_read_variables`, `write_variable`, and the `event.payload["data"]` shape in the data callback are unchanged. `write_variables(dict)` is new for writing several values in one request.

## Step 3 (optional): drop the Python

If a script only existed to copy PLC values onto prims, or to write a value when something in the scene changed, it may not be needed any more. Every variable read from the PLC appears as a prim below the PLC prim, following the variable's structure (`MAIN.custom_struct.var1` becomes `/PLC/PLC1/MAIN/custom_struct/var1`; an array element `MAIN.arr[0]` becomes `/PLC/PLC1/MAIN/arr/_0`), with `value`, `write:value`, `write:pause` and `write:once` attributes. OmniGraph and the property window can read and write those directly. See the README for details.

## What still works

- **`Manager()` with no name.** Deprecated, removal planned for 0.3.0. It addresses `PLC1`. If no `/PLC/PLC1` prim is loaded it creates that runtime in memory from the old persistent settings and logs a warning, so an unchanged 0.1.x script on an unchanged machine still connects. The runtime is not saved with the stage and disappears when the stage closes, until the next `Manager()` call. Do Step 1 to make it permanent.
- **Data callbacks.** Same payload shape; a `meta` key with the PLC name is added.
- **Init callbacks.** Still called once immediately with `None` and again on each init event. Note that an init event's payload no longer carries an empty `data` key.

## What breaks

- **Subscribing to the message bus directly** with the exported `EVENT_TYPE_*` constants, instead of through `Manager`. The constants are now plain strings and the events are per PLC (`loupe.simulation.beckhoff_bridge.DATA_READ.PLC1`). Use `Manager` or `loupe.simulation.common.RuntimeBase.get_stream_name(EVENT_TYPE_DATA_READ, "PLC1")` to build the event id.
- **The old persistent settings are no longer written.** The window edits the PLC prim instead.
- **Kit older than 105.** The shared code uses Python 3.10 syntax.

## Status messages

The `Status` field wording changed. Old and new:

| 0.1.x | 0.2.0 |
|---|---|
| `Disabled` | (no message; the `Enable ADS Client` box is unticked) |
| `Attempting to connect...` | `Connecting` |
| `Connected` | `Connected` |
| `Error reading data from the PLC: ...` | `Error Reading: ...`, followed by `Error Reading One Of: [...]` when a symbol does not exist |
| `Error writing data to the PLC: ...` | `Error Writing: ...` |
| | `Error Connecting: ...`, `Disconnected` (new) |
