# Beckhoff Bridge

The Beckhoff Bridge is an [NVIDIA Omniverse](https://www.nvidia.com/en-us/omniverse/) extension to communicate with `[Beckhoff PLCs](https://www.beckhoff.com/en-en/)` using the [ADS protocol](https://infosys.beckhoff.com/english.php?content=../content/1033/cx8190_hw/5091854987.html&id=).
# Installation

Install this extension via Omniverse's [Extensions Manager](https://docs.omniverse.nvidia.com/extensions/latest/ext_core/ext_extension-manager.html#)

## Enabling the Extension

To enable this extension, go to the Extension Manager menu and enable loupe.beckhoff_bridge extension.

## Configuration

- Enable ADS Client: Enable or disable the ADS client from reading or writing data to the PLC.
- Refresh Rate: The rate at which the ADS client will read data from the PLC.
- PLC AMS Net ID: The AMS Net ID of the PLC to connect to.
- Load: Load the previous configuration.
- Save: Save the current configuration.

## Usage

Once the extension is enabled, the Beckhoff Bridge will start reading data from the PLC.

The user extension specifies what data to read using the API available in the `loupe.beckhoff_bridge` module.

```python
# Import the API from the beckhoff_bridge extension
from omni.isaac.core.utils.extensions import get_extension_path_from_name
extension_path = get_extension_path_from_name('loupe.beckhoff_bridge')
sys.path.append(extension_path)
from loupe.beckhoff_bridge import BeckhoffBridge

        
# Create a subscription to the data read event
beckhoff_bridge = BeckhoffBridge.Manager()
beckhoff_bridge.register_init_callback(on_beckoff_init)
beckhoff_bridge.register_data_callback(on_message)

def on_beckoff_init( event ):
    # Create a list of variable names to be read cyclically, and add to Manager
    variables = [   'MAIN.custom_struct.var1', 
                    'MAIN.custom_struct.var_array[0]', 
                    'MAIN.custom_struct.var_array[1]']

    beckhoff_bridge.add_cyclic_read_variables(variables)

    # Write the value `1` to PLC variable 'MAIN.custom_struct.var1'
    beckhoff_bridge.write_variable('MAIN.custom_struct.var1', 1)

def on_message( event ):
    # Read the event data, which includes values for the PLC variables requested
    data = event.payload['data']['MAIN']['custom_struct']['var_array']

```