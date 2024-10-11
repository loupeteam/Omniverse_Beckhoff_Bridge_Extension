import omni
import omni.usd
from omni.usd import StageEventType
from pxr import Sdf, Gf, Tf
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade

from threading import RLock

from .runtime_base import get_stream_name
from .BeckhoffBridge import (
    EVENT_TYPE_DATA_READ,
    EVENT_TYPE_CONNECTION,
    EVENT_TYPE_STATUS,
)


class RuntimeUsd:
    @staticmethod
    def find_plcs():
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        plcs_prims = []
        for prim in stage.Traverse():
            if prim.GetAttribute("beckhoff_bridge:Enable"):
                plcs_prims.append(prim)
        # For all the prims found, get the prim name and add it to the list
        names = dict()
        for plc in plcs_prims:
            name = plc.GetPath().pathString.split("/")[-1]
            options = RuntimeUsd.get_options(plc)         
            names[name] = options
        return names
    
    @staticmethod
    def get_options(plc_prim):
        options = {
            "REFRESH_RATE": plc_prim.GetAttribute("beckhoff_bridge:RefreshRate").Get(),
            "PLC_AMS_NET_ID": plc_prim.GetAttribute("beckhoff_bridge:AmsNetId").Get(),
            "ENABLE_COMMUNICATION": plc_prim.GetAttribute("beckhoff_bridge:Enable").Get(),
            "READ_VARIABLES": plc_prim.GetAttribute("beckhoff_bridge:Variables").Get(),
        }
        return options

    @staticmethod
    def set_options(plc_prim, options):
        option_set = {
            "beckhoff_bridge:RefreshRate": options.get("REFRESH_RATE") or 20,
            "beckhoff_bridge:AmsNetId": options.get("PLC_AMS_NET_ID") or "127.0.0.1.1.1",
            "beckhoff_bridge:Enable": options.get("ENABLE_COMMUNICATION") or False,
            "beckhoff_bridge:Variables": options.get("READ_VARIABLES") or "",
        }
        for key, value in option_set.items():
            attr = plc_prim.GetAttribute(key)
            if not attr:                
                if type(value) is bool:
                    attr = plc_prim.CreateAttribute(key, Sdf.ValueTypeNames.Bool)
                elif type(value) is int:
                    attr = plc_prim.CreateAttribute(key, Sdf.ValueTypeNames.Int)
                elif type(value) is str:
                    attr = plc_prim.CreateAttribute(key, Sdf.ValueTypeNames.String)
                elif type(value) is list:
                    attr = plc_prim.CreateAttribute(key, Sdf.ValueTypeNames.StringArray)
            attr.Set(value)
    def __init__(self, name="PLC1", prim_path=None):

        # Data stream where the extension will dump the data that it reads from the PLC.
        self.name = name
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()
        self._plc_subscriptions = []

        self._usd_context = omni.usd.get_context()

        self._stage = self._usd_context.get_stage()
        self.prim_path = prim_path
        self._plc_prim = None
        self.plc_prim
        self.lock = RLock()
        self.subscribe_plc()
        self.subscribe_stage()
        self.data_update = dict()

    def __del__(self):
        self.cleanup()

    @property
    def plc_prim(self):
        if self._plc_prim is not None:
            return self._plc_prim

        if self.prim_path is None:
            self.prim_path = f"/PLC/{self.name}"

        self._plc_prim = self._stage.GetPrimAtPath(self.prim_path)
        if not self._plc_prim.IsValid():
            self._plc_prim = self._stage.DefinePrim(self.prim_path)
            self.init_properties()

        return self._plc_prim

    def init_properties(self):
        default_properties = {
            "beckhoff_bridge:Enable": False,
            "beckhoff_bridge:RefreshRate": 20,
            "beckhoff_bridge:AmsNetId": "127.0.0.1.1.1",
            "beckhoff_bridge:Variables": "Variable1, Variable2",  # Ideally this should be a list of variables, but they aren't support on the gui
        }
        RuntimeUsd.set_options(self._plc_prim, default_properties)

    def cleanup(self):
        self.unsubscribe_plc()
        self.unsubscribe_stage()

    def on_data_read(self, event):
        data = event.payload["data"]
        data = flatten_obj(data)
        with self.lock:
            self.data_update.update(data)

    def on_connection(self, event):
        pass

    def on_status(self, event):
        pass

    def subscribe_stage(self):
        events = self._usd_context.get_stage_event_stream()
        self._stage_event_sub = events.create_subscription_to_pop(self._on_stage_event)

        # subscription
        self._update_event_sub = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(self.on_update_event, name="subscription Name")
        )

    # callback
    def on_update_event(self, event):

        if self._stage.expired:
            return
        
        flat = None
        with self.lock:
            flat = self.data_update
            self.data_update = dict()

        for key, value in flat.items():
            path = self._plc_prim.GetPath()
            full_key = path.pathString + "/" + "/".join(key.split("."))

            # Get or create a prim for the variable
            prim = self._stage.GetPrimAtPath(full_key)
            
            if not prim:
                prim = self._stage.DefinePrim(full_key)

            attr = prim.GetAttribute("value")
            if not attr:
                if type(value) is str:
                    attr = prim.CreateAttribute("value", Sdf.ValueTypeNames.String)
                else:
                    attr = prim.CreateAttribute("value", Sdf.ValueTypeNames.Double)
            attr.Set(value)

    def unsubscribe_stage(self):
        # unsubscription
        self._update_event_sub = None
        self._stage_event_sub = None

    def _on_stage_event(self, event):
        if event.type == int(StageEventType.OPENED):
            self._stage = self._usd_context.get_stage()

    def subscribe_plc(self):
        self._plc_subscriptions = [
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_DATA_READ, self.name), self.on_data_read
            ),
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_CONNECTION, self.name), self.on_connection
            ),
            self._event_stream.create_subscription_to_push_by_type(
                get_stream_name(EVENT_TYPE_STATUS, self.name), self.on_status
            ),
        ]

    def unsubscribe_plc(self):
        for subscription in self._plc_subscriptions:
            subscription.unsubscribe()


def flatten_obj(obj):
    """
    Flattens a nested object into a single-level dictionary.
    """

    def flatten(obj, key=""):
        if isinstance(obj, dict):
            for k in obj:
                flatten(obj[k], key + k + ".")
        else:
            flat_obj[key[:-1]] = obj

    flat_obj = {}
    flatten(obj)
    return flat_obj
