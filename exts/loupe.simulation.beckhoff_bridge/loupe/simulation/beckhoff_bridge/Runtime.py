"""
  File: **Runtime.py**
  Copyright (c) 2024 Loupe
  https://loupe.team

  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

  The Kit side of one PLC. The polling itself is plc_bridge.PlcRuntime driving a
  beckhoff_bridge.AdsDriver, both plain Python. This class only connects that
  runtime to Kit: options from the PLC prim in, carb message bus events out, bus
  read and write requests in.
"""

import logging

import omni.kit.app

from beckhoff_bridge import AdsDriver
from plc_bridge import PlcRuntime

from ..common.RuntimeBase import get_stream_name

from .global_variables import (
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID,
    ATTR_BECKHOFF_BRIDGE_ENABLE,
    ATTR_BECKHOFF_BRIDGE_READ_VARS,
    ATTR_BECKHOFF_BRIDGE_REFRESH,
)  # noqa: E501

from .BeckhoffBridge import (
    EVENT_TYPE_DATA_READ,
    EVENT_TYPE_DATA_READ_REQ,
    EVENT_TYPE_DATA_WRITE_REQ,
    EVENT_TYPE_DATA_INIT,
    EVENT_TYPE_CONNECTION,
    EVENT_TYPE_ENABLE,
    EVENT_TYPE_STATUS,
)

logger = logging.getLogger(__name__)


def _option(options: dict, key: str, default):
    """
    Read an option, falling back to the default when the key is missing or None.
    Do not use `options.get(key) or default`: that turns a legitimate False or 0
    into the default, so the option can never be switched off.
    """
    value = options.get(key)
    return default if value is None else value


class Runtime:
    # region - Class lifecycle
    def __init__(self, name="PLC1", options=None):
        options = options or {}
        self._name = name

        self._driver = AdsDriver(
            _option(options, ATTR_BECKHOFF_BRIDGE_AMS_NET_ID, "127.0.0.1.1.1")
        )
        self._plc = PlcRuntime(
            self._driver,
            name=name,
            refresh_ms=_option(options, ATTR_BECKHOFF_BRIDGE_REFRESH, 20),
            enabled=_option(options, ATTR_BECKHOFF_BRIDGE_ENABLE, False),
        )
        self._plc.set_read_variables((options.get(ATTR_BECKHOFF_BRIDGE_READ_VARS) or "").split(","))

        # Runtime events -> message bus. These run on the runtime's worker threads,
        # as the pushes always have; subscribers that touch the stage or the UI
        # marshal to the main thread themselves (see RuntimeUsd).
        self._plc.on_data(lambda data: self._push_event(EVENT_TYPE_DATA_READ, data=data))
        self._plc.on_status(lambda text: self._push_event(EVENT_TYPE_STATUS, status=text))
        self._plc.on_connection(lambda state: self._push_event(EVENT_TYPE_CONNECTION, status=state))
        self._plc.on_enabled(
            lambda enabled: self._push_event(EVENT_TYPE_ENABLE, status={"enabled": enabled}))

        # Message bus requests -> runtime
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()
        self._read_req = self._event_stream.create_subscription_to_push_by_type(
            self._get_stream_name(EVENT_TYPE_DATA_READ_REQ), self._on_read_req_event
        )
        self._write_req = self._event_stream.create_subscription_to_push_by_type(
            self._get_stream_name(EVENT_TYPE_DATA_WRITE_REQ), self._on_write_req_event
        )
        self._push_event(EVENT_TYPE_DATA_INIT, data={})

        self._plc.start()

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        """Stop polling and leave the message bus. Safe to call more than once."""
        plc = getattr(self, "_plc", None)  # __init__ may have failed before it existed
        if plc is not None:
            plc.stop()
        for attr in ("_read_req", "_write_req"):
            subscription = getattr(self, attr, None)
            if subscription is not None:
                subscription.unsubscribe()
                setattr(self, attr, None)

    # endregion
    # region - Properties
    name = property(lambda self: self._name)
    plc = property(lambda self: self._plc, doc="The plc_bridge.PlcRuntime doing the polling.")
    driver = property(lambda self: self._driver, doc="The beckhoff_bridge.AdsDriver.")
    is_connected = property(lambda self: self._plc.is_connected)
    read_variables = property(lambda self: self._plc.read_variables)

    ams_net_id = property(
        lambda self: self._driver.ams_net_id,
        lambda self, value: self._set_ams_net_id(value),
    )

    def _set_ams_net_id(self, value):
        if value == self._driver.ams_net_id:
            return
        self._driver.ams_net_id = value
        self._plc.reconnect()

    enable_communication = property(
        lambda self: self._plc.enabled,
        lambda self, value: setattr(self._plc, "enabled", value),
    )

    refresh_period_ms = property(
        lambda self: self._plc.refresh_ms,
        lambda self, value: setattr(self._plc, "refresh_ms", value),
    )
    # Two names for one value; the prim attribute is called RefreshRate.
    refresh_rate = refresh_period_ms

    write_sleep_time = property(
        lambda self: self._plc.write_sleep,
        lambda self, value: setattr(self._plc, "write_sleep", value),
    )

    @property
    def options(self):
        return {
            ATTR_BECKHOFF_BRIDGE_AMS_NET_ID: self.ams_net_id,
            ATTR_BECKHOFF_BRIDGE_ENABLE: self.enable_communication,
            ATTR_BECKHOFF_BRIDGE_REFRESH: self.refresh_rate,
            ATTR_BECKHOFF_BRIDGE_READ_VARS: ",".join(self._plc.read_variables),
        }

    @options.setter
    def options(self, value):
        self.ams_net_id = value.get(ATTR_BECKHOFF_BRIDGE_AMS_NET_ID, self.ams_net_id)
        # Always assigned, as in 0.2.x: the assignment pushes the ENABLE event that
        # tells listeners the options were (re)applied.
        self.enable_communication = value.get(
            ATTR_BECKHOFF_BRIDGE_ENABLE, self.enable_communication
        )
        self.refresh_rate = _option(value, ATTR_BECKHOFF_BRIDGE_REFRESH, self.refresh_rate)
        # The variables option replaces the cyclic read list, so a variable removed
        # from the prim stops being read. A missing key leaves the list alone.
        if ATTR_BECKHOFF_BRIDGE_READ_VARS in value:
            variables = value[ATTR_BECKHOFF_BRIDGE_READ_VARS] or ""
            self.set_read_variables(variables.split(","))

    # endregion
    # region - Message bus
    def _get_stream_name(self, msg_type):
        return get_stream_name(msg_type, self._name)

    def _push_event(self, event_type, data=None, status=None):
        message = {"meta": {"name": self._name}}
        if data:
            message["data"] = data
        if status:
            message["status"] = status
        try:
            self._event_stream.push(
                event_type=self._get_stream_name(event_type), payload=message)
        except Exception as e:
            logger.error(f"Error pushing event: {e}")

    def _on_read_req_event(self, event):
        self._plc.add_read_variables(event.payload["variables"])

    def _on_write_req_event(self, event):
        for variable in event.payload["variables"]:
            self.queue_write(variable["name"], variable["value"])

    # endregion
    # region - External API
    def set_read_variables(self, variables):
        """
        Replace the cyclic read list. Blank entries are dropped and whitespace is
        stripped (see PlcRuntime.set_read_variables).
        """
        self._plc.set_read_variables(variables)

    def queue_write(self, name, value):
        self._plc.queue_write(name, value)

    # endregion
