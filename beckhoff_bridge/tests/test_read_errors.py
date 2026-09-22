"""
read_data must not deliver pyads' per-symbol error texts as PLC values.
"""

import pytest

from beckhoff_bridge import AdsDriver, AdsReadError


class FakeConnection:
    def __init__(self, result):
        self.result = result
        self.is_open = True

    def read_list_by_name(self, names, structure_defs=None):
        assert list(names) == list(self.result)
        return dict(self.result)


@pytest.fixture
def driver():
    d = AdsDriver("1.2.3.4.1.1")
    d.set_read_names(["A.x", "A.arr[0]", "B"])
    return d


def test_partial_failure_is_reported_not_delivered(driver):
    driver._connection = FakeConnection({"A.x": 1.5, "A.arr[0]": "symbol not found", "B": True})
    assert driver.read_data() == {"A": {"x": 1.5}, "B": True}
    assert driver.last_read_errors == {"A.arr[0]": "symbol not found"}


def test_genuine_string_values_are_delivered(driver):
    driver._connection = FakeConnection({"A.x": "hello", "A.arr[0]": 2.0, "B": False})
    assert driver.read_data()["A"]["x"] == "hello"
    assert driver.last_read_errors == {}


def test_total_failure_raises(driver):
    driver._connection = FakeConnection({n: "symbol not found" for n in driver.read_names})
    with pytest.raises(AdsReadError) as info:
        driver.read_data()
    assert set(info.value.errors) == {"A.x", "A.arr[0]", "B"}


def test_empty_read_list_reads_nothing():
    d = AdsDriver("1.2.3.4.1.1")
    d._connection = None  # would blow up if read_list_by_name were called
    assert d.read_data() == {}


def test_set_read_names_strips_and_drops_blanks():
    d = AdsDriver("1.2.3.4.1.1")
    d.set_read_names([" GVL.a\r", "", "GVL.b", "GVL.a"])
    assert d.read_names == ["GVL.a", "GVL.b"]


def test_read_names_is_a_copy():
    d = AdsDriver("1.2.3.4.1.1")
    d.add_read("GVL.a")
    d.read_names.append("GVL.b")
    assert d.read_names == ["GVL.a"]


def test_disconnect_is_safe_when_not_connected():
    d = AdsDriver("1.2.3.4.1.1")
    d.disconnect()
    assert d.is_connected() is False


# region - plc_bridge driver contract

def test_driver_implements_the_contract():
    from plc_bridge import PlcDriver
    assert isinstance(AdsDriver("1.2.3.4.1.1"), PlcDriver)
    assert AdsDriver.symbol_separators == "."


def test_read_returns_flat_values_and_errors(driver):
    driver._connection = FakeConnection({"A.x": 1.5, "B": "symbol not found"})
    result = driver.read(["A.x", "B"])
    assert result.values == {"A.x": 1.5}
    assert result.errors == {"B": "symbol not found"}


def test_read_of_nothing_does_not_touch_the_connection():
    d = AdsDriver("1.2.3.4.1.1")
    result = d.read([])
    assert result.values == {} and result.errors == {}


def test_read_passes_only_the_struct_defs_it_needs():
    seen = {}

    class Conn:
        def read_list_by_name(self, names, structure_defs=None):
            seen["defs"] = structure_defs
            return {n: 0 for n in names}

    d = AdsDriver("1.2.3.4.1.1")
    d.add_read("A", structure_def=("a_def",))
    d.add_read("B", structure_def=("b_def",))
    d._connection = Conn()
    d.read(["B"])
    assert seen["defs"] == {"B": ("b_def",)}


def test_symbol_not_found_for_the_whole_read_names_the_symbols():
    import pyads

    class Conn:
        def read_list_by_name(self, names, structure_defs=None):
            raise pyads.ADSError(err_code=1808)

    d = AdsDriver("1.2.3.4.1.1")
    d._connection = Conn()
    with pytest.raises(pyads.ADSError) as info:
        d.read(["GVL.a", "GVL.b"])
    assert "GVL.a" in str(info.value) and "GVL.b" in str(info.value)


def test_write_goes_to_the_write_connection():
    written = []

    class Conn:
        def write_list_by_name(self, data):
            written.append(data)
            return {name: "no error" for name in data}

    d = AdsDriver("1.2.3.4.1.1")
    d._connection_write = Conn()
    assert d.write({"GVL.a": 1}) == {}
    d.write_data({"GVL.b": 2})
    assert written == [{"GVL.a": 1}, {"GVL.b": 2}]


def test_write_reports_the_symbols_the_plc_rejected():
    class Conn:
        def write_list_by_name(self, data):
            return {"GVL.a": "no error", "GVL.b": "symbol not found"}

    d = AdsDriver("1.2.3.4.1.1")
    d._connection_write = Conn()
    assert d.write({"GVL.a": 1, "GVL.b": 2}) == {"GVL.b": "symbol not found"}


def test_runtime_drives_the_ads_driver(driver):
    from plc_bridge import PlcRuntime

    driver.connect = lambda: None
    driver._connection = FakeConnection({"A.x": 1.5, "A.arr[0]": 2.0, "B": True})
    plc = PlcRuntime(driver, enabled=True)
    plc.set_read_variables(driver.read_names)
    driver.disconnect = lambda: None
    seen = []
    plc.on_data(seen.append)
    plc.scan_read()
    assert seen == [{"A": {"x": 1.5, "arr": [2.0]}, "B": True}]

# endregion


def test_transport_error_marks_the_link_lost_until_reconnect(monkeypatch):
    import pyads

    class Conn:
        is_open = True

        def read_list_by_name(self, names, structure_defs=None):
            raise pyads.ADSError(err_code=1861)  # timeout

    d = AdsDriver("1.2.3.4.1.1")
    d._connection = Conn()
    assert d.is_connected()
    with pytest.raises(pyads.ADSError):
        d.read(["GVL.a"])
    assert not d.is_connected()

    opened = []

    class FakePyadsConnection:
        def __init__(self, netid, port):
            opened.append(self)
            self.netid = netid
            self.is_open = True
            self.timeout = None
            self.closed = False

        def open(self):
            pass

        def close(self):
            self.closed = True

        def set_timeout(self, ms):
            self.timeout = ms

        def read_state(self):
            return (5, 0)

    monkeypatch.setattr(pyads, "Connection", FakePyadsConnection)
    d.connect()
    assert d.is_connected()
    assert [c.netid for c in opened] == ["1.2.3.4.1.1"] * 2
    assert d._connection.timeout == 1000 and d._connection_write.timeout == 1000


def test_connect_publishes_both_connections_at_once_and_cleans_up_on_failure(monkeypatch):
    import pyads

    opened = []

    class FakePyadsConnection:
        def __init__(self, netid, port):
            opened.append(self)
            self.closed = False
            self.is_open = True

        def open(self):
            pass

        def close(self):
            self.closed = True

        def set_timeout(self, ms):
            pass

        def read_state(self):
            raise pyads.ADSError(err_code=6)

    monkeypatch.setattr(pyads, "Connection", FakePyadsConnection)
    d = AdsDriver("1.2.3.4.1.1")
    with pytest.raises(pyads.ADSError):
        d.connect()
    # nothing half-built is left behind, and what was opened is closed again
    assert d._connection is None and d._connection_write is None
    assert len(opened) == 2 and all(c.closed for c in opened)
    assert not d.is_connected()


def test_disconnect_takes_the_connections_away_before_closing():
    order = []

    class Conn:
        def close(self):
            order.append(("closed", d._connection, d._connection_write))

    d = AdsDriver("1.2.3.4.1.1")
    d._connection, d._connection_write = Conn(), Conn()
    d.disconnect()
    assert order == [("closed", None, None)] * 2


def test_request_errors_do_not_mark_the_link_lost():
    import pyads

    class Conn:
        is_open = True

        def read_list_by_name(self, names, structure_defs=None):
            raise pyads.ADSError(err_code=1808)  # symbol not found

    d = AdsDriver("1.2.3.4.1.1")
    d._connection = Conn()
    with pytest.raises(pyads.ADSError):
        d.read(["GVL.a"])
    assert d.is_connected()


def test_transport_error_from_a_replaced_connection_is_ignored():
    """A write stuck on the old connection returns after the driver reconnected."""
    import pyads

    class Stale:
        is_open = False

        def write_list_by_name(self, data):
            raise pyads.ADSError(err_code=7)

    class Fresh:
        is_open = True

    d = AdsDriver("1.2.3.4.1.1")
    stale = Stale()
    d._connection_write = stale
    d._connection = Fresh()

    # the call goes out on the stale connection, then the driver is reconnected
    original = stale.write_list_by_name

    def write_then_reconnect(data):
        d._connection_write = Fresh()
        return original(data)

    stale.write_list_by_name = write_then_reconnect
    with pytest.raises(pyads.ADSError):
        d.write({"GVL.a": 1})
    assert d.is_connected()


def test_overlapping_connects_leave_one_pair_and_leak_nothing(monkeypatch):
    """A connect() on a worker the runtime gave up on finishes after a new one."""
    import pyads

    opened = []

    class FakePyadsConnection:
        def __init__(self, netid, port):
            opened.append(self)
            self.closed = False
            self.is_open = True

        def open(self):
            pass

        def close(self):
            self.closed = True

        def set_timeout(self, ms):
            pass

        def read_state(self):
            return (5, 0)

    monkeypatch.setattr(pyads, "Connection", FakePyadsConnection)
    d = AdsDriver("1.2.3.4.1.1")
    d.connect()
    first = (d._connection, d._connection_write)
    d.connect()  # the late one
    assert (d._connection, d._connection_write) == first
    assert len(opened) == 4
    assert [c.closed for c in opened] == [False, False, True, True]
    d.disconnect()
    assert all(c.closed for c in opened)
    assert not d.is_connected()
