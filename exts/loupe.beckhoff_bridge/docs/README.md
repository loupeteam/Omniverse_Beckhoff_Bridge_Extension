# Beckhoff Bridge

The Beckhoff Bridge is an [NVIDIA Omniverse](https://www.nvidia.com/en-us/omniverse/) extension for communicating with [Beckhoff PLCs](https://www.beckhoff.com/en-en/) using the [ADS protocol](https://infosys.beckhoff.com/english.php?content=../content/1033/cx8190_hw/5091854987.html&id=).

# Installation

### Install from registry

This is the preferred method. Open up the extensions manager by navigating to `Window / Extensions`. The extension is available as a THIRD PARTY extension. Search for `BECKHOFF BRIDGE`, and click the slider to Enable it. Once enabled, the extension will show up as an option in the top menu banner. 

### Install from source

You can also install from source instead. In order to do so, follow these steps:
- Clone the repo [here](https://github.com/loupeteam/Omniverse_Beckhoff_Bridge_Extension).
- In your Omniverse app, open the extensions manager by navigating to `Window / Extensions`.
- Open the general extension settings, and add a new entry into the `Extension Search Paths` table. This should be the local path to the root of the repo that was just cloned. 
- Back in the extensions manager, search for `BECKHOFF BRIDGE`, and enable it. 
- Once enabled, the extension will show up as an option in the top menu banner. 

# Configuration

You can open the extension by clicking on `Beckhoff Bridge / Open Bridge Settings` from the top menu. The following configuration options are available:

- Enable ADS Client: Enable or disable the ADS client from reading or writing data to the PLC.
- Refresh Rate: The rate at which the ADS client will read data from the PLC in milliseconds.
- PLC AMS Net ID: The AMS Net ID of the PLC to connect to.
- Settings commands: These commands are used to load and save the extension settings as permanent parameters. The Save button backs up the current parameters, and the Load button restores them from the last saved values. 

# Usage

Once the extension is enabled, the Beckhoff Bridge will attempt to connect to the PLC.

### Monitoring Extension Status

The status of the extension can be viewed in the `Status` field. Here are the possible messages and their meaning:
- `Disabled`: the enable checkbox is unchecked, and no communication is attempted. 
- `Attempting to connect...`: the ADS client is trying to connect to the PLC. Staying in this state for more than a few seconds indicates that there is a problem with the connection. 
- `Connected`: the ADS client has successfully established a connection with the PLC. 
- `Error writing data to the PLC: [...]`: an error occurred while performing an ADS variable write. 
- `Error reading data from the PLC: [...]`: an error occurred while performing an ADS variable read.

### Monitoring Variable Values

Once variable reads are occurring, the `Monitor` pane will show a JSON string with the names and values of the variables being read. This is helpful for troubleshooting. 

### Performing read/write operations

The variables on the PLC that should be read or written are specified in a custom user extension or app that uses the API available from the `loupe.beckhoff_bridge` module.

```python
from loupe.beckhoff_bridge import BeckhoffBridge
      
# Instantiate the bridge and register lifecycle subscriptions
beckhoff_bridge = BeckhoffBridge.Manager()
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

```