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
Extension entry point: registers the ADS driver with the PLC bridge framework.

Everything a simulation touches (the /PLC prims, the polling runtimes, the
message bus, the USD mirror, the window) lives in `loupe.simulation.bridge`.
This extension only tells it how to build a `beckhoff_bridge.AdsDriver` from a
PLC prim: prims with `bridge:driver = "beckhoff"` and `beckhoff:AmsNetId`, and
the 0.2.x prims that carry `beckhoff_bridge:*` attributes instead. The
framework builds one settings field per option, so no UI panel is registered.
"""

import omni.ext
from beckhoff_bridge import AdsDriver
from loupe.simulation.bridge import Option, check_extension_requirements, registry

DRIVER_NAME = "beckhoff"
LEGACY_NAMESPACE = "beckhoff_bridge"
OPTIONS = [Option("AmsNetId", "str", "127.0.0.1.1.1", "PLC AMS Net Id")]


def register():
    """Register the ADS driver. Safe to call again: a second registration replaces the first."""
    return registry.register(DRIVER_NAME, AdsDriver, OPTIONS,
                             legacy_namespace=LEGACY_NAMESPACE, title="Beckhoff (ADS)")


def unregister():
    """Remove the ADS driver, unless something else has registered over it since."""
    spec = registry.get(DRIVER_NAME)
    if spec is not None and spec.driver_class is AdsDriver:
        registry.unregister(DRIVER_NAME)


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        # Kit's pip installer only checks that beckhoff_bridge imports; log an
        # error when the one it found is not the version this extension pins.
        check_extension_requirements(ext_id)
        register()

    def on_shutdown(self):
        unregister()
