"""beckhoff_bridge is plain Python: nothing in it may import Omniverse (omni, carb)."""

import importlib
import re
import sys
from pathlib import Path

KIT_IMPORT = re.compile(r"^\s*(?:import|from)\s+(?:omni|carb)\b", re.MULTILINE)
SRC = Path(__file__).resolve().parents[1] / "src" / "beckhoff_bridge"


def test_importing_the_package_loads_no_kit_module():
    importlib.import_module("beckhoff_bridge")
    loaded = sorted(m for m in sys.modules if m.split(".")[0] in ("omni", "carb"))
    assert loaded == []


def test_no_source_file_imports_kit():
    offenders = [p.name for p in SRC.rglob("*.py") if KIT_IMPORT.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
