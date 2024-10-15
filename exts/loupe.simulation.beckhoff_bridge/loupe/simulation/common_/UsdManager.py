import omni
import omni.usd
from omni.usd import StageEventType
from pxr import Sdf, Tf
from pxr import Usd
from .BridgeManager import BridgeManager
from threading import RLock
from contextlib import contextmanager

ATTR_WRITE_VALUE = "write:value"
ATTR_WRITE_PAUSE = "write:pause"
ATTR_WRITE_ONCE = "write:once"
ATTR_WRITE_SYMBOL = "symbol"


class RuntimeUsd:

    def __init__(self, prim_path, manager: BridgeManager):

        self._root_prim = None
        self._root_prim_path = prim_path
        self._bridge_manager = manager
        self._usd_context = omni.usd.get_context()
        self.edit_layer = 0
        self._stage = self._usd_context.get_stage()

        self._lock = RLock()
        self._data_update = dict()

        self._subscribe()

    def __del__(self):
        self.cleanup()

    @property
    def root_prim(self):
        if self._root_prim is not None:
            return self._root_prim

        self._root_prim = self._stage.GetPrimAtPath(self._root_prim_path)
        if not self._root_prim.IsValid():
            self._root_prim = self._stage.DefinePrim(self._root_prim_path)

        return self._root_prim

    def cleanup(self):
        self._unsubscribe()

    def _on_data_read(self, event):
        data = event.payload["data"]
        data = flatten_obj(data)
        with self._lock:
            self._data_update.update(data)

    def _subscribe(self):

        # Data stream where the extension will dump the data that it reads from the PLC.
        self._event_stream = omni.kit.app.get_app().get_message_bus_event_stream()

        self._stage_event_sub = (
            self._usd_context.get_stage_event_stream().create_subscription_to_pop(
                self._on_stage_event
            )
        )

        self._update_event_sub = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(self._on_update_event)
        )

        self._stage_listener = Tf.Notice.Register(
            Usd.Notice.ObjectsChanged,
            self._notice_changed,
            self._usd_context.get_stage(),
        )

        self._bridge_manager.register_data_callback(self._on_data_read)

    def _unsubscribe(self):
        # unsubscription
        self._update_event_sub = None
        self._stage_event_sub = None
        self._stage_listener = None

    def _notice_changed(self, notice, stage):
        if self._stage.expired:
            return

        for changed in notice.GetChangedInfoOnlyPaths():
            if str(changed).startswith(self._root_prim_path):
                if (
                    changed.name == ATTR_WRITE_VALUE
                    or changed.name == ATTR_WRITE_ONCE
                    or changed.name == ATTR_WRITE_PAUSE
                ):
                    # Get the value of the write attribute
                    changed = str(changed).split(".")[0]
                    prim = self._stage.GetPrimAtPath(str(changed))

                    write_symbol = prim.GetAttribute(ATTR_WRITE_SYMBOL)
                    if not write_symbol.IsValid():
                        continue

                    write_once_attr = prim.GetAttribute(ATTR_WRITE_ONCE)
                    write_pause_attr = prim.GetAttribute(ATTR_WRITE_PAUSE)

                    if write_once_attr.Get() or not write_pause_attr.Get():
                        # Set the write attribute to False
                        write_once_attr.Set(False)

                        # Get the value attribute
                        write_value_attr = prim.GetAttribute(ATTR_WRITE_VALUE)
                        self._bridge_manager.write_variable(
                            write_symbol.Get(), write_value_attr.Get()
                        )

    # callback
    def _on_update_event(self, event):

        if self._stage.expired:
            return

        flat = None
        with self._lock:
            flat = self._data_update
            self._data_update = dict()

        for key, value in flat.items():
            path = self.root_prim.GetPath()
            full_key = path.pathString + "/" + "/".join(key.split("."))
            with layer_context(self._stage, self.edit_layer):
                set_prim_value(self._stage, full_key, key, value)

    def _on_stage_event(self, event):
        if event.type == int(StageEventType.OPENED):
            self._stage = self._usd_context.get_stage()
            self._stage_listener = Tf.Notice.Register(
                Usd.Notice.ObjectsChanged, self._notice_changed, self._stage
            )

        if event.type == int(StageEventType.HIERARCHY_CHANGED):
            pass


@contextmanager
def layer_context(stage, layer_id=0):
    layer = stage.GetLayerStack()[layer_id]
    if not layer:
        layer = stage.GetLayerStack()[0]

    edit_target = Usd.EditTarget(layer)
    with Usd.EditContext(stage, edit_target):
        yield


def set_prim_value(stage, full_key, key, value):
    # Get or create a prim for the variable
    prim = stage.GetPrimAtPath(full_key)

    if not prim:
        prim = stage.DefinePrim(full_key)

    (attr, create) = set_attr(prim, "value", value)
    if create:
        # Set the write attributes
        get_or_create(prim, ATTR_WRITE_VALUE, attr.GetTypeName()).Set(value)
        get_or_create(prim, ATTR_WRITE_ONCE, Sdf.ValueTypeNames.Bool).Set(False)
        get_or_create(prim, ATTR_WRITE_PAUSE, Sdf.ValueTypeNames.Bool).Set(False)
        # Write the symbol last, so that we can detect that it has just been added
        get_or_create(prim, ATTR_WRITE_SYMBOL, Sdf.ValueTypeNames.String).Set(key)


def set_attr(prim, attr_name, value):
    attr = prim.GetAttribute(attr_name)
    created = False
    if not attr:
        created = True
        if type(value) is str:
            attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.String)
        elif type(value) is bool:
            attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Bool)
        else:
            attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Double)

    attr.Set(value)
    return (attr, created)


def get_or_create(prim, attr_name, attr_type):
    attr = prim.GetAttribute(attr_name)
    if not attr:
        attr = prim.CreateAttribute(attr_name, attr_type)
    return attr


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
