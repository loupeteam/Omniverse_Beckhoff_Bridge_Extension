"""
  File: **Communication.py**
  Copyright (c) 2024 Loupe
  https://loupe.team

  This file is part of Omniverse_Beckhoff_Bridge_Extension, licensed under the MIT License.

  The ADS driver now lives in the plain-Python `beckhoff_bridge` package at the
  repo root (see docs/ARCHITECTURE_PLAN.md). This module only keeps the 0.2.x
  import path working.
"""

from beckhoff_bridge import AdsDriver, AdsReadError, CommunicationDriver  # noqa: F401

__all__ = ["AdsDriver", "AdsReadError", "CommunicationDriver"]
