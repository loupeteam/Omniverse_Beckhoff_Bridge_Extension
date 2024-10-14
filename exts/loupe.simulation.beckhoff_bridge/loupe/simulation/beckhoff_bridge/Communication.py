"""
  File: **ads_driver.py**
  Copyright (c) 2024 Loupe
  https://loupe.team
  
  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.
  
"""

import pyads
import re


class CommunicationDriver:
    """
    A class that represents an ADS driver. It contains a list of variables to read from the target device and provides methods to read and write data.

    Args:
        ams_net_id (str): The AMS Net ID of the target device.

    Attributes:
        ams_net_id (str): The AMS Net ID of the target device.
        _read_names (list): A list of names for reading data.
        _read_struct_def (dict): A dictionary that maps names to structure definitions.

    """

    def __init__(self, ams_net_id):
        """
        Initializes an instance of the AdsDriver class.

        Args:
            ams_net_id (str): The AMS Net ID of the target device.

        """
        self.ams_net_id = ams_net_id
        self._read_names = list()
        self._read_struct_def = dict()
        self._connection = None
        self._connection_write = None

    def add_read(self, name: str, structure_def=None):
        """
        Adds a variable to the list of data to read.

        Args:
            name (str): The name of the data to be read. "my_struct.my_array[0].my_var"
            structure_def (optional): The structure definition of the data.

        """
        if name not in self._read_names:
            self._read_names.append(name)

        if structure_def is not None:
            if name not in self._read_struct_def:
                self._read_struct_def[name] = structure_def

    def write_data(self, data: dict):
        """
        Writes data to the target device.

        Args:
            data (dict): A dictionary containing the data to be written to the PLC
            e.g.
            data = {'MAIN.b_Execute': False, 'MAIN.str_TestString': 'Goodbye World', 'MAIN.r32_TestReal': 54.321}

        """
        self._connection_write.write_list_by_name(data)

    def read_data(self):
        """
        Reads all variables from the cyclic read list.

        Returns:
            dict: A dictionary containing the parsed data.

        """
        if self._read_names.__len__() > 0:
            data = self._connection.read_list_by_name(
                self._read_names, structure_defs=self._read_struct_def
            )
            parsed_data = dict()
            for name in data.keys():
                parsed_data = self._parse_flat_plc_var_to_dict(
                    parsed_data, name, data[name]
                )
        else:
            parsed_data = dict()
        return parsed_data

    def _ensure_list_with_index_in_dict(self, list_name, _dict, _index):
        """
        Ensure that dictionary has a key of list_name, that it's value is a list,
        and that the list is long enough to include the index
        """

        # Create list if not in dict
        if list_name not in _dict or not isinstance(_dict[list_name], list):
            _dict[list_name] = []

        # Extend list if not long enough
        if _index >= len(_dict[list_name]):
            _dict[list_name].extend([None] * (_index - len(_dict[list_name]) + 1))

    def _parse_flat_plc_var_to_dict(self, plc_var_dict, plc_var, value):
        """
        Convert a flat, string representation of a PLC var into a dictionary.

        This function uses recursion to build up the complete dictionary of PLC variables, and values.

        This is performed every read, rather than being cached, to not assume PLC variable values
        to be at their previous value if they are not being actively read. Caching can be
        performed in the usage of this library if necessary.

        Args:
            plc_var_dict (dict): The dictionary to write the value into
            plc_var (str): The variable name in flattened string form ("Program:myStruct.myVar")
            value (any): The value to write to the dictionary entry
        """

        name_parts = re.split("[.]", plc_var)

        if len(name_parts) > 1:
            # Multiple parts in passed-in plc_var (e.g. Program:myStruct[3].myVar has 3 parts)
            # From here we want to use recursion to assign a dictionary value (i.e. sub dictionary) to the first part.

            first_part_is_array = "[" in name_parts[0]

            ## Get pre-existing subdictionary (or create if necessary)
            if first_part_is_array:
                array_name, array_index = name_parts[0].split("[")
                array_index = int(array_index[:-1])

                # Ensure array is in dictionary and is long enough
                self._ensure_list_with_index_in_dict(
                    array_name, plc_var_dict, array_index
                )

                # Ensure array index location has dict-typed value
                if not isinstance(plc_var_dict[array_name][array_index], dict):
                    plc_var_dict[array_name][array_index] = {}

                existing_sub_dict = plc_var_dict[array_name][array_index]
            else:
                member_plc_var = name_parts[0]

                ## Ensure corresponding subdictionary exists
                if member_plc_var not in plc_var_dict or not isinstance(
                    plc_var_dict[member_plc_var], dict
                ):
                    plc_var_dict[member_plc_var] = {}

                existing_sub_dict = plc_var_dict[member_plc_var]

            # Get subdictionary from using remaining part of path
            sub_plc_var = ".".join(name_parts[1:])
            sub_dict = self._parse_flat_plc_var_to_dict(
                existing_sub_dict, sub_plc_var, value
            )

            # Assign result of recursive call (subdictionary) to first part
            if first_part_is_array:
                plc_var_dict[array_name][array_index] = sub_dict
            else:
                plc_var_dict[member_plc_var] = sub_dict
        else:
            # Only one part in passed-in plc_var
            # Proceed to assign value

            if "[" in name_parts[0]:
                array_name, array_index = name_parts[0].split("[")
                array_index = int(array_index[:-1])

                # Ensure array is in dictionary and is long enough
                self._ensure_list_with_index_in_dict(
                    array_name, plc_var_dict, array_index
                )

                plc_var_dict[array_name][array_index] = value
            else:
                # Write value (regardless of whether it exists or not)
                plc_var_dict[name_parts[0]] = value

        return plc_var_dict

    def connect(self, ams_net_id=None):
        """
        Connects to the target device.

        Args:
            ams_net_id (str): The AMS Net ID of the target device. This does not need to be provided if it was provided in the constructor and has not changed.

        """
        if ams_net_id is not None:
            self.ams_net_id = ams_net_id

        self._connection = pyads.Connection(self.ams_net_id, pyads.PORT_TC3PLC1)
        self._connection.open()
        adsState, deviceState = self._connection.read_state()

        self._connection_write = pyads.Connection(self.ams_net_id, pyads.PORT_TC3PLC1)
        self._connection_write.open()

    def disconnect(self):
        """
        Disconnects from the target device.

        """
        self._connection = None

    def is_connected(self):
        """
        Returns the connection state.

        Returns:
            bool: True if the connection is open, False otherwise.

        """
        try:
            if self._connection is None:
                return False
            return self._connection.is_open
        except Exception as e:
            return False
