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
