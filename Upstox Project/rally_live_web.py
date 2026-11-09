"""Live page (/live): the Rally paper trading dashboard (strategies S1, S2, S3) inside this app.

Read only: it shows the files written by the Rally paper trader (C:\\Users\\tusha\\Downloads\\Rally\\live).
Paper trading only - nothing here places orders, and the Upstox project's own rules are not used.
"""
import importlib.util
import json
from pathlib import Path

from flask import Blueprint, Response

RALLY = Path(r"C:\Users\tusha\Downloads\Rally")
bp = Blueprint("rally_live", __name__)
_mod = {}


def rally():
    """The Rally dashboard module (loaded from the Rally folder, once)."""
    if "m" not in _mod:
        spec = importlib.util.spec_from_file_location("rally_dashboard", RALLY / "rally_dashboard.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _mod["m"] = m
    return _mod["m"]


@bp.route("/live")
def live():
    if not (RALLY / "rally_dashboard.py").exists():
        return Response(f"Rally folder not found: {RALLY}", status=404, mimetype="text/plain")
    return Response(rally().page({"api": "/live/api/all", "back": "/backtest"}), mimetype="text/html")


@bp.route("/live/api/all")
def live_data():
    data = json.dumps(rally().all_data(), default=str)
    return Response(data, mimetype="application/json", headers={"Cache-Control": "no-store"})
