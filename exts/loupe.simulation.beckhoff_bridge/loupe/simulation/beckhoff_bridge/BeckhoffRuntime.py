import time
import threading
import logging
import carb.events
import omni
from threading import RLock
from .ads_driver import AdsDriver
from .runtime_base import Runtime_Base
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
        self._name = name
        self._ads_connector = AdsDriver(options.get("PLC_AMS_NET_ID", "127.0.0.1.1.1"))

        super().__init__()

        self.write_queue = dict()
        self.write_lock = RLock()

        self._was_connected = False
        self._is_connected = False

        self.refresh_rate = options.get("REFRESH_RATE") or 20
        self._log_jitter = options.get("LOG_JITTER") or True
        self._enable_communication = options.get("ENABLE_COMMUNICATION") or False


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

    def _set_enable_communication(self, value):
        self._enable_communication = value
        self._communication_initialized = False
        self._push_event(EVENT_TYPE_ENABLE, status={"enabled": value})

    # endregion

    # region - Event Stream
    def _subscibe_event_stream(self, stream):

        self.read_req = stream.create_subscription_to_push_by_type(
            self.get_stream_name(EVENT_TYPE_DATA_READ_REQ), self._on_read_req_event
        )
        self.write_req = stream.create_subscription_to_push_by_type(
            self.get_stream_name(EVENT_TYPE_DATA_WRITE_REQ), self._on_write_req_event
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
            else:
                time.sleep(0.005)
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
                self._push_event(
                    EVENT_TYPE_STATUS, status=f"Error Connecting: {e}"
                )
            else:
                self._is_connected = True
                self._push_event(EVENT_TYPE_CONNECTION, status="Connected")

        elif not self._enable_communication and self._is_connected:
            self._ads_connector.disconnect()

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

    def _read_data_ending(self):
        if self._ads_connector:
            self._ads_connector.disconnect()

    # endregion

    # region - External API
    def queue_write(self, name, value):
        with self.write_lock:
            self.write_queue[name] = value

    def cleanup(self):
        self.read_req.unsubscribe()
        self.write_req.unsubscribe()
        self._stop_update_thread()

    # endregion


# A singleton class that manages many PLC Connections
class System:
    def __init__(self):
        self.init()

    def init(self):
        self._plcs = dict()
        self._default_options = {
            "PLC_AMS_NET_ID": "127.0.0.1.1.1",
            "REFRESH_RATE": 20,
            "ENABLE_COMMUNICATION": False,
            "LOG_JITTER": False,
        }

    def cleanup(self):
        for plc in self._plcs.values():
            plc.cleanup()
            del plc

    def set_default_options(self, options):
        self._default_options = options

    def get_plc(self, name: str | int):
        if name not in self._plcs:
            self._plcs[name] = Runtime(name, self._default_options)
        return self._plcs[name]

    # Return the names of the PLCs as a list
    def get_plc_names(self):
        return list(self._plcs.keys())

    def add_plc(self, name, options):
        self._plcs[name] = Runtime(name, options)
