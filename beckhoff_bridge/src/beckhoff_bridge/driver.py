"""
  File: **driver.py**
  Copyright (c) 2024 Loupe
  https://loupe.team

  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

  The ADS driver. Plain Python: nothing here may import from Omniverse or Kit.
"""

import threading
import time

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
_ADS_SYMBOL_NOT_FOUND_TEXT = ERROR_CODES[_ADS_SYMBOL_NOT_FOUND]
# A symbol found missing is left out of the sum read and write and reported
# as an error without a round trip; after this long it is looked up again, so
# one that an online change or a new download adds is picked up.
MISSING_RECHECK_SEC = 10.0

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

    One ADS connection: the runtime calls read and write from one thread, in
    turn. It carries a one-second request timeout (ADS_TIMEOUT_MS) because ADS
    cannot abort a request in flight. pyads' `is_open` only says whether we
    opened the port, so a transport-class ADS error on a read or write marks
    the link lost and is_connected() reports False until the next connect().

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
        # Guards publishing and taking away the connection: connect() on a
        # worker the runtime gave up on may overlap connect() or disconnect()
        # on another thread.
        self._publish_lock = threading.Lock()
        # The AMS Net Id the published pair was opened for
        self._published_net_id = None
        self._transport_lost = False
        self.last_read_errors = dict()
        # Symbols the PLC does not know: name -> monotonic time of the lookup
        # that said so. Only valid for the connection they were looked up on.
        self._missing = dict()
        self._missing_connection = None

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

        Two ways a symbol can fail, both reported in ReadResult.errors while
        the other symbols are delivered:

        * pyads puts the ADS error text in the symbol's slot of a sum read
          that went through.
        * pyads looks each name up before the sum read, and an unknown name
          (ADS 1808, "symbol not found") fails the whole request. The names
          are then looked up one by one, the unknown ones are remembered for
          this connection and left out, and the rest is read. A remembered
          name costs no round trip; it is looked up again after
          MISSING_RECHECK_SEC.
        """
        result = ReadResult()
        symbols = list(symbols)
        if not symbols:
            return result
        connection = self._require_connection()
        missing = self._known_missing(connection, symbols)
        wanted = [s for s in symbols if s not in missing]
        data = {}
        if wanted:
            try:
                data = self._read_list(connection, wanted)
            except pyads.ADSError as e:
                if getattr(e, "err_code", None) != _ADS_SYMBOL_NOT_FOUND:
                    raise
                found = self._find_missing(connection, wanted)
                if not found:
                    # Every name looks up fine on its own: nothing to leave out.
                    raise pyads.ADSError(text=f"{e}; one of: {symbols}") from e
                missing.update(found)
                wanted = [s for s in wanted if s not in found]
                if wanted:
                    data = self._read_list(connection, wanted)
        result.errors.update(missing)
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

        A symbol the PLC does not know (ADS 1808, which pyads raises for the
        whole request) is rejected and the others are written, as for read.

        Returns:
            symbol -> ADS error text for each symbol the PLC rejected; empty when
            all succeeded. pyads reports "no error" per symbol on success.
        """
        values = dict(values)
        if not values:
            return {}
        connection = self._require_connection()
        rejected = self._known_missing(connection, values)
        good = {name: value for name, value in values.items() if name not in rejected}
        if not good:
            return rejected
        try:
            results = self._write_list(connection, good)
        except pyads.ADSError as e:
            if getattr(e, "err_code", None) != _ADS_SYMBOL_NOT_FOUND:
                raise
            found = self._find_missing(connection, list(good))
            if not found:
                raise
            rejected.update(found)
            good = {name: value for name, value in good.items() if name not in found}
            results = self._write_list(connection, good) if good else {}
        rejected.update({name: text for name, text in results.items() if text != _ADS_NO_ERROR})
        return rejected

    # endregion
    # region - Requests

    def _require_connection(self):
        connection = self._connection
        if connection is None:
            raise ConnectionError(f"not connected to {self.ams_net_id}")
        return connection

    def _read_list(self, connection, symbols):
        structure_defs = {k: v for k, v in self._read_struct_def.items() if k in symbols}
        try:
            return connection.read_list_by_name(symbols, structure_defs=structure_defs)
        except pyads.ADSError as e:
            self._note_transport(connection, e)
            raise

    def _write_list(self, connection, values):
        try:
            return connection.write_list_by_name(values) or {}
        except pyads.ADSError as e:
            self._note_transport(connection, e)
            raise

    def _known_missing(self, connection, symbols) -> dict:
        """
        The symbols among `symbols` already known to be missing on this
        connection, name -> error text. Entries older than MISSING_RECHECK_SEC
        are looked up again first.
        """
        if connection is not self._missing_connection:
            # A new connection (the PLC may run a new program): start over.
            self._missing = dict()
            self._missing_connection = connection
        now = time.monotonic()
        due = [s for s in symbols if s in self._missing and now - self._missing[s] >= MISSING_RECHECK_SEC]
        if due:
            self._find_missing(connection, due)
        return {s: _ADS_SYMBOL_NOT_FOUND_TEXT for s in symbols if s in self._missing}

    def _find_missing(self, connection, symbols) -> dict:
        """
        Look each symbol up on its own (an ADS handle by name, released at
        once) and remember those the PLC does not know.

        Returns:
            name -> error text for the symbols that are missing.

        Raises:
            pyads.ADSError: any error other than "symbol not found" (the link
            is gone, a timeout), after marking a transport error.
        """
        found = {}
        now = time.monotonic()
        for symbol in symbols:
            try:
                handle = connection.get_handle(symbol)
            except pyads.ADSError as e:
                if getattr(e, "err_code", None) == _ADS_SYMBOL_NOT_FOUND:
                    self._missing[symbol] = now
                    found[symbol] = _ADS_SYMBOL_NOT_FOUND_TEXT
                    continue
                self._note_transport(connection, e)
                raise
            self._missing.pop(symbol, None)
            try:
                connection.release_handle(handle)
            except pyads.ADSError as e:
                self._note_transport(connection, e)
        return found

    def _note_transport(self, connection, error):
        """
        Mark the link lost on a transport-class error, but only if it came from
        a connection we still hold: a request that was in flight on a connection
        disconnect() has since replaced says nothing about the current one.
        """
        if getattr(error, "err_code", None) not in _ADS_TRANSPORT_ERRORS:
            return
        if connection is self._connection:
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

        # Build the connection in a local and publish it at the end: a
        # disconnect() from another thread while this runs (the runtime gave
        # up waiting for us) then finds either nothing or a working connection,
        # never a half-built one.
        net_id = self.ams_net_id
        connection = pyads.Connection(net_id, pyads.PORT_TC3PLC1)
        try:
            connection.open()
            connection.set_timeout(ADS_TIMEOUT_MS)
            adsState, deviceState = connection.read_state()
        except Exception:
            _close_all([connection])
            raise
        with self._publish_lock:
            if net_id != self.ams_net_id:
                # The target changed while we were connecting (a worker the
                # runtime gave up on, finishing after the address was edited).
                # A connection to the old PLC must never replace one to the new.
                _close_all([connection])
                raise ConnectionError(
                    f"AMS Net Id changed to {self.ams_net_id} while connecting to {net_id}")
            if (self._connection is not None and not self._transport_lost
                    and self._published_net_id == net_id):
                # Another connect() to the same PLC got here first (a worker the
                # runtime gave up on, still inside connect()). One working
                # connection is enough; keep the one in use and close ours. A
                # second connect() without a disconnect() is therefore a no-op.
                _close_all([connection])
                return
            # Nothing published, a connection marked lost, or one to a
            # different PLC: ours replaces it.
            stale = self._connection
            self._transport_lost = False
            self._connection = connection
            self._published_net_id = net_id
        _close_all([stale])

    def disconnect(self):
        """
        Disconnects from the target device. Safe to call when not connected.

        """
        # Take the connections away first, then close them, so a read or write
        # on another thread sees None (and fails cleanly) rather than a port
        # that is being closed under it.
        with self._publish_lock:
            connection = self._connection
            self._connection = None
            self._published_net_id = None
        _close_all([connection])

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
