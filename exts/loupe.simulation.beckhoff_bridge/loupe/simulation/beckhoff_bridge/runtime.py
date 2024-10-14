import time
import logging

from threading import RLock
from .Communication import CommunicationDriver
from ..common.RuntimeBase import Runtime_Base

from .global_variables import (ATTR_BECKHOFF_BRIDGE_AMS_NET_ID, ATTR_BECKHOFF_BRIDGE_ENABLE, ATTR_BECKHOFF_BRIDGE_READ_VARS, ATTR_BECKHOFF_BRIDGE_REFRESH) # noqa: E501

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


class Runtime(Runtime_Base):
    # region - Class lifecycle
    def __init__(self, name="PLC1", options={}):

        self._ads_connector = CommunicationDriver(options.get(ATTR_BECKHOFF_BRIDGE_AMS_NET_ID, "127.0.0.1.1.1"))

        super().__init__(name)

        self.write_queue = dict()
        self.write_lock = RLock()

        self._was_connected = False
        self._is_connected = False

        self.refresh_rate = options.get(ATTR_BECKHOFF_BRIDGE_REFRESH) or 20
        self._log_jitter = options.get("LOG_JITTER") or True
        self._enable_communication = options.get(ATTR_BECKHOFF_BRIDGE_ENABLE) or False

        variables = options.get(ATTR_BECKHOFF_BRIDGE_READ_VARS, "")
        if variables:
            variables = variables.split(",")
            for name in variables:
                self._ads_connector.add_read(name.strip())

    # endregion
    # region - Properties
    ams_net_id = property(
        lambda self: self._ads_connector.ams_net_id,
        lambda self, value: self._set_ams_net_id(value),
    )

    def _set_ams_net_id(self, value):
        self._ads_connector.ams_net_id = value
        self._is_connected = False

    enable_communication = property(
        lambda self: self._enable_communication,
        lambda self, value: self._set_enable_communication(value),
    )

    name = property(lambda self: self._name)

    @property
    def options(self):
        return {
            ATTR_BECKHOFF_BRIDGE_AMS_NET_ID: self.ams_net_id,
            ATTR_BECKHOFF_BRIDGE_ENABLE: self.enable_communication,
            ATTR_BECKHOFF_BRIDGE_REFRESH: self.refresh_rate,
            ATTR_BECKHOFF_BRIDGE_READ_VARS: ",".join(self._ads_connector._read_names),
        }

    @options.setter
    def options(self, value):
        self.ams_net_id = value.get(ATTR_BECKHOFF_BRIDGE_AMS_NET_ID, self.ams_net_id)
        self.enable_communication = value.get(ATTR_BECKHOFF_BRIDGE_ENABLE, self.enable_communication)
        self.refresh_rate = value.get(ATTR_BECKHOFF_BRIDGE_REFRESH, self.refresh_rate)
        variables = value.get(ATTR_BECKHOFF_BRIDGE_READ_VARS, self._ads_connector._read_names)
        if variables:
            variables = variables.split(",")
            for name in variables:
                self._ads_connector.add_read(name.strip())


    def _set_enable_communication(self, value):
        self._enable_communication = value
        self._communication_initialized = False
        self._push_event(EVENT_TYPE_ENABLE, status={"enabled": value})

    # endregion

    # region - Event Stream
    def _subscibe_event_stream(self, stream):

        self.read_req = stream.create_subscription_to_push_by_type(
            self._get_stream_name(EVENT_TYPE_DATA_READ_REQ), self._on_read_req_event
        )
        self.write_req = stream.create_subscription_to_push_by_type(
            self._get_stream_name(EVENT_TYPE_DATA_WRITE_REQ), self._on_write_req_event
        )
        self._push_event(EVENT_TYPE_DATA_INIT, data={})

    # endregion
    # region - Event Handlers
    def _on_read_req_event(self, event):
        event_data = event.payload
        variables: list = event_data["variables"]
        for name in variables:
            self._ads_connector.add_read(name)

    def _on_write_req_event(self, event):
        variables = event.payload["variables"]
        for variable in variables:
            self.queue_write(variable["name"], variable["value"])

    # endregion
    # region - Worker Threads
    def _write_data(self):
        try:
            if self._is_connected and self.write_queue:
                with self.write_lock:
                    values = self.write_queue
                    self.write_queue = dict()
                self._ads_connector.write_data(values)
        except Exception as e:
            self._push_event(EVENT_TYPE_STATUS, status=f"Error Writing: {e}")

    def _read_data(self):

        # Start the communication if it is not initialized
        if self._enable_communication and not self._is_connected:
            self._push_event(EVENT_TYPE_CONNECTION, status="Connecting")
            try:
                self._ads_connector.connect()
            except Exception as e:  # noqa
                self._is_connected = False
                self._push_event(EVENT_TYPE_STATUS, status=f"Error Connecting: {e}")
            else:
                self._is_connected = True
                self._push_event(EVENT_TYPE_CONNECTION, status="Connected")

        if not self._enable_communication and self._is_connected:
            self._ads_connector.disconnect()
            self._is_connected = False

        if not self._is_connected and self._was_connected:
            self._push_event(EVENT_TYPE_CONNECTION, status="Disconnected")

        self._was_connected = self._is_connected

        if not self._is_connected or not self._enable_communication:
            time.sleep(1)
            return

        try:
            self._data = self._ads_connector.read_data()
            if len(self._data) > 0:
                # Push the data to the event stream
                self._push_event(EVENT_TYPE_DATA_READ, data=self._data)
        except Exception as e:
            self._push_event(EVENT_TYPE_STATUS, status=f"Error Reading: {e}")
            if e.err_code == 1808:
                variables = self._ads_connector._read_names
                self._push_event(
                    EVENT_TYPE_STATUS, status=f"Error Reading One Of: {variables}"
                )

    def _read_data_ending(self):
        if self._ads_connector:
            self._ads_connector.disconnect()

    # endregion

    # region - External API
    def queue_write(self, name, value):
        with self.write_lock:
            self.write_queue[name] = value

    def _cleanup(self):
        self.read_req.unsubscribe()
        self.write_req.unsubscribe()

    # endregion
