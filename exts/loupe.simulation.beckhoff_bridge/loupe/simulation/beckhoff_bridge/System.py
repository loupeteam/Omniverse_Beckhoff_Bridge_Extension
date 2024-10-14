import omni
from pxr import Sdf
from .Runtime import Runtime
from ..common.UsdManager import RuntimeUsd
from .BeckhoffBridge import Manager
from .global_variables import (
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID,
    ATTR_BECKHOFF_BRIDGE_ENABLE,
    ATTR_BECKHOFF_BRIDGE_READ_VARS,
    ATTR_BECKHOFF_BRIDGE_REFRESH,
)  # noqa: E501


default_properties = {
    ATTR_BECKHOFF_BRIDGE_ENABLE: False,
    ATTR_BECKHOFF_BRIDGE_REFRESH: 20,
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID: "127.0.0.1.1.1",
    ATTR_BECKHOFF_BRIDGE_READ_VARS: "",  # Ideally this should be a list of variables, but they aren't support on the gui
}


class Components:
    def __init__(self, runtime, usd):
        self.runtime = runtime
        self.usd = usd


# A singleton class that manages many PLC Connections
class System:
    def __init__(self):
        self.init()

    def init(self):
        self._components = dict()

    def update_stage_plcs(self):
        plcs = self.find_plcs()
        for name, options in plcs.items():
            if name not in self._plcs:
                self.add_plc(name, options)

    def find_and_create_plcs(self):
        plcs = self.find_plcs()
        if plcs is None:
            return
        for name, options in plcs.items():
            if name not in self._components:
                self.add_plc(name, options)

        #remove plcs that are not in the stage
        for name in list(self._components.keys()):
            if name not in plcs:
                self._components[name].runtime.cleanup()
                self._components[name].usd.cleanup()
                del self._components[name]

        return self.get_plc_names()

    def find_plcs(self):
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        plcs_prims = []
        for prim in stage.Traverse():
            if prim.GetAttribute(ATTR_BECKHOFF_BRIDGE_ENABLE):
                plcs_prims.append(prim)
        # For all the prims found, get the prim name and add it to the list
        names = dict()
        for plc in plcs_prims:
            name = plc.GetPath().pathString.split("/")[-1]
            names[name] = get_options(plc)
        return names

    def create_plc(self, name: str, options: dict):
        create_plc_prim = omni.usd.get_context().get_stage().DefinePrim("/PLC/" + name)
        set_options(create_plc_prim, options)

    def cleanup(self):
        for plc in self._components.values():
            plc.runtime.cleanup()
            plc.usd.cleanup()

        self._components.clear()

    def init_properties(self):
        set_options(self._plc_prim, default_properties)

    def get_plc(self, name: str | int):
        if name not in self._components:
            return None
        return self._components[name].runtime

    def write_options_to_stage(self, plc_name):
        plc = self.get_plc(plc_name)
        if plc is None:
            return
        plc_prim = omni.usd.get_context().get_stage().GetPrimAtPath("/PLC/" + plc_name)
        set_options(plc_prim, plc.options)

    def read_options_from_stage(self, plc_name):
        plc = self.get_plc(plc_name)
        if plc is None:
            return
        plc_prim = omni.usd.get_context().get_stage().GetPrimAtPath("/PLC/" + plc_name)
        if plc_prim is None:
            return
        plc.options = get_options(plc_prim)

    # Return the names of the PLCs as a list
    def get_plc_names(self):
        plc = self.find_plcs()
        if plc is None:
            return []
        return list(self._components.keys())

    def add_plc(self, name, options):
        input_options = default_properties
        input_options.update(options)
        self.create_plc(name, input_options)
        if name not in self._components:
            self._components[name] = Components(
                Runtime(name, input_options), RuntimeUsd("/PLC/" + name, Manager(name))
            )


def get_options(plc_prim):

    options = default_properties.copy()
    for option in default_properties:
        attr = plc_prim.GetAttribute(option)
        if attr.IsValid():
            options[option] = attr.Get()

    return options


def set_options(plc_prim, options):
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
