"""
Beckhoff PLC driver over ADS (pyads). No Omniverse dependency.

Copyright (c) 2024 Loupe, https://loupe.team
Part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.
"""

from .driver import AdsDriver, AdsReadError, parse_flat_plc_var_to_dict

# 0.2.x name, kept so `from ... import CommunicationDriver` still works.
CommunicationDriver = AdsDriver

__all__ = [
    "AdsDriver",
    "AdsReadError",
    "CommunicationDriver",
    "parse_flat_plc_var_to_dict",
]
