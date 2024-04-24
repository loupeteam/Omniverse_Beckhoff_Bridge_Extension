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

from omni.isaac.ui import StringField, IntField, Button, TextBlock
from omni.isaac.ui.ui_utils import get_style, cb_builder
from omni.isaac.ui.element_wrappers import CollapsableFrame

from carb.settings import get_settings
import omni.isaac.core.utils.carb as carb_utils

from .ads_driver import AdsDriver

from .global_variables import EXTENSION_NAME
from .Api import EXTENSION_EVENT_SENDER_ID, EVENT_TYPE_DATA_READ, EVENT_TYPE_DATA_READ_REQ, EVENT_TYPE_DATA_WRITE_REQ, EVENT_TYPE_DATA_INIT

import threading
from threading import RLock

import json

import time

# TODOs: 
# - Publish to the registry
# - Add mapping to the model
 
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

        # Data stream where the extension will dump the data that it reads from the PLC.
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()

        self._ads_connector = AdsDriver(self.get_setting( 'PLC_AMS_NET_ID', '127.0.0.1.1.1'))
        
        self.write_queue = dict()
        self.write_lock = RLock()

        self.read_req = self._event_stream.create_subscription_to_push_by_type(EVENT_TYPE_DATA_READ_REQ, self.on_read_req_event)
        self.write_req = self._event_stream.create_subscription_to_push_by_type(EVENT_TYPE_DATA_WRITE_REQ, self.on_write_req_event)
        self._event_stream.push(event_type=EVENT_TYPE_DATA_INIT, sender=EXTENSION_EVENT_SENDER_ID, payload={'data': {}})

        self._thread = threading.Thread(target=self._update_plc_data)
        self._thread.start()

    ###################################################################################
    #           The Functions Below Are Called Automatically By extension.py
    ###################################################################################

    def on_menu_callback(self):
        """Callback for when the UI is opened from the toolbar. 
        This is called directly after build_ui().
        """
        self._event_stream.push(event_type=EVENT_TYPE_DATA_INIT, sender=EXTENSION_EVENT_SENDER_ID, payload={'data': {}})

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
        self.read_req.unsubscribe()
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
                self._plc_ams_net_id_field = StringField(label="PLC AMS Net Id", default_value=self._ads_connector.ams_net_id, on_value_changed_fn=self._on_plc_ams_net_id_changed)
                with ui.HStack():
                    Button("Settings", "Load", on_click_fn=self.load_settings)
                    Button("", "Save", on_click_fn=self.save_settings)

        status_frame = CollapsableFrame("Status", collapsed=False)

        with status_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self._status_field = StringField(label='Status', default_value='n/a', read_only=True)

        monitor_frame = CollapsableFrame("Monitor", collapsed=False)

        with monitor_frame:
            with ui.VStack(style=get_style(), spacing=5, height=0):
                self._monitor_field = TextBlock(label='Variables', num_lines=10)

        self._ui_initialized = True

    ####################################
    ####################################
    # UTILITY FUNCTIONS
    ####################################
    ####################################

    def on_read_req_event(self, event ):
        event_data = event.payload
        variables : list = event_data['variables'] 
        for name in variables:
            self._ads_connector.add_read(name)

    def on_write_req_event(self, event ):
        variables = event.payload["variables"]
        for variable in variables:
            self.queue_write(variable['name'], variable['value'])

    def queue_write(self, name, value):
        with self.write_lock:
            self.write_queue[name] = value

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

            if not self._enable_communication:
                if self._ui_initialized:
                    self._status_field.set_value("Disabled")
                continue

            try:

                if(not self._communication_initialized):
                    self._ads_connector.connect()
                    self._communication_initialized = True

                # Write data to the PLC if there is data to write
                try:
                    if self.write_queue:                                             
                        with self.write_lock:
                            values = self.write_queue
                            self.write_queue = dict()
                        self._ads_connector.write_data(values)
                except Exception as e:
                    if self._ui_initialized:
                        self._status_field.set_value(f"Error writing data to PLC: {e}")

                # Read data from the PLC
                #measure the time it takes to read data
                self._data = self._ads_connector.read_data()
                self._event_stream.push(event_type=EVENT_TYPE_DATA_READ, sender=EXTENSION_EVENT_SENDER_ID, payload={'data': self._data})
                if self._ui_initialized:
                    self._status_field.set_value("Reading Data OK")
                    json_formatted_str = json.dumps(self._data, indent=4)
                    self._monitor_field.set_text(json_formatted_str)
            except Exception as e:
                if self._ui_initialized:
                    self._status_field.set_value(f"Error reading data from PLC: {e}")
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
        self._ads_connector.ams_net_id = value
        self._communication_initialized = False

    def _on_refresh_rate_changed(self, value):
        self._refresh_rate = value

    def _toggle_communication_enable(self, state):
        self._enable_communication = state
        if not self._enable_communication:
            self._communication_initialized = False

    def save_settings(self):
        self.set_setting('REFRESH_RATE', self._refresh_rate)
        self.set_setting('PLC_AMS_NET_ID', self._ads_connector.ams_net_id)
        self.set_setting('ENABLE_COMMUNICATION', self._enable_communication)

    def load_settings(self):
        self._refresh_rate = self.get_setting('REFRESH_RATE')
        self._ads_connector.ams_net_id = self.get_setting('PLC_AMS_NET_ID')
        self._enable_communication = self.get_setting('ENABLE_COMMUNICATION')

        self._refresh_rate_field.set_value(self._refresh_rate)
        self._plc_ams_net_id_field.set_value(self._ads_connector.ams_net_id)
        self._enable_communication_checkbox.set_value(self._enable_communication)
        self._communication_initialized = False

