"""
  File: **driver.py**
  Copyright (c) 2024 Loupe
  https://loupe.team

  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

  The ADS driver. Plain Python: nothing here may import from Omniverse or Kit.
"""

import pyads
from pyads.errorcodes import ERROR_CODES

from plc_bridge import PlcDriver, ReadResult, nest_symbol

# ADS error code for "symbol not found"
_ADS_SYMBOL_NOT_FOUND = 1808

# pyads.Connection.read_list_by_name does not raise when one symbol of a sum read
# fails: it puts the ADS error text (e.g. "symbol not found") in that symbol's slot.
# Delivered as data, that string would be mirrored, compared and written back as if
# it were the PLC value. Recognise those strings and report them separately.
_ADS_ERROR_TEXTS = frozenset(ERROR_CODES.values())


class AdsReadError(Exception):
    """
    Raised by AdsDriver.read_data when every requested symbol failed.

    Attributes:
        errors (dict): symbol name -> ADS error text.
    """

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__("ADS read failed for all {} symbol(s): {}".format(
            len(errors), "; ".join("{}: {}".format(k, v) for k, v in errors.items())))


def parse_flat_plc_var_to_dict(plc_var_dict: dict, plc_var: str, value) -> dict:
    """
    Write one flat symbol ("GVL.myStruct[3].myVar") into a nested dict, in place.
    0.2.x name of plc_bridge.nest_symbol, which both vendor bridges now share.
    """
    return nest_symbol(plc_var_dict, plc_var, value, AdsDriver.symbol_separators)


class AdsDriver(PlcDriver):
    """
    An ADS client for one PLC, implementing the plc_bridge driver contract
    (connect / disconnect / is_connected / read / write).

    It opens two ADS connections, one for reads and one for writes, so the
    runtime's read and write threads never share one.

    The read-list methods (add_read, set_read_names, read_data, write_data) are
    the 0.2.x API, kept for code that drives the driver without a PlcRuntime.

    Args:
        ams_net_id (str): The AMS Net ID of the target device.

    Attributes:
        ams_net_id (str): The AMS Net ID of the target device.
        last_read_errors (dict): Per-symbol ADS errors from the last read_data() call,
            symbol name -> error text.
    """

    symbol_separators = "."

    def __init__(self, ams_net_id: str):
        self.ams_net_id = ams_net_id
        self._read_names = list()
        self._read_struct_def = dict()
        self._connection = None
        self._connection_write = None
        self.last_read_errors = dict()

    # region - Read list

    @property
    def read_names(self) -> list:
        """The symbols read by read_data, in order. A copy; use add_read / set_read_names to change it."""
        return list(self._read_names)

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

    def set_read_names(self, names):
        """
        Replace the cyclic read list. Blank entries are dropped and whitespace
        (including the '\\r' a Windows multiline field leaves behind) is stripped,
        since ADS reports a padded name as "symbol not found".
        """
        self._read_names = []
        for name in names:
            name = name.strip()
            if name:
                self.add_read(name)

    # endregion
    # region - Data

    def read(self, symbols) -> ReadResult:
        """
        Read the symbols in one ADS sum read.

        pyads does not raise when one symbol of a sum read fails: it puts the ADS
        error text (e.g. "symbol not found") in that symbol's slot. Those go to
        ReadResult.errors instead of being delivered as the PLC value.
        """
        result = ReadResult()
        symbols = list(symbols)
        if not symbols:
            return result
        structure_defs = {k: v for k, v in self._read_struct_def.items() if k in symbols}
        try:
            data = self._connection.read_list_by_name(symbols, structure_defs=structure_defs)
        except pyads.ADSError as e:
            if getattr(e, "err_code", None) == _ADS_SYMBOL_NOT_FOUND:
                raise pyads.ADSError(text=f"{e}; one of: {symbols}") from e
            raise
        for name, value in data.items():
            if isinstance(value, str) and value in _ADS_ERROR_TEXTS:
                result.errors[name] = value
            else:
                result.values[name] = value
        return result

    def write(self, values):
        """
        Write flat symbol -> value in one ADS sum write, e.g.
        {'MAIN.b_Execute': False, 'MAIN.r32_TestReal': 54.321}
        """
        self._connection_write.write_list_by_name(dict(values))

    def write_data(self, data: dict):
        """0.2.x name of write."""
        self.write(data)

    def read_data(self) -> dict:
        """
        Reads all variables from the cyclic read list (0.2.x API).

        Returns:
            dict: The nested data. Symbols whose read failed are left out; their
            error texts are in last_read_errors.

        Raises:
            AdsReadError: when every requested symbol failed (the PLC is gone or
            has no program), so the caller can report a read error.

        """
        result = self.read(self._read_names)
        parsed_data = dict()
        for name, value in result.values.items():
            parse_flat_plc_var_to_dict(parsed_data, name, value)
        self.last_read_errors = result.errors
        if result.errors and not parsed_data:
            raise AdsReadError(result.errors)
        return parsed_data

    def _parse_flat_plc_var_to_dict(self, plc_var_dict, plc_var, value):
        """0.2.x name of parse_flat_plc_var_to_dict, kept for callers and tests."""
        return parse_flat_plc_var_to_dict(plc_var_dict, plc_var, value)

    # endregion
    # region - Connection

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
        Disconnects from the target device, closing both the read and the write
        connection. Safe to call when not connected.

        """
        for connection in (self._connection, self._connection_write):
            if connection is None:
                continue
            try:
                connection.close()
            except Exception:  # noqa
                pass
        self._connection = None
        self._connection_write = None

    def is_connected(self) -> bool:
        """
        Returns the connection state.

        Returns:
            bool: True if the connection is open, False otherwise.

        """
        try:
            if self._connection is None:
                return False
            return self._connection.is_open
        except Exception:
            return False

    # endregion
