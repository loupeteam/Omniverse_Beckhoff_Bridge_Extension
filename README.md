# Info
This tool is provided by Loupe.  
https://loupe.team  
info@loupe.team  
1-800-240-7042

# Description

This is an extension that connects Beckhoff PLCs into the Omniverse ecosystem. It leverages [pyads](https://github.com/stlehmann/pyads) to set up an ADS client for communicating with PLCs.

Since 0.3.0 the extension is a driver for the vendor-neutral PLC Bridge framework, the Kit extension `loupe.simulation.bridge` from [Omni-Utils](https://github.com/loupeteam/Omni-Utils), which it depends on. The framework owns the PLC prims, the polling, the message bus, the USD mirror and the window; this extension registers the ADS driver with it.

# Documentation

Detailed documentation can be found in the extension readme file [here](exts/loupe.simulation.beckhoff_bridge/docs/README.md).

The ADS driver itself is the plain-Python [`beckhoff_bridge`](beckhoff_bridge/README.md) package and can be used without Omniverse; `.github/workflows/beckhoff-bridge.yml` tests it and builds its wheel, and a `beckhoff-bridge-v<version>` tag publishes it to PyPI once the `PYPI_TOKEN` secret exists. The direction for the next major version is laid out in [docs/ARCHITECTURE_PLAN.md](docs/ARCHITECTURE_PLAN.md) and the work in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

# Installing the extension

The extension depends on the framework extension `loupe.simulation.bridge`.
From a registry Kit fetches it; from a clone, put the `exts/` folder of an
[Omni-Utils](https://github.com/loupeteam/Omni-Utils) checkout on the app's
extension search path next to this repo's `exts/`.

The Python dependencies are pip packages, installed by Kit before the
extensions start. This extension lists `pyads` and `beckhoff-bridge` (the ADS
driver, `beckhoff_bridge/` in this repo) under `[python.pipapi]` in
`exts/loupe.simulation.beckhoff_bridge/config/extension.toml`; the framework
lists `plc-bridge` (the vendor-neutral polling runtime and driver contract) and
owns its version pin. There are two ways to make them available to Kit.

## From a registry or a packaged extension

Until the Loupe packages are on PyPI their wheels ship inside the extension,
in `exts/loupe.simulation.beckhoff_bridge/wheels/` (git-ignored). Fill that folder
before packaging:

```
python tools/build_wheels.py --plc-bridge <Omni-Utils checkout>/plc_bridge
```

This builds `beckhoff_bridge` (from the repo root) and `plc_bridge` (from the
Omni-Utils checkout; the default is `../Omni-Utils/plc_bridge` next to this repo)
and downloads `pyads`, so the folder holds everything the install needs:
`beckhoff-bridge` depends on `plc-bridge`, and pipapi installs from the folder
without looking at what is already installed. On
first start Kit installs from it with `--no-index` into the app's pip environment;
on later starts it finds the packages importable and does nothing.

This folder only serves this extension. The framework installs `plc-bridge`
from **its own** `wheels/` folder, and it starts first, so it needs that folder
filled too: run Omni-Utils' `python tools/build_wheels.py` in the Omni-Utils
checkout as well. Without it the framework's pipapi finds no archive, falls back
to PyPI, where `plc-bridge` is not published yet, and the framework fails to
import `plc_bridge`; this extension then fails with it.

## Working from a clone

To run from source without building wheels, install the checkouts editable
into the Kit app's own Python. This satisfies both extensions' pip
requirements, the framework's `plc-bridge` included, so neither `wheels/`
folder is needed; it is the path the harness in `tools/kit_check` is verified on:

```
python tools/dev_link.py <kit build root> --plc-bridge <Omni-Utils checkout>/plc_bridge
```

`<kit build root>` is the folder holding `kit/kit.exe`. Leave out `--plc-bridge`
when Omni-Utils' own `tools/dev_link.py` has already installed `plc_bridge`.
Edits under `beckhoff_bridge/src` (and `plc_bridge/src`) are picked up on the
next start. `python tools/dev_link.py <kit build root> --uninstall [--plc-bridge
...]` removes them again (it leaves `pyads` installed).

## What Kit's pipapi does (verified on Kit 110.3, omni.kit.pipapi 0.0.0+00c488ae)

- For each requirement pipapi first imports the module named in the manifest's
  `modules` list (`pyads`, `beckhoff_bridge.driver` here; `plc_bridge.runtime` in
  the framework's) and
  calls pip only when that import fails. An editable install in Kit's Python
  therefore takes precedence over the bundled wheels: with `dev_link.py` applied
  the log shows no `Attempting to install` line at all and the extension imports
  from the working tree. Without `modules`, pipapi tries to import the requirement
  string itself (`beckhoff-bridge>=0.3.0,<0.4`), which never succeeds.
- pip runs as `pip --isolated install --target <env> --no-index --find-links
  <wheels>` first, then without `--no-index` against the online index. `--target`
  ignores packages that are already installed, so the archive has to contain the
  whole dependency closure, which is why `pyads` is in `wheels/`; a dependency
  missing from the folder fails the archive attempt silently and pip falls through
  to the index. `<env>` is `%LOCALAPPDATA%\ov\data\Kit\<app name>\<app
  version>\pip3-envs\default-<python>`; delete it to force a reinstall, for
  example after rebuilding the wheels under the same version.
- Kit has its working directory on `sys.path`. Started from this repo's root, the
  bare `beckhoff_bridge/` folder imports as an empty namespace package: pipapi's
  check still fails (there is no `beckhoff_bridge.driver` in it) and the wheel is
  installed, but the empty package stays cached in `sys.modules`, pipapi logs
  `'beckhoff-bridge>=0.3.0,<0.4' failed to install`, and the extension's own
  import would hit the same cached entry. The extension's `__init__.py` drops a
  cached namespace package before importing, so that start works (verified) and
  the warning is harmless. The harness launchers run Kit from a temp folder to
  avoid it altogether.

## Headless check

`tools/kit_check/` runs the extension and the framework in a built Kit app
without a window and checks a 0.2.x prim, a 0.3 prim and an unchanged 0.2.x
script side by side: startup, driver registration, data delivery, the USD
mirror and write-back, live against a PLC or with injected data. See
[its README](tools/kit_check/README.md). `tools/kit_test.ps1` runs the
extension's Kit tests through `omni.kit.test`.

# Upgrading

Version 0.3.0 moves everything but the ADS driver into the framework extension and introduces vendor-neutral prim attributes and bus names; 0.2.x stages and scripts keep working with deprecation warnings. Version 0.2.0 moved the PLC connection into the USD stage. See the [migration guide](exts/loupe.simulation.beckhoff_bridge/docs/MIGRATION.md) for both.

# Licensing

This software contains source code provided by NVIDIA Corporation. This code is subject to the terms of the [NVIDIA Omniverse License Agreement](https://docs.omniverse.nvidia.com/isaacsim/latest/common/NVIDIA_Omniverse_License_Agreement.html). Files are licensed as follows:

### Files created entirely by Loupe ([MIT License](LICENSE)):
* everything under `beckhoff_bridge/` (the ADS driver as a plain Python package)
* `tools/build_wheels.py`, `tools/dev_link.py`, `tools/kit_test.ps1` and everything under `tools/kit_check/`
* `BeckhoffBridge.py`, `Communication.py`, `global_variables.py` (deprecated re-exports)
* everything under `tests/` in the extension

### Files including Nvidia-generated code and modifications by Loupe (Nvidia Omniverse License Agreement AND MIT License; use must comply to whichever is most restrictive for any attribute):
* `__init__.py`
* `extension.py`

This software is intended for use with NVIDIA Omniverse apps, which are subject to the [NVIDIA Omniverse License Agreement](https://docs.omniverse.nvidia.com/isaacsim/latest/common/NVIDIA_Omniverse_License_Agreement.html) for use and distribution.

The framework extension `loupe.simulation.bridge` and the `plc-bridge` package are part of [Omni-Utils](https://github.com/loupeteam/Omni-Utils) and carry their own licence terms.

This software also relies on [pyads](https://github.com/stlehmann/pyads), which is licensed under the MIT license.
