import omni
from pxr import Sdf
from .runtime import Runtime
from ..common.UsdManager import RuntimeUsd


# A singleton class that manages many PLC Connections
class System:
    def __init__(self):
        self.init()

    def init(self):
        self._plcs = dict()
        self._usd_managers = dict()
        self._default_options = {
            "PLC_AMS_NET_ID": "127.0.0.1.1.1",
            "REFRESH_RATE": 20,
            "ENABLE_COMMUNICATION": False,
            "LOG_JITTER": False,
        }

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

    def cleanup(self):
        for plc in self._plcs.values():
            plc.cleanup()
            del plc

        for man in self._usd_managers.values():
            man.cleanup()
            del man

        self._plcs.clear()
        self._usd_managers.clear()

    def set_default_options(self, options):
        self._default_options = options

    def get_options(plc_prim):
        options = {
            "REFRESH_RATE": plc_prim.GetAttribute("beckhoff_bridge:RefreshRate").Get(),
            "PLC_AMS_NET_ID": plc_prim.GetAttribute("beckhoff_bridge:AmsNetId").Get(),
            "ENABLE_COMMUNICATION": plc_prim.GetAttribute(
                "beckhoff_bridge:Enable"
            ).Get(),
            "READ_VARIABLES": plc_prim.GetAttribute("beckhoff_bridge:Variables").Get(),
        }
        return options

    def init_properties(self):
        default_properties = {
            "beckhoff_bridge:Enable": False,
            "beckhoff_bridge:RefreshRate": 20,
            "beckhoff_bridge:AmsNetId": "127.0.0.1.1.1",
            "beckhoff_bridge:Variables": "",  # Ideally this should be a list of variables, but they aren't support on the gui
        }
        RuntimeUsd.set_options(self._plc_prim, default_properties)

    def set_options(plc_prim, options):
        # option_set = {
        #     "beckhoff_bridge:RefreshRate": options.get("REFRESH_RATE") or 20,
        #     "beckhoff_bridge:AmsNetId": options.get("PLC_AMS_NET_ID") or "127.0.0.1.1.1",
        #     "beckhoff_bridge:Enable": options.get("ENABLE_COMMUNICATION") or False,
        #     "beckhoff_bridge:Variables": options.get("READ_VARIABLES") or "",
        #     "beckhoff_bridge:VariableArray": options.get("READ_VARIABLES") or "",
        # }
        for key, value in options.items():
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

    def get_plc(self, name: str | int):
        if name not in self._plcs:
            return None
        return self._plcs[name]

    # Return the names of the PLCs as a list
    def get_plc_names(self):
        plc = self.find_plcs()
        self.cleanup()
        if plc:
            for name, options in plc.items():
                if name not in self._plcs:
                    self.add_plc(name, options)

        return list(self._plcs.keys())

    def add_plc(self, name, options):
        if name not in self._plcs:
            self._plcs[name] = Runtime(name, options)
            self._usd_managers[name] = RuntimeUsd(name)
