"""
  File: **BeckhoffBridge.py**
  Copyright (c) 2024 Loupe
  https://loupe.team
  
  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.
  
"""

from typing import Callable
import logging
import carb.events
import carb.settings
import omni.kit.app
from ..common.RuntimeBase import get_stream_name
from ..common.BridgeManager import BridgeManager, Manager_Events as ManEvents
from .global_variables import (
    EXTENSION_NAME,
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID,
    ATTR_BECKHOFF_BRIDGE_ENABLE,
    ATTR_BECKHOFF_BRIDGE_REFRESH,
)

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

# The PLC a 0.1.x script gets when it calls Manager() with no name.
LEGACY_PLC_NAME = "PLC1"

# Where 0.1.x stored its single connection (ui_builder.save_settings). Read once,
# only to seed the legacy PLC; nothing is written back there.
_LEGACY_SETTINGS = {
    "PLC_AMS_NET_ID": ATTR_BECKHOFF_BRIDGE_AMS_NET_ID,
    "REFRESH_RATE": ATTR_BECKHOFF_BRIDGE_REFRESH,
    "ENABLE_COMMUNICATION": ATTR_BECKHOFF_BRIDGE_ENABLE,
}


def _legacy_options() -> dict:
    """
    The 0.1.x persistent settings translated to 0.2.0 component options.
    Only keys that were actually saved are returned, so the defaults apply otherwise.
    """
    settings = carb.settings.get_settings()
    options = {}
    for old_key, attr in _LEGACY_SETTINGS.items():
        value = settings.get("/persistent/" + EXTENSION_NAME + "/" + old_key)
        if value is not None:
            options[attr] = value
    return options


def _ensure_legacy_plc(system) -> bool:
    """
    DEPRECATED compatibility for 0.1.x scripts, scheduled for removal in 0.3.0.

    Create the PLC1 runtime in memory when no PLC of that name is loaded, seeded
    from the 0.1.x persistent settings. Nothing is authored into the user's file:
    the prim is not written and the mirror lives in the session layer, so the
    runtime is gone when the stage closes (and after the UI's Refresh) until the
    next Manager() call. Add a /PLC/PLC1 prim to make it permanent.
    """
    if system.get_component(LEGACY_PLC_NAME) is not None:
        return False
    options = _legacy_options()
    system.add_component(LEGACY_PLC_NAME, options, author_prim=False)
    logger.warning(
        "BeckhoffBridge.Manager() was called without a PLC name and no '%s%s' prim "
        "is loaded, so a '%s' runtime was created from the 0.1.x persistent settings "
        "(%s). This compatibility path is DEPRECATED and will be removed in 0.3.0: "
        "add a '%s%s' prim to the stage and call Manager('%s') instead.",
        system.system_root, LEGACY_PLC_NAME, LEGACY_PLC_NAME,
        options or "defaults", system.system_root, LEGACY_PLC_NAME, LEGACY_PLC_NAME,
    )
    return True


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

    def __init__(self, Name=None):
        """
        Initializes the BeckhoffBridge object for the PLC at /PLC/<Name>.

        Args:
            Name (str): The name of the PLC prim under /PLC/.

        Calling with no name is the 0.1.x form and is DEPRECATED (removal planned
        for 0.3.0): it addresses "PLC1" and, if no such PLC is loaded, creates one in
        memory from the 0.1.x persistent settings so old scripts keep working.
        """
        legacy = Name is None
        if legacy:
            Name = LEGACY_PLC_NAME
        self._plc_name = Name
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()
        self._callbacks = []

        system = get_system()
        if system is None:
            return
        if legacy:
            _ensure_legacy_plc(system)
        elif system.get_component(Name) is None:
            # An explicit name that does not exist is a typo or a load-order problem;
            # inventing a PLC would only hide it.
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
