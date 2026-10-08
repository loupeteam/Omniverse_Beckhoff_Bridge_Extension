# This software contains source code provided by NVIDIA Corporation.
# Copyright (c) 2022-2023, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#
# Modifications copyright (c) 2024 Loupe, https://loupe.team, MIT License.

"""
loupe.simulation.beckhoff_bridge: registers the Beckhoff ADS driver with the
PLC bridge framework (`loupe.simulation.bridge`).

`BeckhoffBridge` is the deprecated 0.2.x import path. It is not imported here,
so its warning appears only for code that still uses it.
"""

import sys as _sys

# beckhoff_bridge comes from a pip requirement that Kit's pipapi installs before
# this module loads. Kit has its working directory on sys.path, so when Kit is
# started from a checkout of this repo the bare beckhoff_bridge/ folder at the
# root is importable as an empty namespace package. pipapi's import check then
# caches that empty package in sys.modules before the wheel is installed, and
# the real package can no longer be imported in that process. Drop such an
# entry (no __file__: a namespace package, never the real one).
_mod = _sys.modules.get("beckhoff_bridge")
if _mod is not None and getattr(_mod, "__file__", None) is None:
    del _sys.modules["beckhoff_bridge"]
del _mod, _sys

from .extension import *  # noqa: E402,F401,F403
