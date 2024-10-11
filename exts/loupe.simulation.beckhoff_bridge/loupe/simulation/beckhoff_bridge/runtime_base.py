import time
import threading
import logging
import omni
from .BeckhoffBridge import get_stream_name
from typing import final

logger = logging.getLogger(__name__)


""" Notes about the Runtime_Base class:
    - This class is a base class that should be inherited by the child class.
    - The child class should override the following methods:
        - _cleanup
        - _write_data
        - _read_data
        - _write_data_ending
        - _read_data_ending
        - _write_data_starting
        - _read_data_starting
        - _subscibe_event_stream
    - The User should call the cleanup method when the class is no longer needed.

    Naming Conventions:
    - Methods that can be overridden by the child class should be prefixed with an underscore.
    - Methods that should not be overridden by the child class should be prefixed with a double underscore.
    - Do not override anything with @final
    - Anything the has __ should call super().__
""" 

class Runtime_Base:
    # region - Overridable Methods: These methods should be overridden by the child class
    def _cleanup(self):
        pass

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

    def _subscibe_event_stream(self, event_stream):
        pass

    # endregion

    # region - Class lifecycle
    def __init__(self, name):
        self._name = name

        self._thread_is_alive = False
        self._refresh_rate = 20

        self.__threads = []

        self.__start_update_thread()
        self.__subscibe_event_stream()

    def __del__(self):
        self.cleanup()

    # endregion
    # region - Properties
    refresh_rate = property(
        lambda self: self._refresh_rate,
        lambda self, value: setattr(self, "_refresh_rate", value),
    )

    # endregion
    # region - Thread Management
    def __start_update_thread(self):
        if not self._thread_is_alive:
            self._thread_is_alive = True
            # Add internal methods to the thread methods
            self.__threads = [
                threading.Thread(target=self.__read_data),
                threading.Thread(target=self.__write_data),
            ]

            for thread in self.__threads:
                thread.start()

    def __stop_update_thread(self):
        self._thread_is_alive = False
        for thread in self.__threads:
            thread.join()

        self.__threads = []

    # endregion
    # region - Event Stream
    def __subscibe_event_stream(self):
        # Data stream where the extension will dump the data that it reads from the PLC.
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()

        self._subscibe_event_stream(self._event_stream)

    # endregion
    # region - Worker Threads

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
    def _push_event(self, event_type, data=None, status=None):
        try:
            self._event_stream.push(
                event_type=self._get_stream_name(event_type),
                payload=self._create_message(data, status),
            )
        except Exception as e:
            logger.error(f"Error pushing event: {e}")

    def _create_message(self, data=None, status=None):
        obj = {"meta": {"name": self._name}}
        if data:
            obj["data"] = data
        if status:
            obj["status"] = status
        return obj

    def _get_stream_name(self, msg_type):
        return get_stream_name(msg_type, self._name)

    # endregion
    # region - External API
    @final    
    def cleanup(self):
        """
        FINAL - Do not override this method
        """        
        self.__stop_update_thread()
        self._cleanup()

    @final
    def _add_thread_method(self, method):
        """
        FINAL - Do not override this method
        """        
        thread = threading.Thread(target=method)
        self.__threads.append(thread)
        thread.start()

    # endregion
