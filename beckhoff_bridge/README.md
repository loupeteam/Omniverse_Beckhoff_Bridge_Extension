# beckhoff_bridge

The Beckhoff ADS driver used by the `loupe.simulation.beckhoff_bridge` Omniverse
extension, as a plain Python package. It imports nothing from Omniverse or Kit;
its only dependency is [pyads](https://github.com/stlehmann/pyads).

This is the first piece of the layering described in
[docs/ARCHITECTURE_PLAN.md](../docs/ARCHITECTURE_PLAN.md): the vendor library
that a future vendor-neutral runtime will drive. For now the extension's
`Runtime` drives it directly.

## Usage

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
pip install -e .[test]
pytest
```

The tests use a fake connection and do not need a PLC or the TwinCAT router.

## Development in the extension repo

The extension loads this package straight from the repo (see
`[[python.module]]` in the extension's `config/extension.toml`), so no install
step is needed when working on both together.
