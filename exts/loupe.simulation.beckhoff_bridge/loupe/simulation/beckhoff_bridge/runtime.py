import time
import threading
import logging
import carb.events
import omni
from threading import RLock
from .ads_driver import AdsDriver

from .BeckhoffBridge import (
    EVENT_TYPE_DATA_READ,
    EVENT_TYPE_DATA_READ_REQ,
    EVENT_TYPE_DATA_WRITE_REQ,
    EVENT_TYPE_DATA_INIT,
    EVENT_TYPE_CONNECTION,
    EVENT_TYPE_ENABLE,
    EVENT_TYPE_STATUS,
    get_stream_name,
)

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, name="PLC1", options={}):

        self._name = name

        self.write_queue = dict()
        self.write_lock = RLock()

        self._thread_is_alive = False
        self._was_connected = False
        self._communication_initialized = False
        self._thread = None

        self._refresh_rate = options.get("REFRESH_RATE") or 20
        self._log_jitter = options.get("LOG_JITTER") or True
        self._enable_communication = options.get("ENABLE_COMMUNICATION") or False
        self._ads_connector = AdsDriver(options.get("PLC_AMS_NET_ID", "127.0.0.1.1.1"))

        self._subscibe_event_stream()

        self._start_update_thread()

    def __del__(self):
        self.cleanup()

    ams_net_id = property(
        lambda self: self._ads_connector.ams_net_id,
        lambda self, value: self._set_ams_net_id(value),
    )

    def _set_ams_net_id(self, value):
        self._ads_connector.ams_net_id = value
        self._communication_initialized = False

    refresh_rate = property(
        lambda self: self._refresh_rate,
        lambda self, value: setattr(self, "_refresh_rate", value),
    )

    enable_communication = property(
        lambda self: self._enable_communication,
        lambda self, value: self._set_enable_communication(value),
    )

    name = property(lambda self: self._name)

    def _set_enable_communication(self, value):
        self._enable_communication = value
        self._communication_initialized = False
        self._push_event(EVENT_TYPE_ENABLE, status={"enabled": value})

    def _start_update_thread(self):
        if not self._thread_is_alive:
            self._thread_is_alive = True
            self._thread = threading.Thread(target=self._update_plc_data)
            self._thread.start()

    def _stop_update_thread(self):
        if self._thread is not None:
            self._thread_is_alive = False
            self._thread.join()

    def _subscibe_event_stream(self):
        # Data stream where the extension will dump the data that it reads from the PLC.
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()

        self.read_req = self._event_stream.create_subscription_to_push_by_type(
            self.get_stream_name(EVENT_TYPE_DATA_READ_REQ), self.on_read_req_event
        )
        self.write_req = self._event_stream.create_subscription_to_push_by_type(
            self.get_stream_name(EVENT_TYPE_DATA_WRITE_REQ), self.on_write_req_event
        )
        self._push_event(EVENT_TYPE_DATA_INIT, data={})

    def _push_event(self, event_type, data=None, status=None):
        try:
            self._event_stream.push(
                event_type=self.get_stream_name(event_type),
                payload=self.create_message(data, status),
            )
        except Exception as e:
            logger.error(f"Error pushing event: {e}")

    def cleanup(self):
        self.read_req.unsubscribe()
        self.write_req.unsubscribe()
        self._stop_update_thread()

    def on_read_req_event(self, event):
        event_data = event.payload
        variables: list = event_data["variables"]
        for name in variables:
            self._ads_connector.add_read(name)

    def on_write_req_event(self, event):
        variables = event.payload["variables"]
        for variable in variables:
            self.queue_write(variable["name"], variable["value"])

    def queue_write(self, name, value):
        with self.write_lock:
            self.write_queue[name] = value

    def _update_plc_data(self):

        thread_start_time = time.time()
        status_update_time = time.time()
        measure = time.time()

        while self._thread_is_alive:
            # Sleep for the refresh rate
            now = time.time()

            sleepy_time = self._refresh_rate / 1000 - (now - thread_start_time)

            if self._log_jitter:
                delta_measure = now - measure
                measure = now
                jitter = (delta_measure - self._refresh_rate / 1000) * 1000

                if abs(jitter) > 1:
                    logger.info(f"Jitter: {int(jitter)} ms. Time: {delta_measure}")

            if sleepy_time > 0:
                thread_start_time = now + sleepy_time
                time.sleep(sleepy_time)
            else:
                # If the refresh rate is too fast,Yield to other threads,
                # but come back to this thread immediately
                thread_start_time = now
                time.sleep(0)

            # Catch exceptions and log them to the status field
            try:
                # Manage connection events
                connected = self._ads_connector.is_connected()

                # Start the communication if it is not initialized
                if self._enable_communication and not connected:
                    self._ads_connector.connect()
                elif not self._enable_communication and connected:
                    self._ads_connector.disconnect()

                if connected and not self._was_connected:
                    self._push_event(EVENT_TYPE_CONNECTION, status="Connected")
                elif not connected and self._was_connected:
                    self._push_event(EVENT_TYPE_CONNECTION, status="Disconnected")

                self._was_connected = connected

                if not connected or not self._enable_communication:
                    time.sleep(1)
                    continue

                # Write data to the PLC if there is data to write
                # If there is an exception, log it to the status field but continue reading data
                try:
                    if self.write_queue:
                        with self.write_lock:
                            values = self.write_queue
                            self.write_queue = dict()
                        self._ads_connector.write_data(values)
                except Exception as e:
                    self._push_event(EVENT_TYPE_STATUS, status=f"Error Writing: {e}")

                try:
                    self._data = self._ads_connector.read_data()
                    if len(self._data) > 0:
                        # Push the data to the event stream
                        self._push_event(EVENT_TYPE_DATA_READ, data=self._data)
                except Exception as e:
                    self._push_event(EVENT_TYPE_STATUS, status=f"Error Reading: {e}")

            except Exception as e:
                self._push_event(EVENT_TYPE_STATUS, status=f"Error: {e}")
                time.sleep(1)

        if self._ads_connector:
            self._ads_connector.disconnect()

    def create_message(self, data=None, status=None):
        obj = {"meta": {"name": self._name}}
        if data:
            obj["data"] = data
        if status:
            obj["status"] = status
        return obj

    def get_stream_name(self, msg_type):
        return get_stream_name(msg_type, self._name)


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
