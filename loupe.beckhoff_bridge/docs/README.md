# Beckhoff Bridge

The Beckhoff Bridge is a software that allows to communicate with Beckhoff PLCs using the ADS protocol.

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
    # Send the variable names we care about
    variables = [   'MAIN.custom_struct.var1', 
                    'MAIN.custom_struct.var_array[0]', 
                    'MAIN.custom_struct.var_array[1]']

    # Add the variables to be read cyclically
    beckhoff_bridge.add_cyclic_read_variables(variables)

    # Write a 1 to the variable 'MAIN.custom_struct.var1'
    beckhoff_bridge.write_variable('MAIN.custom_struct.var1', 1)

def on_message( event ):
    # Get the data from the event
    data = event.payload['data']['MAIN']['custom_struct']['var_array']

```