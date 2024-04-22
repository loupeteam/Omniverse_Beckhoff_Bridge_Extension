# This software contains source code provided by NVIDIA Corporation.
# Copyright (c) 2022-2023, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#

import omni.ui as ui
import omni.timeline
from omni.usd import StageEventType

from omni.isaac.ui.ui_utils import get_style, btn_builder, cb_builder, str_builder, int_builder
from omni.isaac.ui.element_wrappers import CollapsableFrame
# from omni.isaac.ui import Checkbox
from omni.isaac.ui.element_wrappers.core_connectors import LoadButton, ResetButton

import os
import numpy as np

from .ads_driver import AdsDriver
from .global_variables import EXTENSION_TITLE, EXTENSION_DESCRIPTION, EXTENSION_EVENT_SENDER_ID, EXTENSION_EVENT_TYPE

import threading
import time

# TODOs:
# 1. Find a way for data to get fed back into the PLC, from IsaacSim GUI (i.e. HUD things).
# 2. Pass all the data onto the stream (not just 'var_array'). 
# 3. Set up a way to customize the data to read, via the UI. 
# 4. Ensure that thread stops at correct times (i.e. during cleanup, etc). 
# 5. Maybe find a way to make the stream id and message type global constants (i.e. for other extensions to use). 
# 6. Publish to the registry

class UIBuilder:
    def __init__(self):
        # UI elements created using a UIElementWrapper instance
        self.wrapped_ui_elements = []

        # Get access to the timeline to control stop/pause/play programmatically
        self._timeline = omni.timeline.get_timeline_interface()

        # Internal status flags. 
        self._thread_is_alive = True   
        self._communication_initialized = False
        self._ui_initialized = False

        # Configuration parameters for the extension.
        # These are exposed on the UI. 
        self._enable_communication = False
        self._refresh_rate = 20
        self._plc_ams_net_id = '39.163.103.49.1.1'

        # Data stream where the extension will dump the data that it reads from the PLC.
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()

        # Thread to perform the cyclic PLC interactions. 
        self._thread = threading.Thread(target=self._update_plc_data)
        self._thread.start()

    ###################################################################################
    #           The Functions Below Are Called Automatically By extension.py
    ###################################################################################

    def on_menu_callback(self):
        """Callback for when the UI is opened from the toolbar. 
        This is called directly after build_ui().
        """
        pass

    def on_timeline_event(self, event):
        """Callback for Timeline events (Play, Pause, Stop)

        Args:
            event (omni.timeline.TimelineEventType): Event Type
        """
        if(event.type == int(omni.timeline.TimelineEventType.STOP)):
            pass
        elif(event.type == int(omni.timeline.TimelineEventType.PLAY)):
            pass
        elif(event.type == int(omni.timeline.TimelineEventType.PAUSE)):
            pass     
   
    def on_stage_event(self, event):
        """Callback for Stage Events

        Args:
            event (omni.usd.StageEventType): Event Type
        """
        pass

    def cleanup(self):
        """
        Called when the stage is closed or the extension is hot reloaded.
        Perform any necessary cleanup such as removing active callback functions
        Buttons imported from omni.isaac.ui.element_wrappers implement a cleanup function that should be called
        """
        self._thread_is_alive = False
        # for ui_elem in self.wrapped_ui_elements:
        #     ui_elem.cleanup()
        time.sleep(1) # to give thread time to complete

    def build_ui(self):
        """
        Build a custom UI tool to run your extension.  
        This function will be called any time the UI window is closed and reopened.
        """
        configuration_frame = CollapsableFrame("Configuration", collapsed=False)

        with configuration_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                cb_builder(label='Enable ADS Client', type='checkbox', default_val=self._enable_communication, on_clicked_fn=self._toggle_communication_enable)
                self._refresh_rate_field = int_builder(label='Refresh Rate (ms)', type='intfield', default_val=self._refresh_rate, min=10, max=10000)
                self._plc_ams_net_id_field = str_builder(label="PLC AMS Net Id", type='stringfield', default_val=self._plc_ams_net_id)

        data_frame = CollapsableFrame("Data", collapsed=False)

        with data_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                str_builder(label="PLC Variable Name", type='stringfield', default_val='n/a')

        status_frame = CollapsableFrame("Status", collapsed=False)

        with status_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self._status_counter_field = str_builder(label='Counter', type='stringfield', default_val='n/a', read_only=True)

        self._ui_initialized = True

    def _toggle_communication_enable(self, state):
        self._enable_communication = state

    ####################################
    ####################################
    # UTILITY FUNCTIONS
    ####################################
    ####################################

    def _update_plc_data(self):
        while self._thread_is_alive:
            thread_start_time = time.time()
            if self._ui_initialized:
                self._refresh_rate = self._refresh_rate_field.get_value_as_int()
                self._plc_ams_net_id = self._plc_ams_net_id_field.get_value_as_string()
                if self._enable_communication:
                    if not self._communication_initialized:
                        self._ads_connector = AdsDriver(self._plc_ams_net_id)
                        self._communication_initialized = True
                    else:
                        self._data = self._ads_connector.read_structure()
                        var_array = self._data['var_array']
                        self._event_stream.push(event_type=EXTENSION_EVENT_TYPE, sender=EXTENSION_EVENT_SENDER_ID, payload={'data': var_array})                   
                        self._status_counter_field.set_value(str(var_array[0]))
                else:
                    self._status_counter_field.set_value(str(0))
            sleepy_time = self._refresh_rate/1000 - (time.time() - thread_start_time)
            if sleepy_time > 0:
                time.sleep(sleepy_time)
            else:
                time.sleep(0.1)

    