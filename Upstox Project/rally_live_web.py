"""Live page (/live): the Rally paper trading dashboard (strategies S1, S2, S3) inside this app.

Shows the files written by the Rally paper trader (C:\\Users\\tusha\\Downloads\\Rally\\live). Its only action is the
"Exit now" button, which asks the paper trader to close a PAPER trade at the live price.
Paper trading only - nothing here places orders, and the Upstox project's own rules are not used.
"""
import importlib.util
import json
from pathlib import Path

from flask import Blueprint, Response, jsonify, request

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
    return Response(rally().page({"api": "/live/api/all", "back": "/backtest", "exit_api": "/live/api/exit"}), mimetype="text/html")


@bp.route("/live/api/exit", methods=["POST"])
def live_exit():
    """'Exit now' button: asks the Rally PAPER trader to close a paper trade (no real order is ever sent)."""
    body = request.get_json(silent=True) or {}
    ok, msg = rally().request_exit(str(body.get("id", "")))
    return jsonify(ok=ok, message=msg)


@bp.route("/live/api/all")
def live_data():
    data = json.dumps(rally().all_data(), default=str)
    return Response(data, mimetype="application/json", headers={"Cache-Control": "no-store"})
