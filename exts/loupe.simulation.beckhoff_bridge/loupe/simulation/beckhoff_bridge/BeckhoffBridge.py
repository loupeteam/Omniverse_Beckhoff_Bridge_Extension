"""
  File: **BeckhoffBridge.py**
  Copyright (c) 2024 Loupe
  https://loupe.team
  
  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.
  
"""

from typing import Callable
import carb.events
import omni.kit.app

EVENT_TYPE_DATA_INIT = "loupe.simulation.beckhoff_bridge.DATA_INIT"
EVENT_TYPE_DATA_READ = "loupe.simulation.beckhoff_bridge.DATA_READ"
EVENT_TYPE_DATA_READ_REQ = "loupe.simulation.beckhoff_bridge.DATA_READ_REQ"
EVENT_TYPE_DATA_WRITE_REQ = "loupe.simulation.beckhoff_bridge.DATA_WRITE_REQ"
EVENT_TYPE_CONNECTION = "loupe.simulation.beckhoff_bridge.CONNECTION"
EVENT_TYPE_STATUS = "loupe.simulation.beckhoff_bridge.STATUS"
EVENT_TYPE_ENABLE = "loupe.simulation.beckhoff_bridge.ENABLE"

manager = None


def get_system():
    global manager
    return manager


def _set_system(m):
    global manager
    manager = m


class Manager:
    """
    BeckhoffBridge class provides an interface for interacting with the Beckhoff Bridge Extension.
    It can be used in Python scripts to read and write variables.

    Methods:

        register_init_callback( callback : Callable[[carb.events.IEvent], None] ): Registers a callback function for the DATA_INIT event.

        register_data_callback( callback : Callable[[carb.events.IEvent], None] ): Registers a callback function for the DATA_READ event.

        add_cyclic_read_variables( variable_name_array : list[str]): Adds variables to the cyclic read list.

        write_variable( name : str, value : any ): Writes a variable value to the Beckhoff Bridge.
    """

    def __init__(self, Name="PLC1"):
        """
        Initializes the BeckhoffBridge object.
        """
        self._plc_name = Name
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()
        self._callbacks = []

    def __del__(self):
        """
        Cleans up the event subscriptions.
        """
        for callback in self._callbacks:
            self._event_stream.remove_subscription(callback)

    def register_init_callback(self, callback: Callable[[carb.events.IEvent], None]):
        """
        Registers a callback function for the DATA_INIT event.
        The callback is triggered when the Beckhoff Bridge is initialized.
        The user should use this event to add cyclic read variables.
        This event may get called multiple times in normal operation due to the nature of how extensions are loaded.

        Args:
            callback (function): The callback function to be registered.

        Returns:
            None
        """
        self._callbacks.append(
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_DATA_INIT, self._plc_name), callback
            )
        )
        callback(None)

    def register_data_callback(self, callback: Callable[[carb.events.IEvent], None]):
        """
        Registers a callback function for the DATA_READ event.
        The callback is triggered when the Beckhoff Bridge receives new data. The payload contains the updated variables.

        Args:
            callback (Callable): The callback function to be registered.

        example callback:
            def on_message( event ):
                data = event.payload['data']['MAIN']['custom_struct']['var_array']

        Returns:
            None
        """
        self._callbacks.append(
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_DATA_READ, self._plc_name), callback
            )
        )

    def add_cyclic_read_variables(self, variable_name_array: list[str]):
        """
        Adds variables to the cyclic read list.
        Variables in the cyclic read list are read from the Beckhoff Bridge at a fixed interval.

        Args:
            variableList (list): List of variables to be added. ["MAIN.myStruct.myvar1", "MAIN.var2", ...]

        Returns:
            None
        """
        self._event_stream.push(
            event_type=get_stream_name(EVENT_TYPE_DATA_READ_REQ, self._plc_name),
            payload={"variables": variable_name_array},
        )

    def write_variable(self, name: str, value: any):
        """
        Writes a variable value to the Beckhoff Bridge.

        Args:
            name (str): The name of the variable. "MAIN.myStruct.myvar1"
            value (basic type): The value to be written.  1, 2.5, "Hello", ...

        Returns:
            None
        """
        payload = {"variables": [{"name": name, "value": value}]}
        self._event_stream.push(
            event_type=get_stream_name(EVENT_TYPE_DATA_WRITE_REQ, self._plc_name),
            payload=payload,
        )


def get_stream_name(msg_type, name):
    return carb.events.type_from_string(f"{msg_type}.{name})")
