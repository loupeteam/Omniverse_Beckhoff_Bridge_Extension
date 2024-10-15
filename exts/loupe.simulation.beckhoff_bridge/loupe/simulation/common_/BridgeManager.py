from abc import ABC, abstractmethod
from typing import Callable
import carb.events


class BridgeManager(ABC):
    @abstractmethod
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

    @abstractmethod
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

    @abstractmethod
    def add_cyclic_read_variables(self, variable_name_array: list[str]):
        """
        Adds variables to the cyclic read list.
        Variables in the cyclic read list are read from the Beckhoff Bridge at a fixed interval.

        Args:
            variableList (list): List of variables to be added. ["MAIN.myStruct.myvar1", "MAIN.var2", ...]

        Returns:
            None
        """

    @abstractmethod
    def write_variable(self, name: str, value: any):
        """
        Writes a variable value to the Beckhoff Bridge.

        Args:
            name (str): The name of the variable. "MAIN.myStruct.myvar1"
            value (basic type): The value to be written.  1, 2.5, "Hello", ...

        Returns:
            None
        """
