# This software contains source code provided by NVIDIA Corporation.
# Copyright (c) 2022-2023, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#


EXTENSION_TITLE = "Beckhoff Bridge"
EXTENSION_NAME = "loupe.simulation.beckhoff_bridge"
EXTENSION_DESCRIPTION = "Bridge to Beckhoff PLCs"

ATTR_BECKHOFF_BRIDGE_AMS_NET_ID = "beckhoff_bridge:AmsNetId"
ATTR_BECKHOFF_BRIDGE_ENABLE = "beckhoff_bridge:Enable"
ATTR_BECKHOFF_BRIDGE_REFRESH = "beckhoff_bridge:RefreshRate"
ATTR_BECKHOFF_BRIDGE_READ_VARS = "beckhoff_bridge:Variables"

"""
    These are the default properties for the Beckhoff Bridge when creating a new component
"""
default_beckoff_properties = {
    ATTR_BECKHOFF_BRIDGE_ENABLE: False,
    ATTR_BECKHOFF_BRIDGE_REFRESH: 20,
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID: "127.0.0.1.1.1",
    ATTR_BECKHOFF_BRIDGE_READ_VARS: "",  # Ideally this should be a list of variables, but they aren't support on the gui
}
