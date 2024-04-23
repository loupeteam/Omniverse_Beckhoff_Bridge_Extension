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
from omni.isaac.ui import StringField, IntField, Button
from omni.isaac.ui.element_wrappers import CollapsableFrame
# from omni.isaac.ui import Checkbox
from omni.isaac.ui.element_wrappers.core_connectors import LoadButton, ResetButton

from carb.settings import get_settings
import omni.isaac.core.utils.carb as carb_utils

import os
import numpy as np

from .ads_driver import AdsDriver
from .global_variables import EXTENSION_TITLE, EXTENSION_DESCRIPTION, EXTENSION_NAME, EXTENSION_EVENT_SENDER_ID, EVENT_TYPE_DATA_READ, EVENT_TYPE_DATA_READ_REQ, EVENT_TYPE_DATA_WRITE_REQ

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

        # Get the settings interface
        self.settings_interface = get_settings()
        
        # Internal status flags. 
        self._thread_is_alive = True   
        self._communication_initialized = False
        self._ui_initialized = False

        # Configuration parameters for the extension.
        # These are exposed on the UI. 
        self._enable_communication = self.get_setting( 'ENABLE_COMMUNICATION', False ) 
        self._refresh_rate = self.get_setting( 'REFRESH_RATE', 20 )
        self._plc_ams_net_id = self.get_setting( 'PLC_AMS_NET_ID', '127.0.0.1.1.1')

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
        if(not self._thread_is_alive):
            self._thread_is_alive = True
            self._thread = threading.Thread(target=self._update_plc_data)
            self._thread.start()

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
        self._thread.join()

    def build_ui(self):
        """
        Build a custom UI tool to run your extension.  
        This function will be called any time the UI window is closed and reopened.
        """
        configuration_frame = CollapsableFrame("Configuration", collapsed=False)

        with configuration_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self._enable_communication_checkbox = cb_builder(label='Enable ADS Client', type='checkbox', default_val=self._enable_communication, on_clicked_fn=self._toggle_communication_enable)
                self._refresh_rate_field = IntField(label='Refresh Rate (ms)', default_value=self._refresh_rate, lower_limit=10, upper_limit=10000, on_value_changed_fn=self._on_refresh_rate_changed)
                self._plc_ams_net_id_field = StringField(label="PLC AMS Net Id", default_value=self._plc_ams_net_id, on_value_changed_fn=self._on_plc_ams_net_id_changed)
                with ui.HStack():
                    Button("Settings", "Load", on_click_fn=self.load_settings)
                    Button("", "Save", on_click_fn=self.save_settings)

        status_frame = CollapsableFrame("Status", collapsed=False)

        with status_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self._status_field = str_builder(label='Status', type='stringfield', default_val='n/a', read_only=True)

        self._ui_initialized = True

    ####################################
    ####################################
    # UTILITY FUNCTIONS
    ####################################
    ####################################

    def _update_plc_data(self):

        thread_start_time = time.time()

        while self._thread_is_alive:

            # Sleep for the refresh rate
            sleepy_time = self._refresh_rate/1000 - (time.time() - thread_start_time)
            if sleepy_time > 0:
                time.sleep(sleepy_time)
            else:
                time.sleep(0.1)

            thread_start_time = time.time()

            if not self._ui_initialized:
                continue

            if not self._enable_communication:
                self._status_field.set_value("Disabled")
                continue

            try:

                if not self._communication_initialized:
                    self._ads_connector = AdsDriver(self._plc_ams_net_id)
                    self._communication_initialized = True

                self._status_field.set_value("Reading Data")
                self._data = self._ads_connector.read_structure()
                self._event_stream.push(event_type=EVENT_TYPE_DATA_READ, sender=EXTENSION_EVENT_SENDER_ID, payload={'data': self._data})

            except Exception as e:
                print(f"Error reading data from PLC: {e}")
                self._status_field.set_value(str(e))
                time.sleep(1)

    ####################################
    ####################################
    # Manage Settings
    ####################################
    ####################################

    def get_setting(self, name, default_value=None ):
        setting =  carb_utils.get_carb_setting(self.settings_interface, "/persistent/" + EXTENSION_NAME + "/" + name )
        if setting is None:
            setting = default_value
            self.set_setting(name, setting)
        return setting

    def set_setting(self, name, value ):
        carb_utils.set_carb_setting(self.settings_interface, "/persistent/" + EXTENSION_NAME + "/" + name, value )

    def _on_plc_ams_net_id_changed(self, value):
        self._plc_ams_net_id = value
        self._communication_initialized = False


    def _on_refresh_rate_changed(self, value):
        self._refresh_rate = value

    def _toggle_communication_enable(self, state):
        self._enable_communication = state
        if not self._enable_communication:
            self._communication_initialized = False

    def save_settings(self):
        self.set_setting('REFRESH_RATE', self._refresh_rate)
        self.set_setting('PLC_AMS_NET_ID', self._plc_ams_net_id)
        self.set_setting('ENABLE_COMMUNICATION', self._enable_communication)

    def load_settings(self):
        self._refresh_rate = self.get_setting('REFRESH_RATE')
        self._plc_ams_net_id = self.get_setting('PLC_AMS_NET_ID')
        self._enable_communication = self.get_setting('ENABLE_COMMUNICATION')

        self._refresh_rate_field.set_value(self._refresh_rate)
        self._plc_ams_net_id_field.set_value(self._plc_ams_net_id)
        self._enable_communication_checkbox.set_value(self._enable_communication)
