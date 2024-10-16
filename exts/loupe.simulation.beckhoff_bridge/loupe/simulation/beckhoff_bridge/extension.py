# This software contains source code provided by NVIDIA Corporation.
# Copyright (c) 2022-2023, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#

import weakref
import asyncio
import gc
import omni
import omni.ui as ui
import omni.usd
import omni.timeline
import omni.kit.commands
from carb.settings import get_settings

from omni.kit.menu.utils import add_menu_items, remove_menu_items, MenuItemDescription
from omni.usd import StageEventType
import omni.physx as _physx

from .global_variables import EXTENSION_TITLE

# from .ui_builder import UIBuilder
from ..common.System import System
from .BeckhoffBridge import _set_system, Manager, Manager_Events
from .ui_builder import UIBuilder
from .global_variables import default_beckoff_properties
from .Runtime import Runtime

"""
This file serves as a basic template for the standard boilerplate operations
that make a UI-based extension appear on the toolbar.

This implementation is meant to cover most use-cases without modification.
Various callbacks are hooked up to a seperate class UIBuilder in .ui_builder.py
Most users will be able to make their desired UI extension by interacting solely with
UIBuilder.

This class sets up standard useful callback functions in UIBuilder:
    on_menu_callback: Called when extension is opened
    on_timeline_event: Called when timeline is stopped, paused, or played
    on_stage_event: Called when stage is opened or closed
    cleanup: Called when resources such as physics subscriptions should be cleaned up
    build_ui: User function that creates the UI they want.
"""

MENU_HEADER = "Loupe"
MENU_ITEM_NAME = "Beckhoff Bridge"


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id: str):
        """Initialize extension and UI elements"""

        self._component_manager = System(
            "/PLC/", default_beckoff_properties, Runtime, Manager
        )
        _set_system(self._component_manager)

        # Events
        self._usd_context = omni.usd.get_context()

        # Build Window
        self._window = ui.Window(
            title=EXTENSION_TITLE,
            width=600,
            height=500,
            visible=False,
            dockPreference=ui.DockPreference.LEFT_BOTTOM,
        )
        self._window.set_visibility_changed_fn(self._on_window)

        # UI
        self._models = {}
        self._ext_id = ext_id
        self._menu_items = [
            MenuItemDescription(
                name=MENU_ITEM_NAME,
                onclick_fn=lambda a=weakref.proxy(self): a._menu_callback(),
            )
        ]
        add_menu_items(self._menu_items, MENU_HEADER)

        # Filled in with User Functions
        self.ui_builder = UIBuilder(self._component_manager, Manager_Events)

        # Events
        self._usd_context = omni.usd.get_context()
        self._physxIFace = _physx.acquire_physx_interface()
        self._physx_subscription = None
        self._stage_event_sub = None
        self._timeline = omni.timeline.get_timeline_interface()

        self._component_manager.find_and_create_components()

    def find_components(self):
        self._component_manager.find_components()

    def on_shutdown(self):
        self._models = {}
        remove_menu_items(self._menu_items, MENU_HEADER, True)
        if self._window:
            self._window = None
        self.ui_builder.cleanup()
        self._component_manager.cleanup()
        _set_system(None)

        gc.collect()

    def _on_window(self, visible):
        if self._window.visible:
            # Subscribe to Stage and Timeline Events
            self._usd_context = omni.usd.get_context()
            events = self._usd_context.get_stage_event_stream()
            self._stage_event_sub = events.create_subscription_to_pop(
                self._on_stage_event
            )
            stream = self._timeline.get_timeline_event_stream()
            self._timeline_event_sub = stream.create_subscription_to_pop(
                self._on_timeline_event
            )

            self._build_ui()
        else:
            self._usd_context = None
            self._stage_event_sub = None
            self._timeline_event_sub = None

    def _build_ui(self):
        with self._window.frame:
            with ui.VStack(spacing=5, height=0):
                self._build_extension_ui()

        async def dock_window():
            await omni.kit.app.get_app().next_update_async()

            def dock(space, name, location, pos=0.5):
                window = omni.ui.Workspace.get_window(name)
                if window and space:
                    window.dock_in(space, location, pos)
                return window

            tgt = ui.Workspace.get_window("Viewport")
            dock(tgt, EXTENSION_TITLE, omni.ui.DockPosition.LEFT, 0.33)
            await omni.kit.app.get_app().next_update_async()

        self._task = asyncio.ensure_future(dock_window())

    def _menu_callback(self):
        self._window.visible = not self._window.visible
        self.ui_builder.on_menu_callback()

    def _on_timeline_event(self, event):
        pass

    def _on_stage_event(self, event):
        if event.type == int(StageEventType.OPENED) or event.type == int(
            StageEventType.CLOSED
        ):
            # stage was opened or closed, cleanup
            self._physx_subscription = None
            self._component_manager.cleanup()
            self.find_components()

    def _build_extension_ui(self):
        # Call user function for building UI
        self.ui_builder.build_ui()
