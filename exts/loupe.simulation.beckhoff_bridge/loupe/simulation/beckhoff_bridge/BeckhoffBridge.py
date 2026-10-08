"""
DEPRECATED 0.2.x import path, kept through 0.3.x.

Copyright (c) 2024 Loupe, https://loupe.team
Part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

    from loupe.simulation.beckhoff_bridge import BeckhoffBridge   # 0.2.x
    from loupe.simulation.bridge import Manager, get_system       # 0.3.0

`Manager`, `get_system`, `get_stream_name` and the `EVENT_TYPE_*` constants
come from the framework extension. `Manager` talks on the 0.2.x bus names
(`loupe.simulation.beckhoff_bridge.*`) while the framework still pushes them
(setting `/exts/loupe.simulation.bridge/legacyBusNames`, on in 0.3), so its
callbacks get the 0.2.x payloads, and the constants are those names. With the
setting off, `Manager` talks on the neutral names. See docs/MIGRATION.md.
"""

import logging
import warnings

from loupe.simulation.bridge import Manager as _Manager
from loupe.simulation.bridge import get_system  # noqa: F401
from loupe.simulation.bridge.BridgeManager import Manager_Events as _Events
from loupe.simulation.bridge.bus import BUS_NAMESPACE, get_stream_name, legacy_bus_names_enabled  # noqa: F401

from .extension import LEGACY_NAMESPACE

_MESSAGE = (
    "loupe.simulation.beckhoff_bridge.BeckhoffBridge is deprecated since 0.3.0 and will be removed in 0.5.0: "
    "import Manager and get_system from loupe.simulation.bridge instead (see the extension's MIGRATION.md)."
)
warnings.warn(_MESSAGE, DeprecationWarning, stacklevel=2)
# Python hides a DeprecationWarning raised outside __main__; put it in the log as well.
logging.getLogger(__name__).warning(_MESSAGE)

beckhoff_bridge_name = LEGACY_NAMESPACE
Manager_Events = _Events(LEGACY_NAMESPACE)
EVENT_TYPE_DATA_INIT = Manager_Events.EVENT_TYPE_DATA_INIT
EVENT_TYPE_DATA_READ = Manager_Events.EVENT_TYPE_DATA_READ
EVENT_TYPE_DATA_READ_REQ = Manager_Events.EVENT_TYPE_DATA_READ_REQ
EVENT_TYPE_DATA_WRITE_REQ = Manager_Events.EVENT_TYPE_DATA_WRITE_REQ
EVENT_TYPE_CONNECTION = Manager_Events.EVENT_TYPE_CONNECTION
EVENT_TYPE_STATUS = Manager_Events.EVENT_TYPE_STATUS
EVENT_TYPE_ENABLE = Manager_Events.EVENT_TYPE_ENABLE


class Manager(_Manager):
    """
    The framework's `Manager` on the 0.2.x bus names: `Manager("PLC1")` as in
    0.2.x. The no-name `Manager()` form was removed in 0.3.0 and raises.
    """

    def __init__(self, Name: str = None):
        # The framework raises on a missing name before it sets this, and its
        # __del__ then fails on the half-built object; give __del__ what it needs.
        self._callbacks = []
        namespace = LEGACY_NAMESPACE if legacy_bus_names_enabled() else BUS_NAMESPACE
        super().__init__(Name, namespace=namespace)
