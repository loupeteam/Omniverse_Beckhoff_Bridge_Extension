"""
DEPRECATED 0.2.x constants, kept through 0.3.x; removed in 0.5.0.

Copyright (c) 2024 Loupe, https://loupe.team
Part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

The 0.2.x attribute names. 0.3 prims use `bridge:Enable`, `bridge:RefreshRate`,
`bridge:Variables` and `beckhoff:AmsNetId` (see MIGRATION.md).
"""

import logging
import warnings

_MESSAGE = ("loupe.simulation.beckhoff_bridge.global_variables is deprecated since 0.3.0 and will be removed in 0.5.0: "
            "the 0.2.x 'beckhoff_bridge:*' attributes give way to 'bridge:*' and 'beckhoff:AmsNetId' (see MIGRATION.md).")
warnings.warn(_MESSAGE, DeprecationWarning, stacklevel=2)
logging.getLogger(__name__).warning(_MESSAGE)

EXTENSION_TITLE = "Beckhoff Bridge"
EXTENSION_NAME = "loupe.simulation.beckhoff_bridge"
EXTENSION_DESCRIPTION = "Bridge to Beckhoff PLCs"
ATTR_BECKHOFF_BRIDGE_AMS_NET_ID = "beckhoff_bridge:AmsNetId"
ATTR_BECKHOFF_BRIDGE_ENABLE = "beckhoff_bridge:Enable"
ATTR_BECKHOFF_BRIDGE_REFRESH = "beckhoff_bridge:RefreshRate"
ATTR_BECKHOFF_BRIDGE_READ_VARS = "beckhoff_bridge:Variables"
default_beckoff_properties = {
    ATTR_BECKHOFF_BRIDGE_ENABLE: False,
    ATTR_BECKHOFF_BRIDGE_REFRESH: 20,
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID: "127.0.0.1.1.1",
    ATTR_BECKHOFF_BRIDGE_READ_VARS: "",
}
