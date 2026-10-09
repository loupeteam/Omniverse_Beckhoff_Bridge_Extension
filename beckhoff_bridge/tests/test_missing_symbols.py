"""
A symbol the PLC does not know (ADS 1808) must not take the others down.

pyads looks every name up before a sum read or write, and an unknown name
makes it raise for the whole request. The driver finds the unknown names one
by one, reports them as errors (read) or rejections (write), remembers them
for the connection and keeps reading and writing the rest.
"""

import pyads
import pytest

import beckhoff_bridge.driver as drv
from beckhoff_bridge import AdsDriver
from plc_bridge import PlcRuntime, PROBLEM_READ, PROBLEM_WRITE

NOT_FOUND = "symbol not found"


class PlcConnection:
    """A fake pyads.Connection over a dict of the symbols the PLC knows."""

    def __init__(self, known: dict):
        self.known = dict(known)
        self.is_open = True
        self.reads = []
        self.writes = []
        self.lookups = []
        self.released = []

    def _check(self, names):
        if any(n not in self.known for n in names):
            raise pyads.ADSError(err_code=1808)

    def read_list_by_name(self, names, structure_defs=None):
        names = list(names)
        self.reads.append(names)
        self._check(names)
        return {n: self.known[n] for n in names}

    def write_list_by_name(self, values):
        self.writes.append(dict(values))
        self._check(values)
        self.known.update(values)
        return {n: "no error" for n in values}

    def get_handle(self, name):
        self.lookups.append(name)
        if name not in self.known:
            raise pyads.ADSError(err_code=1808)
        return 1000 + len(self.lookups)

    def release_handle(self, handle):
        self.released.append(handle)


@pytest.fixture
def plc():
    return PlcConnection({"GVL.a": 1, "GVL.b": 2.5, "GVL.c": True})


@pytest.fixture
def driver(plc):
    d = AdsDriver("1.2.3.4.1.1")
    d._connection = plc
    return d


def test_read_reports_the_unknown_symbol_and_delivers_the_rest(driver, plc):
    result = driver.read(["GVL.a", "GVL.bad", "GVL.b"])
    assert result.values == {"GVL.a": 1, "GVL.b": 2.5}
    assert result.errors == {"GVL.bad": NOT_FOUND}
    # one failed sum read, one lookup per name, one sum read of the good ones
    assert plc.reads == [["GVL.a", "GVL.bad", "GVL.b"], ["GVL.a", "GVL.b"]]
    assert sorted(plc.lookups) == ["GVL.a", "GVL.b", "GVL.bad"]
    assert len(plc.released) == 2  # every handle that was opened is released


def test_the_lookup_is_not_repeated_every_scan(driver, plc):
    driver.read(["GVL.a", "GVL.bad"])
    plc.reads.clear()
    plc.lookups.clear()
    for _ in range(5):
        result = driver.read(["GVL.a", "GVL.bad"])
        assert result.values == {"GVL.a": 1} and result.errors == {"GVL.bad": NOT_FOUND}
    assert plc.reads == [["GVL.a"]] * 5
    assert plc.lookups == []


def test_a_missing_symbol_is_looked_up_again_after_the_recheck_interval(driver, plc, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(drv.time, "monotonic", lambda: clock[0])
    driver.read(["GVL.a", "GVL.new"])
    plc.lookups.clear()
    clock[0] += drv.MISSING_RECHECK_SEC - 1
    assert driver.read(["GVL.a", "GVL.new"]).errors == {"GVL.new": NOT_FOUND}
    assert plc.lookups == []
    # an online change adds the symbol
    plc.known["GVL.new"] = 7
    clock[0] += 2
    result = driver.read(["GVL.a", "GVL.new"])
    assert plc.lookups == ["GVL.new"]
    assert result.values == {"GVL.a": 1, "GVL.new": 7} and result.errors == {}


def test_a_new_connection_starts_over(driver, plc):
    driver.read(["GVL.a", "GVL.bad"])
    fresh = PlcConnection(dict(plc.known, **{"GVL.bad": 3}))
    driver._connection = fresh
    result = driver.read(["GVL.a", "GVL.bad"])
    assert result.values == {"GVL.a": 1, "GVL.bad": 3} and result.errors == {}
    assert fresh.lookups == []  # nothing remembered from the old connection


def test_every_symbol_missing_gives_errors_and_no_values(driver, plc):
    result = driver.read(["X.a", "X.b"])
    assert result.values == {}
    assert result.errors == {"X.a": NOT_FOUND, "X.b": NOT_FOUND}
    assert plc.reads == [["X.a", "X.b"]]  # nothing left to read after the lookups


def test_read_data_keeps_the_0_2_api(driver):
    driver.set_read_names(["GVL.a", "GVL.bad"])
    assert driver.read_data() == {"GVL": {"a": 1}}
    assert driver.last_read_errors == {"GVL.bad": NOT_FOUND}


def test_a_lookup_that_fails_for_another_reason_raises(driver, plc):
    def broken(name):
        raise pyads.ADSError(err_code=1861)  # timeout: the link, not the name

    plc.get_handle = broken
    with pytest.raises(pyads.ADSError):
        driver.read(["GVL.a", "GVL.bad"])
    assert not driver.is_connected()  # a transport error marks the link lost


def test_write_rejects_the_unknown_symbol_and_writes_the_rest(driver, plc):
    rejected = driver.write({"GVL.a": 5, "GVL.bad": 1, "GVL.b": 0.5})
    assert rejected == {"GVL.bad": NOT_FOUND}
    assert plc.known["GVL.a"] == 5 and plc.known["GVL.b"] == 0.5
    assert plc.writes[-1] == {"GVL.a": 5, "GVL.b": 0.5}


def test_write_of_a_known_missing_symbol_costs_no_round_trip(driver, plc):
    driver.read(["GVL.a", "GVL.bad"])
    plc.writes.clear()
    plc.lookups.clear()
    assert driver.write({"GVL.bad": 1}) == {"GVL.bad": NOT_FOUND}
    assert plc.writes == [] and plc.lookups == []
    assert driver.write({"GVL.bad": 1, "GVL.c": False}) == {"GVL.bad": NOT_FOUND}
    assert plc.writes == [{"GVL.c": False}]


def test_runtime_keeps_good_symbols_flowing_and_reports_the_bad_one(driver):
    runtime = PlcRuntime(driver, name="T", enabled=True)
    runtime.set_read_variables(["GVL.a", "GVL.bad", "GVL.b"])
    driver.connect = lambda: None  # the fake connection is already in place
    driver.disconnect = lambda: None
    problems = []
    runtime.on_problem(problems.append)
    for _ in range(3):
        runtime.scan()
    sample = runtime.latest()
    assert sample.seq == 3
    assert sample.values == {"GVL.a": 1, "GVL.b": 2.5}
    assert sample.errors == {"GVL.bad": NOT_FOUND}
    read = [p for p in problems if p.kind == PROBLEM_READ]
    assert len(read) == 1  # reported once, not every scan
    assert read[0].symbols == ("GVL.bad",)
    assert read[0].text == "Error Reading: GVL.bad: symbol not found"

    handle = runtime.queue_write("GVL.bad", 1)
    good = runtime.queue_write("GVL.c", False)
    runtime.scan()
    assert handle.error == NOT_FOUND and good.ok
    assert [p.symbols for p in problems if p.kind == PROBLEM_WRITE] == [("GVL.bad",)]
