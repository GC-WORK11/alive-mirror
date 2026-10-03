"""Pytest path setup — make `server/` and the alive_core build dir importable."""
import os
import sys

_SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SERVER, os.path.join(_SERVER, "core", "build")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
