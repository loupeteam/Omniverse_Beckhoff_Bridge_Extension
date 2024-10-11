import time
import threading
import logging
import omni
from .BeckhoffBridge import get_stream_name
logger = logging.getLogger(__name__)


class Runtime_Base:
    # region - Class lifecycle
    def __init__(self):
        if not hasattr(self, "_name"):
            self._name = "Runtime_Base"
        self._thread_is_alive = False
        self._refresh_rate = 20
        self._thread = []

        self.__subscibe_event_stream()
        self._thread_methods = []
        self._start_update_thread()

    def __del__(self):
        self.cleanup()

    # endregion

    refresh_rate = property(
        lambda self: self._refresh_rate,
        lambda self, value: setattr(self, "_refresh_rate", value),
    )

    # region - Thread Management
    def _start_update_thread(self):
        if not self._thread_is_alive:
            self._thread_is_alive = True
            # Add internal methods to the thread methods
            self._threads = [
                threading.Thread(target=self.__read_data),
                threading.Thread(target=self.__write_data),
            ]

            # Add any user defined methods to the thread methods
            for method in self._thread_methods:
                self._threads.append(threading.Thread(target=method))

            for thread in self._threads:
                thread.start()

    def _stop_update_thread(self):
        self._thread_is_alive = False
        for thread in self._threads:
            thread.join()

        self._threads = []

    # endregion
    # region - Event Stream
    def __subscibe_event_stream(self):
        # Data stream where the extension will dump the data that it reads from the PLC.
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()

        self._subscibe_event_stream(self._event_stream)

    def _subscibe_event_stream(self, event_stream):
        pass

    def _push_event(self, event_type, data=None, status=None):
        try:
            self._event_stream.push(
                event_type=self.get_stream_name(event_type),
                payload=self.create_message(data, status),
            )
        except Exception as e:
            logger.error(f"Error pushing event: {e}")

    # endregion
    # region - Worker Threads
    def _write_data(self):
        pass

    def _read_data(self):
        pass

    def _write_data_ending(self):
        pass

    def _read_data_ending(self):
        pass

    def _write_data_starting(self):
        pass

    def _read_data_starting(self):
        pass

    def __write_data(self):
        self._read_data_starting()
        while self._thread_is_alive:
            try:
                self._write_data()
                time.sleep(0.005)
            except Exception as e:
                pass
                # self._push_event(EVENT_TYPE_STATUS, status=f"Error Writing: {e}")

        self._read_data_ending()

    def __read_data(self):

        self._read_data_starting()

        thread_start_time = time.time()

        while self._thread_is_alive:
            # Sleep for the refresh rate
            now = time.time()
            sleep_time = self.refresh_rate / 1000 - (now - thread_start_time)
            if sleep_time > 0:
                thread_start_time = now + sleep_time
                time.sleep(sleep_time)
            else:
                # If the refresh rate is too fast,Yield to other threads,
                # but come back to this thread immediately
                thread_start_time = now
                time.sleep(0)

            # Catch exceptions and log them to the status field
            try:
                self._read_data()
            except Exception as e:
                time.sleep(1)

        self._read_data_ending()

    # endregion
    # region - Helper Functions
    def create_message(self, data=None, status=None):
        obj = {"meta": {"name": self._name}}
        if data:
            obj["data"] = data
        if status:
            obj["status"] = status
        return obj

    def get_stream_name(self, msg_type):
        return get_stream_name(msg_type, self._name)

    # endregion
    # region - External API
    def cleanup(self):
        self.read_req.unsubscribe()
        self.write_req.unsubscribe()
        self._stop_update_thread()

    # endregion
