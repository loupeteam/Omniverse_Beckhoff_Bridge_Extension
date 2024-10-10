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
import logging
from carb.settings import get_settings
from .global_variables import EXTENSION_NAME
from .BeckhoffBridge import (
    EVENT_TYPE_DATA_READ,
    EVENT_TYPE_CONNECTION,
    EVENT_TYPE_STATUS,
    get_stream_name,
)
import time
from .BeckhoffBridge import get_system

logger = logging.getLogger(__name__)


LABEL_WIDTH = 100
BUTTON_WIDTH = 100


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
        self._enable_communication = self.get_setting("ENABLE_COMMUNICATION", False)
        self._refresh_rate = self.get_setting("REFRESH_RATE", 20)

        self._plc_manager = get_system()

        # Data stream where the extension will dump the data that it reads from the PLC.
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()
        self._active_plc = None
        self._plc_subscriptions = []

        self._status_stack = dict()

    beckhoff_bridge_runtime = property(
        lambda self: self._plc_manager.get_plc(self._active_plc)
    )

    def select_plc(self, index):
        self.unsubscribe_plc()
        self._active_plc = index
        name = self._plc_manager.get_plc(index).name

        self._plc_subscriptions = [
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_DATA_READ, name), self.on_data_read
            ),
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_CONNECTION, name), self.on_connection
            ),
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_STATUS, name), self.on_status
            ),
        ]

    def unsubscribe_plc(self):
        for subscription in self._plc_subscriptions:
            subscription.unsubscribe()

    def cleanup(self):
        """
        Called when the stage is closed or the extension is hot reloaded.
        Perform any necessary cleanup such as removing active callback functions
        """
        self.unsubscribe_plc()

    def on_status(self, event):
        data = event.payload["status"]

        self.add_status(data)
        self.clean_status()
        self._status_field.model.set_value(str(self.get_status()))

    def get_status(self):
        status_list = []
        for status in self._status_stack:
            data = self._status_stack[status]
            status_list.append(data["data"])
        return status_list

    def clean_status(self):
        for status in list(self._status_stack.keys()):
            data = self._status_stack[status]
            if time.time() - data["time"] > 10:
                del self._status_stack[status]

    def add_status(self, data):
        self._status_stack[hash(str(data))] = {"time": time.time(), "data": str(data)}

    def on_connection(self, event):
        data = event.payload["status"]
        self.add_status(data)
        self.clean_status()
        self._status_field.model.set_value(str(self.get_status()))

    def on_data_read(self, event):
        data = event.payload["data"]
        self._monitor_field.model.set_value(str(data))

    def on_menu_callback(self):
        """Callback for when the UI is opened from the toolbar.
        This is called directly after build_ui().
        """
        pass

    def build_ui(self):
        """
        Build a custom UI tool to run your extension.
        This function will be called any time the UI window is closed and reopened.
        """

        plcs = self._plc_manager.get_plc_names()
        if len(plcs) > 0:
            self.select_plc(plcs[0])

        with ui.CollapsableFrame("Selection", collapsed=False):
            with ui.VStack(spacing=5, height=0):
                with ui.HStack(spacing=5, height=0):
                    ui.Label("Select PLC", width=LABEL_WIDTH)
                    self._plc_dropdown = ui.ComboBox(0, *plcs, selected_index=0)
                    self._plc_dropdown.model.add_item_changed_fn(self.select_plc)

        with ui.CollapsableFrame("Configuration", collapsed=False):
            with ui.VStack(spacing=5, height=0):

                with ui.HStack(spacing=5, height=0):
                    ui.Label("Enable ADS Client", width=LABEL_WIDTH)
                    self._enable_communication_checkbox = ui.CheckBox(
                        ui.SimpleBoolModel(self._enable_communication)
                    )
                    self._enable_communication_checkbox.model.add_value_changed_fn(
                        self._toggle_communication_enable
                    )

                with ui.HStack(spacing=5, height=0):
                    ui.Label("Refresh Rate (ms)", width=LABEL_WIDTH)
                    self._refresh_rate_field = ui.IntField(
                        ui.SimpleIntModel(self._refresh_rate)
                    )
                    self._refresh_rate_field.model.set_min(10)
                    self._refresh_rate_field.model.set_max(10000)
                    self._refresh_rate_field.model.add_value_changed_fn(
                        self._on_refresh_rate_changed
                    )

                with ui.HStack(spacing=5, height=0):
                    ui.Label("PLC AMS Net Id", width=LABEL_WIDTH)
                    self._plc_ams_net_id_field = ui.StringField(
                        ui.SimpleStringModel(self.beckhoff_bridge_runtime.ams_net_id)
                    )
                    self._plc_ams_net_id_field.model.add_value_changed_fn(
                        self._on_plc_ams_net_id_changed
                    )

                with ui.HStack(spacing=5, height=0):
                    ui.Label("Settings", width=LABEL_WIDTH)
                    ui.Button("Load", clicked_fn=self.load_settings, width=BUTTON_WIDTH)
                    ui.Button("Save", clicked_fn=self.save_settings, width=BUTTON_WIDTH)

        with ui.CollapsableFrame("Status", collapsed=False):
            with ui.VStack(spacing=5, height=0):
                with ui.HStack(spacing=5, height=0):
                    ui.Label("Status", width=LABEL_WIDTH)
                    self._status_field = ui.StringField(
                        ui.SimpleStringModel("n/a"), read_only=True
                    )

        with ui.CollapsableFrame("Monitor", collapsed=False):
            with ui.VStack(spacing=5, height=0):
                with ui.HStack(spacing=5, height=100):
                    ui.Label("Variables", width=LABEL_WIDTH)
                    self._monitor_field = ui.StringField(
                        ui.SimpleStringModel("{}"), multiline=True, read_only=True
                    )

        self._ui_initialized = True

    ####################################
    ####################################
    # Manage Settings
    ####################################
    ####################################

    def get_setting(self, name, default_value=None):
        setting = self.settings_interface.get(
            "/persistent/" + EXTENSION_NAME + "/" + name
        )
        if setting is None:
            setting = default_value
            self.settings_interface.set(
                "/persistent/" + EXTENSION_NAME + "/" + name, setting
            )
        return setting

    def set_setting(self, name, value):
        self.settings_interface.set("/persistent/" + EXTENSION_NAME + "/" + name, value)

    def _on_plc_ams_net_id_changed(self, value):
        self.beckhoff_bridge_runtime.ams_net_id = value.get_value_as_string()

    def _on_refresh_rate_changed(self, value):
        self.beckhoff_bridge_runtime.refresh_rate = value.get_value_as_int()

    def _toggle_communication_enable(self, state):
        self.beckhoff_bridge_runtime.enable_communication = state.get_value_as_bool()

    def save_settings(self):
        self.set_setting("REFRESH_RATE", self.beckhoff_bridge_runtime.refresh_rate)
        self.set_setting("PLC_AMS_NET_ID", self.beckhoff_bridge_runtime.ams_net_id)
        self.set_setting(
            "ENABLE_COMMUNICATION", self.beckhoff_bridge_runtime.enable_communication
        )

    def load_settings(self):
        self.beckhoff_bridge_runtime.refresh_rate = self.get_setting("REFRESH_RATE")
        self.beckhoff_bridge_runtime.ams_net_id = self.get_setting("PLC_AMS_NET_ID")
        self.beckhoff_bridge_runtime.enable_communication = self.get_setting(
            "ENABLE_COMMUNICATION"
        )

        self._refresh_rate_field.model.set_value(
            self.beckhoff_bridge_runtime.refresh_rate
        )
        self._plc_ams_net_id_field.model.set_value(
            self.beckhoff_bridge_runtime.ams_net_id
        )
        self._enable_communication_checkbox.model.set_value(
            self.beckhoff_bridge_runtime.enable_communication
        )
