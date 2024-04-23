# This software contains source code provided by NVIDIA Corporation.
# Copyright (c) 2022-2023, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#
import carb.events


EXTENSION_TITLE = "beckhoff_bridge"
EXTENSION_NAME = "omni.loupe.beckhoff_bridge"
EXTENSION_DESCRIPTION = "Connector for Beckhoff PLCs"

EXTENSION_EVENT_SENDER_ID = 500
EVENT_TYPE_DATA_INIT = carb.events.type_from_string("omni.loupe.beckhoff_bridge.DATA_INIT")
EVENT_TYPE_DATA_READ = carb.events.type_from_string("omni.loupe.beckhoff_bridge.DATA_READ")
EVENT_TYPE_DATA_READ_REQ = carb.events.type_from_string("omni.loupe.beckhoff_bridge.DATA_READ_REQ")
EVENT_TYPE_DATA_WRITE_REQ = carb.events.type_from_string("omni.loupe.beckhoff_bridge.DATA_WRITE_REQ")

