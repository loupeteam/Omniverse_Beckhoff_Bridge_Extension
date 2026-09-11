# Beckhoff Bridge

The Beckhoff Bridge is an [NVIDIA Omniverse](https://www.nvidia.com/en-us/omniverse/) extension for communicating with [Beckhoff PLCs](https://www.beckhoff.com/en-en/) using the [ADS protocol](https://infosys.beckhoff.com/english.php?content=../content/1033/cx8190_hw/5091854987.html&id=).

Upgrading from 0.1.x? See [MIGRATION.md](MIGRATION.md).

# Installation

### Install from registry

This is the preferred method. Open up the extensions manager by navigating to `Window / Extensions`. The extension is available as a "Third Party" extension. Search for `Beckhoff Bridge`, and click the slider to Enable it. Once enabled, the extension will be available as an option in the top menu banner of the Omniverse app.

### Install from source

You can also install from source instead. In order to do so, follow these steps:
- Clone the repo [here](https://github.com/loupeteam/Omniverse_Beckhoff_Bridge_Extension) **with submodules** (`git clone --recurse-submodules ...`, or `git submodule update --init` after cloning). The shared runtime code lives in the `loupe/simulation/common` submodule.
- In your Omniverse app, open the extensions manager by navigating to `Window / Extensions`.
- Open the general extension settings, and add a new entry into the `Extension Search Paths` table. This should be the local path to the `exts` folder of the repo that was just cloned.
- Back in the extensions manager, search for `BECKHOFF BRIDGE`, and enable it.
- Once enabled, the extension will show up as an option in the top menu banner.

# Concepts

A **PLC** (also called a *component*) is a prim in the USD stage under `/PLC/`, for example `/PLC/PLC1`. The connection settings live as attributes on that prim, so they are saved with the stage and a stage can describe any number of PLCs:

| Attribute | Type | Default | Meaning |
|---|---|---|---|
| `beckhoff_bridge:AmsNetId` | string | `127.0.0.1.1.1` | AMS Net ID of the PLC |
| `beckhoff_bridge:Enable` | bool | `false` | Enable or disable the ADS client |
| `beckhoff_bridge:RefreshRate` | int | `20` | Cyclic read period in milliseconds |
| `beckhoff_bridge:Variables` | string | `""` | Comma separated list of variables to read cyclically |

When the extension starts, and whenever a stage is opened or closed, every prim carrying these attributes becomes a running **runtime**: a worker thread that connects to the PLC, reads the cyclic variables at the refresh rate, and publishes the values on the Kit message bus. No window has to be opened for this to happen, so the bridge also works in headless apps.

Values read from the PLC are mirrored into the stage as prims below the PLC prim, one per variable, following the variable's structure. `MAIN.custom_struct.var1` on `PLC1` becomes `/PLC/PLC1/MAIN/custom_struct/var1`. An array element becomes a child prim of the array named `_<index>`, because a USD prim name cannot start with a digit: `MAIN.axes[0].position` becomes `/PLC/PLC1/MAIN/axes/_0/position`. Each mirror prim has these attributes:

| Attribute | Meaning |
|---|---|
| `value` | Latest value read from the PLC |
| `symbol` | The PLC variable name |
| `write:value` | Set this to write a value to the PLC |
| `write:pause` | While `true`, changes to `write:value` are not sent (edit several fields, then release) |
| `write:once` | Set to `true` to send `write:value` a single time, even when paused |

The mirror prims live in the stage's **session layer**. They are visible to the property window, scripts and OmniGraph like any other prim, but they are never saved with the stage and do not count as unsaved changes. Edits you make to `write:value` in the property window are authored in your current edit target as usual.

Mirroring can be switched off per PLC by adding a bool attribute `bridge:MirrorToUsd = false` to the PLC prim. Writes through `write:value` still work when the mirror is off.

# Configuration

Open the extension window by clicking on `Loupe / Beckhoff Bridge` from the top menu.

- **Add component**: type a name and click `Add` to create a new PLC prim under `/PLC/` with default settings.
- **Select component**: choose which PLC the rest of the window shows. `Refresh` rescans the stage for PLC prims.
- **Enable ADS Client**: enable or disable the ADS client for the selected PLC.
- **Refresh Rate (ms)**: the period at which the client reads data from the PLC.
- **PLC AMS Net Id**: the AMS Net ID of the PLC to connect to.
- **Cyclic Read Variables**: one variable name per line to read cyclically.
- **Settings**: `Write To USD` stores the current settings on the PLC prim so they are saved with the stage. `Update From USD` reloads them from the prim.

Changes made in the window take effect immediately on the running runtime, but are only persisted once written to USD.

# Usage

### Monitoring Extension Status

The status of the selected PLC is shown in the `Status` field of the `Monitor` pane. Messages clear after a few seconds. Possible messages:
- `Connecting`: the ADS client is trying to connect to the PLC.
- `Connected`: the connection was established.
- `Disconnected`: the connection was lost or the client was disabled.
- `Error Connecting: [...]`: the connection attempt failed.
- `Error Reading: [...]`: an ADS read failed. `Error Reading One Of: [...]` follows when the PLC reports that one of the requested symbols does not exist.
- `Error Writing: [...]`: an ADS write failed.

### Monitoring Variable Values

Once variable reads are occurring, the `Monitor` pane shows a JSON string with the names and values of the variables being read. The same values are visible on the mirrored prims in the stage tree.

### Performing read/write operations from Python

The variables on the PLC that should be read or written can also be specified from a custom user extension or app that uses the API available from the `loupe.simulation.beckhoff_bridge` module. One `Manager` addresses one PLC, by the name of its prim under `/PLC/`.

Scripts written for 0.1.x that call `Manager()` with no name still work, but that form is **deprecated** and will be removed in 0.3.0. It addresses `PLC1` and, if no `/PLC/PLC1` prim is loaded, creates that runtime in memory from the 0.1.x persistent settings and logs a warning. Add a `/PLC/PLC1` prim to the stage and pass the name explicitly.

```python
from loupe.simulation.beckhoff_bridge import BeckhoffBridge

# Instantiate the bridge for the PLC at /PLC/PLC1 and register lifecycle subscriptions
beckhoff_bridge = BeckhoffBridge.Manager("PLC1")
beckhoff_bridge.register_init_callback(on_beckoff_init)
beckhoff_bridge.register_data_callback(on_message)

# This function gets called once on init, and should be used to subscribe to cyclic reads.
def on_beckoff_init( event ):
    # Create a list of variable names to be read cyclically, and add to Manager
    variables = [   'MAIN.custom_struct.var1',
                    'MAIN.custom_struct.var_array[0]',
                    'MAIN.custom_struct.var_array[1]']

    beckhoff_bridge.add_cyclic_read_variables(variables)

# This function is called every time the bridge receives new data
def on_message( event ):
    # Read the event data, which includes values for the PLC variables requested
    data = event.payload['data']['MAIN']['custom_struct']['var_array']

# In the app's cyclic logic, writes can be performed as follows:
def cyclic():
    # Write the value `1` to PLC variable 'MAIN.custom_struct.var1'
    beckhoff_bridge.write_variable('MAIN.custom_struct.var1', 1)

    # Or several at once
    beckhoff_bridge.write_variables({'MAIN.custom_struct.var1': 1, 'MAIN.custom_struct.var2': 2.5})
```

The system that owns all runtimes is also reachable, for example to create runtimes for prims added by a script:

```python
from loupe.simulation.beckhoff_bridge.BeckhoffBridge import get_system

system = get_system()
system.find_and_create_components()      # rescan the stage
runtime = system.get_component("PLC1")   # the Runtime object for /PLC/PLC1
```
