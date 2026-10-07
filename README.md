# Info
This tool is provided by Loupe.  
https://loupe.team  
info@loupe.team  
1-800-240-7042

# Description

This is an extension that connects Beckhoff PLCs into the Omniverse ecosystem. It leverages [pyads](https://github.com/stlehmann/pyads) to set up an ADS client for communicating with PLCs. 

# Documentation

Detailed documentation can be found in the extension readme file [here](exts/loupe.simulation.beckhoff_bridge/docs/README.md).

The ADS driver itself is the plain-Python [`beckhoff_bridge`](beckhoff_bridge/README.md) package and can be used without Omniverse; `.github/workflows/beckhoff-bridge.yml` tests it and builds its wheel, and a `beckhoff-bridge-v<version>` tag publishes it to PyPI once the `PYPI_TOKEN` secret exists. The direction for the next major version is laid out in [docs/ARCHITECTURE_PLAN.md](docs/ARCHITECTURE_PLAN.md) and the work in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

# Installing the extension

The extension's Python dependencies are pip packages, listed under
`[python.pipapi]` in `exts/loupe.simulation.beckhoff_bridge/config/extension.toml`
and installed by Kit before the extension starts: `pyads`, `plc-bridge` (the
vendor-neutral polling runtime and driver contract, from
[Omni-Utils](https://github.com/loupeteam/Omni-Utils)) and `beckhoff-bridge` (the
ADS driver, `beckhoff_bridge/` in this repo). There are two ways to make them
available to Kit.

## From a registry or a packaged extension

Until the two Loupe packages are on PyPI their wheels ship inside the extension,
in `exts/loupe.simulation.beckhoff_bridge/wheels/` (git-ignored). Fill that folder
before packaging:

```
git submodule update --init
python tools/build_wheels.py
```

This builds `plc_bridge` (from the submodule) and `beckhoff_bridge` (from the repo
root) and downloads `pyads`, so the folder holds everything the install needs. On
first start Kit installs from it with `--no-index` into the app's pip environment;
on later starts it finds the packages importable and does nothing.

## Working from a clone

To run from source without building wheels, install the two checkouts editable
into the Kit app's own Python:

```
git submodule update --init
python tools/dev_link.py <kit build root>      # the folder holding kit/kit.exe
```

Edits under `beckhoff_bridge/src` and the submodule's `plc_bridge/src` are picked
up on the next start. `python tools/dev_link.py <kit build root> --uninstall`
removes the two packages again (it leaves `pyads` installed).

## What Kit's pipapi does (verified on Kit 110.3, omni.kit.pipapi 0.0.0+00c488ae)

- For each requirement pipapi first imports the module named in the manifest's
  `modules` list (`pyads`, `plc_bridge.runtime`, `beckhoff_bridge.driver`) and
  calls pip only when that import fails. An editable install in Kit's Python
  therefore takes precedence over the bundled wheels: with `dev_link.py` applied
  the log shows no `Attempting to install` line at all and the extension imports
  from the working tree. Without `modules`, pipapi tries to import the requirement
  string itself (`plc-bridge>=0.3.0rc1,<0.4`), which never succeeds.
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
  `'beckhoff-bridge>=0.3.0rc1,<0.4' failed to install`, and the extension's own
  import would hit the same cached entry. The extension's `__init__.py` drops a
  cached namespace package before importing, so that start works (verified) and
  the warning is harmless. The harness launchers run Kit from a temp folder to
  avoid it altogether.

## Headless check

`tools/kit_check/` runs the extension in a built Kit app without a window and
checks startup, data delivery, the USD mirror and write-back, live against a PLC
or with injected data. See [its README](tools/kit_check/README.md).

# Upgrading from 0.1.x

Version 0.2.0 moves the PLC connection into the USD stage and supports several PLCs. Existing scripts keep working, but the connection has to be set up once as a prim. See the [migration guide](exts/loupe.simulation.beckhoff_bridge/docs/MIGRATION.md).

# Licensing

This software contains source code provided by NVIDIA Corporation. This code is subject to the terms of the [NVIDIA Omniverse License Agreement](https://docs.omniverse.nvidia.com/isaacsim/latest/common/NVIDIA_Omniverse_License_Agreement.html). Files are licensed as follows:

### Files created entirely by Loupe ([MIT License](LICENSE)):
* everything under `beckhoff_bridge/` (the ADS driver as a plain Python package)
* `tools/build_wheels.py`, `tools/dev_link.py` and everything under `tools/kit_check/`
* `Communication.py`
* `Runtime.py`
* `BeckhoffBridge.py`
* everything under `loupe/simulation/common` (the [Omni-Utils](https://github.com/loupeteam/Omni-Utils) submodule)

### Files including Nvidia-generated code and modifications by Loupe (Nvidia Omniverse License Agreement AND MIT License; use must comply to whichever is most restrictive for any attribute):
* `__init__.py`
* `extension.py`
* `global_variables.py`
* `ui_builder.py`

This software is intended for use with NVIDIA Omniverse apps, which are subject to the [NVIDIA Omniverse License Agreement](https://docs.omniverse.nvidia.com/isaacsim/latest/common/NVIDIA_Omniverse_License_Agreement.html) for use and distribution.

This software also relies on [pyads](https://github.com/stlehmann/pyads), which is licensed under the MIT license.
