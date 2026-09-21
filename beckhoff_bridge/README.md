# beckhoff_bridge

The Beckhoff ADS driver used by the `loupe.simulation.beckhoff_bridge` Omniverse
extension, as a plain Python package. It imports nothing from Omniverse or Kit.
It depends on [pyads](https://github.com/stlehmann/pyads) and on `plc_bridge`,
the vendor-neutral runtime and driver contract from
[Omni-Utils](https://github.com/loupeteam/Omni-Utils).

`AdsDriver` implements the `plc_bridge.PlcDriver` contract, so it is
interchangeable with any other vendor's driver. See
[docs/ARCHITECTURE_PLAN.md](../docs/ARCHITECTURE_PLAN.md) for the layering.

## Usage with the polling runtime

```python
from plc_bridge import PlcRuntime
from beckhoff_bridge import AdsDriver

plc = PlcRuntime(AdsDriver("10.20.30.40.1.1"), refresh_ms=20, enabled=True)
plc.set_read_variables(["GVL.Axes[0].ActualPosition"])
plc.on_data(print)      # {"GVL": {"Axes": [{"ActualPosition": 1.5}]}}
plc.on_status(print)    # "Error Reading: GVL.x: symbol not found", "Reading OK", ...
plc.start()
```

Swapping to another vendor changes only the driver import and its arguments.

## Usage of the driver alone

```python
from beckhoff_bridge import AdsDriver, AdsReadError

plc = AdsDriver("10.20.30.40.1.1")
plc.set_read_names(["GVL.Axes[0].ActualPosition", "GVL.Command.Blend"])
plc.connect()

data = plc.read_data()        # {"GVL": {"Axes": [{"ActualPosition": 1.5}], "Command": {"Blend": 0.0}}}
plc.last_read_errors          # {} or {"GVL.Command.Blend": "symbol not found"}

plc.write_data({"GVL.Command.Blend": 1.0})
plc.disconnect()
```

`read_data` reads every name in one ADS sum read and returns a nested dict:
`a.b.c` becomes nested dicts, `arr[2]` becomes a list padded with `None`.
A symbol the PLC rejects is left out of the result and reported in
`last_read_errors`. When every symbol fails, `read_data` raises `AdsReadError`.

## Tests

```bash
pip install -e ../exts/loupe.simulation.beckhoff_bridge/loupe/simulation/common/plc_bridge
pip install -e .[test]
pytest
```

The tests use a fake connection and do not need a PLC or the TwinCAT router.

## Development in the extension repo

The extension loads this package and `plc_bridge` straight from the repo (see
the `[[python.module]]` entries in the extension's `config/extension.toml`), so
no install step is needed when working on them together. `plc_bridge` is not on
PyPI yet, hence the path install above.
