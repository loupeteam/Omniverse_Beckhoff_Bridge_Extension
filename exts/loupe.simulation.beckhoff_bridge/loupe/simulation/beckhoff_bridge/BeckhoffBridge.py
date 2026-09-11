"""
  File: **BeckhoffBridge.py**
  Copyright (c) 2024 Loupe
  https://loupe.team
  
  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.
  
"""

from typing import Callable
import logging
import carb.events
import omni.kit.app
from ..common.RuntimeBase import get_stream_name
from ..common.BridgeManager import BridgeManager, Manager_Events as ManEvents

beckhoff_bridge_name = "beckhoff_bridge"
Manager_Events = ManEvents(beckhoff_bridge_name)

EVENT_TYPE_DATA_INIT = Manager_Events.EVENT_TYPE_DATA_INIT
EVENT_TYPE_DATA_READ = Manager_Events.EVENT_TYPE_DATA_READ
EVENT_TYPE_DATA_READ_REQ = Manager_Events.EVENT_TYPE_DATA_READ_REQ
EVENT_TYPE_DATA_WRITE_REQ = Manager_Events.EVENT_TYPE_DATA_WRITE_REQ
EVENT_TYPE_CONNECTION = Manager_Events.EVENT_TYPE_CONNECTION
EVENT_TYPE_STATUS = Manager_Events.EVENT_TYPE_STATUS
EVENT_TYPE_ENABLE = Manager_Events.EVENT_TYPE_ENABLE

manager = None
logger = logging.getLogger(__name__)


def get_system():
    global manager
    return manager


def _set_system(m):
    global manager
    manager = m


class Manager(BridgeManager):
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
        Initializes the BeckhoffBridge object for the PLC at /PLC/<Name>.

        Args:
            Name (str): The name of the PLC prim under /PLC/. Defaults to "PLC1".
        """
        self._plc_name = Name
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()
        self._callbacks = []

        # Since 0.2.0 a Manager addresses one PLC prim; before that there was a
        # single connection configured in the app's persistent settings. A script
        # written for 0.1.x still constructs Manager() and then waits for data that
        # never comes, with nothing logged. Say so.
        system = get_system()
        if system is not None and system.get_component(Name) is None:
            logger.warning(
                "BeckhoffBridge.Manager('%s'): no PLC prim '%s%s' is loaded, so no "
                "data will arrive until one exists. Since 0.2.0 a PLC is configured "
                "as a prim under /PLC/ (see the README), not in persistent settings.",
                Name, system.system_root, Name,
            )

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

    def write_variables(self, data: dict):
        """
        Writes several variable values to the Beckhoff Bridge in one request.

        Args:
            data (dict): Variable names mapped to the values to write.
                {"MAIN.myStruct.myvar1": 1, "MAIN.str": "Hello"}

        Returns:
            None
        """
        writes = []
        for name, value in data.items():
            writes.append({"name": name, "value": value})
        payload = {"variables": writes}
        self._event_stream.push(
            event_type=get_stream_name(EVENT_TYPE_DATA_WRITE_REQ, self._plc_name),
            payload=payload,
        )
