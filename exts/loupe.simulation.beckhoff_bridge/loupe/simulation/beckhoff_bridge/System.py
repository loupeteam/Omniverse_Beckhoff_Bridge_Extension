import omni
from pxr import Sdf
from .Runtime import Runtime
from ..common.UsdManager import RuntimeUsd, get_options_from_prim, set_options_on_prim
from .BeckhoffBridge import Manager
from .global_variables import (
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID,
    ATTR_BECKHOFF_BRIDGE_ENABLE,
    ATTR_BECKHOFF_BRIDGE_READ_VARS,
    ATTR_BECKHOFF_BRIDGE_REFRESH,
)  # noqa: E501

"""
    These are the default properties for the Beckhoff Bridge when creating a new PLC
"""
default_properties = {
    ATTR_BECKHOFF_BRIDGE_ENABLE: False,
    ATTR_BECKHOFF_BRIDGE_REFRESH: 20,
    ATTR_BECKHOFF_BRIDGE_AMS_NET_ID: "127.0.0.1.1.1",
    ATTR_BECKHOFF_BRIDGE_READ_VARS: "",  # Ideally this should be a list of variables, but they aren't support on the gui
}


class Components:
    """
    This is a holder for the Runtime and USD components of a single PLC
    """

    def __init__(self, runtime, usd):
        """
        Initializes the System class with runtime and USD parameters.

        Args:
            runtime: The runtime environment for the system.
            usd: The USD (Universal Scene Description) file or object.
        """
        self.runtime = runtime
        self.usd = usd


class System:
    """
    System class for managing multiple PLC objects
    """

    def __init__(self):
        self.init()

    def init(self):
        self._system_root = "/PLC/"
        self._components = dict()

    system_root = property(lambda self: self._system_root)

    def cleanup(self):
        """
        Remove all the runtime and USD objects from the system
        """
        for plc in self._components.values():
            plc.runtime.cleanup()
            plc.usd.cleanup()

        self._components.clear()

    def find_plcs(self) -> dict[str, dict[str, any]]:
        """
        Find all the prims in the stage that have the Bridge parameters
        Return a dictionary of the prim names and their options
        """
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
            names[name] = get_options_from_prim(plc, default_properties)
        return names

    def find_and_create_plcs(self) -> list[str]:
        """
        Find the PLCs defined in the stage and create runtime objects for them
        """
        # Find all the PLCs in the stage
        plcs = self.find_plcs()
        if plcs is None:
            return

        # Add new plcs to the stage
        for name, options in plcs.items():
            if name not in self._components:
                self.add_plc(name, options)

        # Remove plcs that are not in the stage
        for name in list(self._components.keys()):
            if name not in plcs:
                self._components[name].runtime.cleanup()
                self._components[name].usd.cleanup()
                del self._components[name]

        # Return the names of the PLCs
        return self.get_plc_names()

    def create_plc_prim(self, name: str, options: dict) -> str:
        """
        Create a new PLC in the stage with the given name and options
        """
        prim_name = self.system_root + name
        plc_prim = omni.usd.get_context().get_stage().DefinePrim(prim_name)
        set_options_on_prim(plc_prim, options)
        return prim_name

    def get_plc(self, name: str | int) -> Runtime | None:
        """
        Get the runtime object for the given PLC name
        """
        if name not in self._components:
            return None
        return self._components[name].runtime

    def write_options_to_stage(self, plc_name: str | int):
        """
        Write the options for the given PLC from the runtime object to the stage
        """
        plc = self.get_plc(plc_name)
        if plc is None:
            return

        plc_prim = omni.usd.get_context().get_stage().GetPrimAtPath(self.system_root + plc_name)
        if plc_prim is None:
            return

        set_options_on_prim(plc_prim, plc.options)

    def read_options_from_stage(self, plc_name: str | int):
        """
        Read the options for the given PLC from the stage to the runtime object
        """
        plc = self.get_plc(plc_name)
        if plc is None:
            return

        plc_prim = omni.usd.get_context().get_stage().GetPrimAtPath(self.system_root + plc_name)
        if plc_prim is None:
            return

        plc.options = get_options_from_prim(plc_prim, default_properties)

    # Return the names of the PLCs as a list
    def get_plc_names(self) -> list[str]:
        """
        Get the names of all the PLCs in the system
        """        
        plc = self.find_plcs()
        if plc is None:
            return []
        return list(self._components.keys())

    def add_plc(self, name, options):
        """
        Add a new PLC to the system with the given name and options
        Create the PRIM in the stage
        Create the runtime and USD objects for the PLC
        """
        input_options = default_properties.copy()
        input_options.update(options)
        prim_name = self.create_plc_prim(name, input_options)
        if name not in self._components:
            self._components[name] = Components(
                Runtime(name, input_options), RuntimeUsd(prim_name, Manager(name))
            )
