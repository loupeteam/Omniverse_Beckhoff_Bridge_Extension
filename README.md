# Info
This tool is provided by Loupe.  
https://loupe.team  
info@loupe.team  
1-800-240-7042

# Description

This is an extension that connects Beckhoff PLCs into the Omniverse ecosystem. It leverages [pyads](https://github.com/stlehmann/pyads) to set up an ADS client for communicating with PLCs. 

# Documentation

Detailed documentation can be found in the extension readme file [here](exts/loupe.simulation.beckhoff_bridge/docs/README.md).

# Upgrading from 0.1.x

Version 0.2.0 moves the PLC connection into the USD stage and supports several PLCs. Existing scripts keep working, but the connection has to be set up once as a prim. See the [migration guide](exts/loupe.simulation.beckhoff_bridge/docs/MIGRATION.md).

# Licensing

This software contains source code provided by NVIDIA Corporation. This code is subject to the terms of the [NVIDIA Omniverse License Agreement](https://docs.omniverse.nvidia.com/isaacsim/latest/common/NVIDIA_Omniverse_License_Agreement.html). Files are licensed as follows:

### Files created entirely by Loupe ([MIT License](LICENSE)):
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
