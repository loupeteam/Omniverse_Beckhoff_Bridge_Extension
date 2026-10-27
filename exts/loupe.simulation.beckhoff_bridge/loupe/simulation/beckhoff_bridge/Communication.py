"""
DEPRECATED 0.2.x import path: present, with a warning, in 0.3 and 0.4; removed in 0.5.0.

Copyright (c) 2024 Loupe, https://loupe.team
Part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

The ADS driver is the plain-Python `beckhoff_bridge` package:
`from beckhoff_bridge import AdsDriver, AdsReadError`. `CommunicationDriver`
is the same class under its 0.2.x name (same constructor and methods).
"""

import logging
import warnings

from beckhoff_bridge import AdsDriver, AdsReadError, CommunicationDriver  # noqa: F401

_MESSAGE = ("loupe.simulation.beckhoff_bridge.Communication is deprecated since 0.3.0 and will be removed in 0.5.0: "
            "use 'from beckhoff_bridge import AdsDriver, AdsReadError' instead (see MIGRATION.md).")
warnings.warn(_MESSAGE, DeprecationWarning, stacklevel=2)
logging.getLogger(__name__).warning(_MESSAGE)

__all__ = ["AdsDriver", "AdsReadError", "CommunicationDriver"]
