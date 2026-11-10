"""Web pages and data feeds for the backtest dashboard (served by app.py at /backtest)."""
import argparse
import json
from functools import lru_cache
from pathlib import Path

import pandas as pd
from flask import Blueprint, Response, abort, jsonify, render_template

import backtest as bt
from config import BASE_DIR
from resample_data import resample_frame

bp = Blueprint("bt", __name__)
OUT = BASE_DIR / "data" / "backtest"
DATA = BASE_DIR / "data"

LIST_COLS = ["id", "variant", "date", "side", "strike", "option_symbol", "expiry", "days_to_expiry",
             "signal_time", "entry_time", "entry_price", "exit_time", "exit_price", "exit_reason", "points",
             "best_points", "trail_steps", "mean_holds", "minutes_held", "pnl", "qty", "fut_entry", "fut_exit"]

_trades = {"mtime": None, "df": None}


def trades_df():
    f = OUT / "all_trades.csv"
    if not f.exists():
        return None
    m = f.stat().st_mtime
    if _trades["mtime"] != m:
        _trades["df"], _trades["mtime"] = pd.read_csv(f), m
        futures_day.cache_clear()
    return _trades["df"]


def config():
    f = OUT / "config.json"
    return json.loads(f.read_text()) if f.exists() else None


def stop_rs(args, side):
    """Rs loss that triggers the stop for this side (runs before 4 Nov 2026 used one stop for both)."""
    return args.get("call_max_loss", args["max_loss"]) if side == "CALL" else args["max_loss"]


RALLY_WEB = Path(r"C:\Users\tusha\Downloads\Rally\live\backtest_web.json")   # Rally\export_backtest_web.py


@bp.route("/backtest")
def page():
    return render_template("backtest.html")                # Rally S1, S2, S3 (chosen 10 Nov 2026)


@bp.route("/api/rally/backtest")
def rally_backtest():
    if not RALLY_WEB.exists():
        return jsonify(error="Run Rally\\export_backtest_web.py first."), 404
    return Response(RALLY_WEB.read_bytes(), mimetype="application/json")


@bp.route("/api/bt/meta")
def meta():
    cfg, df = config(), trades_df()
    if cfg is None or df is None:
        return jsonify(error="No backtest results yet. Double-click backtest.bat first."), 404
    a = cfg["args"]
    return jsonify(variants=cfg["variants"], timeframes=cfg["timeframes"], data_from=cfg["data_from"],
                   data_to=cfg["data_to"], max_loss=a["max_loss"], call_max_loss=stop_rs(a, "CALL"), lots=a["lots"],
                   trail_gain=a["trail_gain"], trail_step=a["trail_step"], ema=a["ema"], square_off=a["square_off"],
                   rules=bt.describe(argparse.Namespace(**a)))


@bp.route("/api/bt/trades/<int:tf>")
def trades(tf):
    df = trades_df()
    if df is None:
        abort(404)
    sub = df[df["timeframe"] == tf][[c for c in LIST_COLS if c in df.columns]]  # older runs lack mean_holds
    return Response(sub.to_json(orient="split", index=False), mimetype="application/json")


@lru_cache(maxsize=24)
def futures_day(fut_expiry, tf):
    """5/15/30-minute futures candles with indicators for one contract (computed like the backtest)."""
    key = pd.Timestamp(fut_expiry).strftime("%d-%m-%Y")
    files = list((DATA / "futures").glob(f"NSE_FO_*_{key}.csv"))
    if not files:
        return None
    r = bt.read_candles(files[0])
    if r is None:
        return None
    d5 = resample_frame(r[0], tf)
    d5["ts"] = pd.to_datetime(d5["timestamp"], format="ISO8601").dt.tz_localize(None)
    ns = argparse.Namespace(**config()["args"])
    return bt.build_signals(d5.sort_values("ts").reset_index(drop=True), ns)


@bp.route("/api/bt/trade/<int:trade_id>")
def trade(trade_id):
    df = trades_df()
    if df is None:
        abort(404)
    row = df[df["id"] == trade_id]
    if row.empty:
        abort(404)
    t = row.iloc[0].to_dict()
    cfg = config()["args"]
    out = {"trade": {k: (v.item() if hasattr(v, "item") else v) for k, v in t.items()},
           # the trade's own stop (it can be tighter near the daily loss limit); older runs only have the config's
           "stop_points": round((t.get("stop_rs") or stop_rs(cfg, t["side"])) / t["qty"], 2), "futures": [], "option": []}
    d = futures_day(t["fut_expiry"], int(t["timeframe"]))
    if d is not None:
        day = d[d["ts"].dt.strftime("%Y-%m-%d") == t["date"]]
        for _, r in day.iterrows():
            ema = None if pd.isna(r["ema"]) else round(float(r["ema"]), 2)
            mean = None if pd.isna(r["mean"]) else round(float(r["mean"]), 2)  # average close since 09:15
            out["futures"].append({"m": r["ts"].hour * 60 + r["ts"].minute, "o": r["open"], "h": r["high"],
                                   "l": r["low"], "c": r["close"], "ema": ema, "mean": mean})
    f = DATA / "options" / t["option_file"]
    if f.exists():
        r = bt.read_candles(f)
        if r is not None:
            raw, ts = r
            keep = ts.dt.strftime("%Y-%m-%d") == t["date"]
            for tt, o, h, l, c in zip(ts[keep], raw["open"][keep], raw["high"][keep], raw["low"][keep], raw["close"][keep]):
                out["option"].append({"m": tt.hour * 60 + tt.minute, "o": o, "h": h, "l": l, "c": c})
    return Response(json.dumps(out, default=float), mimetype="application/json")
