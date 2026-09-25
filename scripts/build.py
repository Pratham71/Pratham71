"""Build the profile README SVGs into assets/. Run: python scripts/build.py"""
import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONT = ASSETS / "fonts" / "MartianMono[wdth,wght].ttf"
MAX_BYTES = 50_000

C = {
    "ink": "#0A0D10", "panel": "#12171C", "line": "#232B33", "text": "#E6EDF3",
    "muted": "#7D8A96", "amber": "#FFB547", "ok": "#3DDC97",
}
FALLBACK = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


def esc(s):
    return escape(s, {'"': "&quot;"})


def validate(svg):
    size = len(svg.encode("utf-8"))
    if size >= MAX_BYTES:
        raise ValueError(f"svg is {size} bytes, limit {MAX_BYTES}")
    try:
        ET.fromstring(svg)
    except ET.ParseError as e:
        raise ValueError(f"invalid svg: {e}") from e


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)
