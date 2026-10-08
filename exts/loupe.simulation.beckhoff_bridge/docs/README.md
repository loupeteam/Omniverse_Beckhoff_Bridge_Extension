# Beckhoff Bridge

The Beckhoff Bridge connects [NVIDIA Omniverse](https://www.nvidia.com/en-us/omniverse/) to [Beckhoff PLCs](https://www.beckhoff.com/en-en/) over the [ADS protocol](https://infosys.beckhoff.com/english.php?content=../content/1033/cx8190_hw/5091854987.html&id=).

Since 0.3.0 it is a driver for the vendor-neutral **PLC Bridge** framework, the extension `loupe.simulation.bridge` from [Omni-Utils](https://github.com/loupeteam/Omni-Utils). The framework owns the PLC prims, the polling, the message bus, the USD mirror and the window; this extension registers the Beckhoff ADS driver with it under the name `beckhoff`. A simulation written against the framework runs on a Beckhoff or a B&R PLC by changing one attribute on the PLC prim.

Upgrading from 0.2.x or 0.1.x? See [MIGRATION.md](MIGRATION.md).

# Installation

### Install from registry

Open the extensions manager (`Window / Extensions`), search for `Beckhoff Bridge` under "Third Party", and enable it. Kit enables the framework extension `loupe.simulation.bridge` with it and installs the Python packages (`pyads`, `beckhoff-bridge`, `plc-bridge`).

### Install from source

- Clone this repo and [Omni-Utils](https://github.com/loupeteam/Omni-Utils) side by side.
- In your Omniverse app, open `Window / Extensions`, then the general extension settings, and add both repos' `exts` folders to the `Extension Search Paths`.
- Make the Python packages available to Kit: `tools/dev_link.py` (from source) or `tools/build_wheels.py` (bundled wheels). See the root README.
- Search for `BECKHOFF BRIDGE` in the extensions manager and enable it.

# Configuring a PLC

A PLC is a prim under `/PLC/`, for example `/PLC/PLC1`, saved with the stage. A stage can hold any number of them, of any vendor:

```usda
def Scope "PLC"
{
    def Scope "PLC1"
    {
        custom string bridge:driver = "beckhoff"
        custom bool bridge:Enable = true
        custom int bridge:RefreshRate = 20
        custom string[] bridge:Variables = ["MAIN.custom_struct.var1", "MAIN.custom_struct.var_array[0]"]
        custom string beckhoff:AmsNetId = "127.0.0.1.1.1"
    }
}
```

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `bridge:driver` | string | | `beckhoff` selects this driver |
| `bridge:Enable` | bool | `false` | Connect and poll |
| `bridge:RefreshRate` | int | `20` | Read period in milliseconds |
| `bridge:Variables` | string[] | `[]` | Variables read every period |
| `bridge:MirrorToUsd` | bool | `true` in 0.3 | Mirror the values into the stage (see below) |
| `beckhoff:AmsNetId` | string | `127.0.0.1.1.1` | AMS Net ID of the PLC |

The 0.2.x form, `beckhoff_bridge:AmsNetId` / `Enable` / `RefreshRate` / `Variables` without `bridge:driver`, is still read in 0.3, with a deprecation warning.

The prims can also be created and edited from the window, `Loupe / PLC Bridge`: add a component, pick the `beckhoff` driver, fill in the AMS Net ID, and `Write To USD`.

A runtime is created for every PLC prim when the extension starts and whenever a stage is opened, with or without the window, so the bridge works headless.

# Using the data

`docs/CONSUMING.md` in [Omni-Utils](https://github.com/loupeteam/Omni-Utils) covers the ways to get at the data and the thread rules. In short:

```python
from loupe.simulation.bridge import Manager, get_plc, on_sample_main

# Main thread, once per frame, newest sample: the default for Kit code.
remove = on_sample_main("PLC1", lambda s: print(s.values["MAIN.custom_struct.var1"]))

# Every sample, on the PLC's worker thread; or pull the newest.
plc = get_plc("PLC1")
plc.on_sample(lambda s: ...)
latest = plc.latest()
plc.queue_write("MAIN.custom_struct.var1", 1)

# The 0.2.x message bus API, on the neutral bus names.
manager = Manager("PLC1")
manager.register_data_callback(lambda event: event.payload["data"]["MAIN"]["custom_struct"])
manager.add_cyclic_read_variables(["MAIN.custom_struct.var2"])
manager.write_variable("MAIN.custom_struct.var1", 1)
```

`from loupe.simulation.beckhoff_bridge import BeckhoffBridge` still works in 0.3 and gives the same `Manager` on the 0.2.x bus names, with a deprecation warning.

# The USD mirror

Values read from the PLC appear as prims below the PLC prim in the stage's session layer: `MAIN.custom_struct.var1` on `PLC1` becomes `/PLC/PLC1/MAIN/custom_struct/var1`, and an array element `MAIN.axes[0].position` becomes `/PLC/PLC1/MAIN/axes/_0/position`. Each has `value`, `symbol`, and `write:value` / `write:pause` / `write:once` for writing back without Python. The mirror is on by default in 0.3 and off by default from 0.4; set `bridge:MirrorToUsd` on the prim to choose, and `bridge:MirrorSymbols` to limit it to a watch list.

# Status

The window shows each PLC's connection (`Connecting`, `Connected`, `Disconnected`) and the last problem, such as `Error Connecting: ...` or `Error Reading: <symbol>: <reason>`. Code gets the same as structured problems from `get_plc(name).on_problem`.
