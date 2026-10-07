"""
  File: **driver.py**
  Copyright (c) 2024 Loupe
  https://loupe.team

  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

  The ADS driver. Plain Python: nothing here may import from Omniverse or Kit.
"""

import threading

import pyads
from pyads.errorcodes import ERROR_CODES

from plc_bridge import PlcDriver, ReadResult, nest_symbol

# ADS error code for "symbol not found"
_ADS_SYMBOL_NOT_FOUND = 1808
# ADS errors that mean the link to the PLC is gone rather than the request
# being wrong: target port / machine not found, port disabled, timeout, port
# not opened. After one of these is_connected() reports False until connect().
_ADS_TRANSPORT_ERRORS = frozenset({6, 7, 18, 1861, 1864})
# pyads' default request timeout is 5 s, longer than the runtime waits for a
# worker on stop(). ADS cannot abort a request in flight, so keep it short.
ADS_TIMEOUT_MS = 1000
# What pyads' sum write reports for a symbol that was written
_ADS_NO_ERROR = ERROR_CODES[0]

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


def _close_all(connections):
    for connection in connections:
        if connection is None:
            continue
        try:
            connection.close()
        except Exception:  # noqa
            pass


class AdsDriver(PlcDriver):
    """
    An ADS client for one PLC, implementing the plc_bridge driver contract
    (connect / disconnect / is_connected / read / write).

    It opens two ADS connections, one for reads and one for writes, so the
    runtime's read and write threads never share one. Both carry a one-second
    request timeout (ADS_TIMEOUT_MS) because ADS cannot abort a request in
    flight. pyads' `is_open` only says whether we opened the port, so a
    transport-class ADS error on a read or write marks the link lost and
    is_connected() reports False until the next connect().

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
        # Guards publishing and taking away the connection pair: connect() on a
        # worker the runtime gave up on may overlap connect() or disconnect()
        # on another thread.
        self._publish_lock = threading.Lock()
        # The AMS Net Id the published pair was opened for
        self._published_net_id = None
        self._transport_lost = False
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
        connection = self._connection
        try:
            data = connection.read_list_by_name(symbols, structure_defs=structure_defs)
        except pyads.ADSError as e:
            self._note_transport(connection, e)
            if getattr(e, "err_code", None) == _ADS_SYMBOL_NOT_FOUND:
                raise pyads.ADSError(text=f"{e}; one of: {symbols}") from e
            raise
        for name, value in data.items():
            if isinstance(value, str) and value in _ADS_ERROR_TEXTS:
                result.errors[name] = value
            else:
                result.values[name] = value
        return result

    def write(self, values) -> dict:
        """
        Write flat symbol -> value in one ADS sum write, e.g.
        {'MAIN.b_Execute': False, 'MAIN.r32_TestReal': 54.321}

        Returns:
            symbol -> ADS error text for each symbol the PLC rejected; empty when
            all succeeded. pyads reports "no error" per symbol on success.
        """
        connection = self._connection_write
        try:
            results = connection.write_list_by_name(dict(values)) or {}
        except pyads.ADSError as e:
            self._note_transport(connection, e)
            raise
        return {name: text for name, text in results.items() if text != _ADS_NO_ERROR}

    def _note_transport(self, connection, error):
        """
        Mark the link lost on a transport-class error, but only if it came from
        a connection we still hold: a request that was in flight on a connection
        disconnect() has since replaced says nothing about the current one.
        """
        if getattr(error, "err_code", None) not in _ADS_TRANSPORT_ERRORS:
            return
        if connection is self._connection or connection is self._connection_write:
            self._transport_lost = True

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

        # Build both connections in locals and publish them together at the
        # end: a disconnect() from another thread while this runs (the runtime
        # gave up waiting for us) then finds either nothing or a complete pair,
        # never a half-built one.
        net_id = self.ams_net_id
        opened = []
        try:
            for _ in range(2):
                connection = pyads.Connection(net_id, pyads.PORT_TC3PLC1)
                connection.open()
                opened.append(connection)
                connection.set_timeout(ADS_TIMEOUT_MS)
            adsState, deviceState = opened[0].read_state()
        except Exception:
            _close_all(opened)
            raise
        with self._publish_lock:
            if net_id != self.ams_net_id:
                # The target changed while we were connecting (a worker the
                # runtime gave up on, finishing after the address was edited).
                # A pair to the old PLC must never replace one to the new.
                _close_all(opened)
                raise ConnectionError(
                    f"AMS Net Id changed to {self.ams_net_id} while connecting to {net_id}")
            if (self._connection is not None and not self._transport_lost
                    and self._published_net_id == net_id):
                # Another connect() to the same PLC got here first (a worker the
                # runtime gave up on, still inside connect()). One working pair
                # is enough; keep the one in use and close ours. A second
                # connect() without a disconnect() is therefore a no-op.
                _close_all(opened)
                return
            # Nothing published, a pair marked lost, or a pair to a different
            # PLC: ours replaces it.
            stale = (self._connection, self._connection_write)
            self._transport_lost = False
            self._connection, self._connection_write = opened
            self._published_net_id = net_id
        _close_all(stale)

    def disconnect(self):
        """
        Disconnects from the target device, closing both the read and the write
        connection. Safe to call when not connected.

        """
        # Take the connections away first, then close them, so a read or write
        # on another thread sees None (and fails cleanly) rather than a port
        # that is being closed under it.
        with self._publish_lock:
            connections = (self._connection, self._connection_write)
            self._connection = None
            self._connection_write = None
            self._published_net_id = None
        _close_all(connections)

    def is_connected(self) -> bool:
        """
        Returns the connection state.

        Returns:
            bool: True if the connection is open, False otherwise.

        """
        try:
            if self._connection is None or self._transport_lost:
                return False
            return self._connection.is_open
        except Exception:
            return False

    # endregion
