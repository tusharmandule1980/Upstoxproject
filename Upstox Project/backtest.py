"""Backtest: Nifty futures 5-minute signals -> buy ATM Nifty call/put options.  P&L is GROSS
(no taxes, brokerage or slippage) unless you set --charges-per-trade.

    python backtest.py                      # everything in data/, 1 lot
    python backtest.py --from 2025-01-01 --lots 2
    python backtest.py --rising-mode both   # looser reading of "increasing vs previous two candles"

How the rules were turned into code (assumptions are listed in README.md too):
  * Signals use 5-minute candles of the nearest-expiry Nifty future (indicators computed per contract).
  * Indicators: EMA 20, ADX / +DI / -DI (Wilder 14), RSI (Wilder 14), MACD line (12, 26, 9).
  * "Increasing vs previous two candles" = higher than the previous candle, which was higher than the one before.
  * Entry at the open of the 1-minute option candle right after the signal candle closes.
    ATM = the strike whose call and put prices are closest (put-call parity; no index data needed).
  * Option expiry = nearest one (including expiry day unless --min-dte says otherwise).
  * Stop = total loss on the trade (lots x lot size x points): Rs 3000 for a CALL, Rs 2500 for a PUT
    (--call-max-loss, --max-loss); checked on every 1-minute candle's low.
  * Trailing (chosen 4 Nov 2026): once the trade is up Rs 3000, the stop keeps half of the best profit
    (--profit-lock-at 3000 --profit-lock-pct 50; --profit-lock-at 0 = no trail). ATM only
    (--profit-lock-variants; it lowered profit on the in-the-money strikes).
    --trail-step 15 --trail-gain 45 = the old step trail (stop up 15 points per 45 points of gain).
  * Entries from 09:25 to 14:25 signal-candle close; anything still open is closed at 14:30.
  * PUT entry keeps ADX rising, as written (--put-adx off drops it; tried on 4 Nov 2026, it lowered profit).
  * Daily loss limit (4 Nov 2026): once a strategy's closed trades have lost Rs 3000 in a day it takes no more trades
    that day, and a trade's stop is cut to what is left of the limit (--daily-loss-cap, --daily-cap-mode; 0 = off).
  * Entry gap (4 Nov 2026): the signal candle must close at least 20 points beyond the 20 EMA (--entry-gap; 0 = off).
  * The EMA exit below needs 2 closes in a row beyond the 20 EMA (--ema-exit-closes; 1 = the first close, as before).
  * Exits (rules of 4 Nov 2026, second change; shown as "EMA exit"):
      CALL: a candle closes below the 20 EMA, unless the average close since 09:15 rose on each of the last two
            candles and is below the close; then the trade stays open.
      PUT:  a candle closes above the 20 EMA, unless the average close since 09:15 fell on each of the last two
            candles and is above the close.
    --mean-hold off exits on the 20 EMA close alone.
  * Earlier exits are still there: --exit-rule di (CALL: +DI falls two candles in a row; PUT: +DI rises two in a row)
    and --put-ema-gap 80 (PUT also exits when the future is more than 80 points below the 20 EMA and that gap shrank
    on each of the last two candles, "EMA gap exit"; a tie with the other exit counts as the other exit).
    The rules used until 4 Nov 2026: --exit-rule di --put-ema-gap 80 --call-max-loss 2500 --trail-step 15
"""
import argparse
import csv
import json
import re
import sys
from functools import lru_cache
from collections import Counter
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from config import BASE_DIR
from resample_data import resample_frame

DATA_DIR = BASE_DIR / "data"
OUT_DIR = DATA_DIR / "backtest"
EPOCH = date(1970, 1, 1)
# name -> (label, strikes in the money). Calls go below ATM, puts above ATM.
VARIANTS = {"atm": ("ATM buy", 0), "itm2": ("ITM 2 buy", 2), "itm5": ("Deep ITM buy (ITM 5)", 5)}


# ---------------------------------------------------------------- indicators
def wilder(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rising(x, mode="consecutive"):
    a, b = x.shift(1), x.shift(2)
    return ((x > a) & (a > b)) if mode == "consecutive" else ((x > a) & (x > b))


def falling(x, mode="consecutive"):
    a, b = x.shift(1), x.shift(2)
    return ((x < a) & (a < b)) if mode == "consecutive" else ((x < a) & (x < b))


def build_signals(d5, a):
    d = d5.copy()
    c, h, l = d["close"], d["high"], d["low"]
    d["ema"] = c.ewm(span=a.ema, adjust=False).mean()
    delta = c.diff()
    ag, al = wilder(delta.clip(lower=0), a.rsi_len), wilder(-delta.clip(upper=0), a.rsi_len)
    d["rsi"] = 100 - 100 / (1 + ag / al)
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=d.index)
    mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=d.index)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = wilder(tr, a.adx_len)
    d["pdi"], d["mdi"] = 100 * wilder(pdm, a.adx_len) / atr, 100 * wilder(mdm, a.adx_len) / atr
    d["adx"] = wilder(100 * (d["pdi"] - d["mdi"]).abs() / (d["pdi"] + d["mdi"]), a.adx_len)
    line = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    d["macd"] = line if a.macd_use == "line" else line - line.ewm(span=9, adjust=False).mean()
    m = a.rising_mode
    # the signal candle must close at least this many points beyond the 20 EMA (4 Nov 2026; older runs: 0)
    eg = getattr(a, "entry_gap", 0)
    d["call"] = ((c > d["ema"]) & (c - d["ema"] >= eg) & rising(d["pdi"], m) & rising(d["adx"], m) & rising(d["rsi"], m)
                 & rising(d["macd"], m))
    if a.put_di == "plus":
        put_di, put_exit = falling(d["pdi"], m), rising(d["pdi"])
    else:
        put_di, put_exit = rising(d["mdi"], m), falling(d["mdi"])
    # a setting missing from an older config.json means that run used the rules from before 4 Nov 2026
    put_adx = rising(d["adx"], m) if getattr(a, "put_adx", "rising") == "rising" else True
    d["put"] = (c < d["ema"]) & (d["ema"] - c >= eg) & put_di & put_adx & falling(d["rsi"], m) & falling(d["macd"], m)
    # average close since 09:15, and whether it rose / fell on each of the last two candles of the same day
    day = d["ts"].dt.normalize()
    g = c.groupby(day)
    mean = g.cumsum() / (g.cumcount() + 1)
    m1, m2 = mean.groupby(day).shift(1), mean.groupby(day).shift(2)
    d["mean"] = mean
    d["call_hold"] = (mean > m1) & (m1 > m2) & (mean < c)
    d["put_hold"] = (mean < m1) & (m1 < m2) & (mean > c)
    # settings missing from an older config.json mean that run used the exits from before 4 Nov 2026
    hold = getattr(a, "mean_hold", "on") == "on"
    if getattr(a, "exit_rule", "di") == "ema":
        below, above = c < d["ema"], c > d["ema"]
        n = int(getattr(a, "ema_exit_closes", 1))  # closes in a row beyond the EMA needed to exit (older runs: 1)
        if n > 1:
            below = below.astype(int).rolling(n).sum().eq(n)
            above = above.astype(int).rolling(n).sum().eq(n)
        d["call_exit"] = below & ~d["call_hold"] if hold else below
        d["put_exit"] = above & ~d["put_hold"] if hold else above
        # candles where the EMA exit was due but the average since 09:15 kept the trade open
        d["call_held"] = below & d["call_hold"] if hold else False
        d["put_held"] = above & d["put_hold"] if hold else False
    else:
        d["call_exit"], d["put_exit"] = falling(d["pdi"]), put_exit
        d["call_held"] = d["put_held"] = False
    gap, max_gap = d["ema"] - c, getattr(a, "put_ema_gap", 0)  # points the future is below its 20 EMA
    d["put_gap_exit"] = (gap > max_gap) & falling(gap) if max_gap else False
    return d


def describe(a):
    """One line with the exit and risk settings of a run (older config.json files lack the newer settings)."""
    rule, put_loss = getattr(a, "exit_rule", "di"), a.max_loss
    call_loss = getattr(a, "call_max_loss", put_loss)
    n = int(getattr(a, "ema_exit_closes", 1))
    if rule == "ema":
        exit_txt = ("candle closes beyond the 20 EMA" if n == 1 else f"{n} closes in a row beyond the 20 EMA") + (
            ", held while the average since 09:15 trends with the price" if getattr(a, "mean_hold", "on") == "on" else "")
    else:
        exit_txt = "+DI" if a.put_di == "plus" else "+DI for calls, -DI for puts"
    stop_txt = f"Rs {call_loss:,.0f} call / Rs {put_loss:,.0f} put" if call_loss != put_loss else f"Rs {put_loss:,.0f}"
    trails = [f"{a.trail_step:g} pts per {a.trail_gain:g} pts"] if a.trail_step > 0 and a.trail_gain > 0 else []
    lock_on = getattr(a, "profit_lock_variants", None)  # missing = every strike choice (runs before ATM-only)
    if getattr(a, "profit_lock_at", 0) > 0 and lock_on != []:
        only = "" if lock_on is None or set(lock_on) >= set(VARIANTS) else \
            " (" + ", ".join(VARIANTS[v][0] for v in lock_on if v in VARIANTS) + " only)"
        trails.append(f"keep {a.profit_lock_pct:g}% of the best profit once up Rs {a.profit_lock_at:,.0f}{only}")
    trail_txt = " + ".join(trails) or "off"
    gap = getattr(a, "put_ema_gap", 0)
    eg = getattr(a, "entry_gap", 0)
    entry_txt = f"entry: close {eg:g}+ pts beyond the 20 EMA | " if eg else ""
    cap = getattr(a, "daily_loss_cap", 0)
    if cap:
        stop_txt += (f" | daily loss limit Rs {cap:,.0f} (no more trades that day"
                     + ("; a trade's stop never risks more than what is left)" if getattr(a, "daily_cap_mode", "") == "tighten" else ")"))
    return (f"{entry_txt}exit: {exit_txt} | stop loss {stop_txt} | trail {trail_txt} | put EMA gap exit: "
            f"{f'{gap:g} pts' if gap else 'off'} | put ADX: {getattr(a, 'put_adx', 'rising')} | square-off {a.square_off}")


# ---------------------------------------------------------------- trade simulation
def simulate(t, o, h, l, c, i0, entry, stop_pts, gain_step, trail_step, di_t, sq_t, day_end, sig_reason="DI exit",
             lock_at=0.0, lock_pct=0.0):
    """Walk 1-minute candles from the entry candle. Returns (index, price, reason, best_gain_points).
    di_t = minute the first indicator exit fires (reported as sig_reason), or None.
    Step trail: every gain_step points of gain moves the stop up trail_step points; 0 for either = off.
    Profit lock: once the best gain reaches lock_at points, the stop keeps lock_pct (0-1) of it; 0 = off.
    The stop only ever moves up."""
    init = entry - stop_pts
    stop, top, last, i, n = init, entry, i0, i0, len(t)
    trail = gain_step > 0 and trail_step > 0
    while i < n and t[i] < day_end:
        ti = t[i]
        if i > i0:
            if ti >= sq_t or (di_t is not None and ti >= di_t):
                reason = sig_reason if (di_t is not None and di_t <= sq_t) else "square-off"
                return i, float(o[i]), reason, top - entry
            if o[i] <= stop:  # gapped through the stop
                return i, float(o[i]), "trail stop" if stop > init else "stop loss", top - entry
        if l[i] <= stop:
            return i, float(stop), "trail stop" if stop > init else "stop loss", top - entry
        if h[i] > top:  # trail is updated after the stop check (conservative)
            top = float(h[i])
            if trail:
                stop = max(stop, init + int((top - entry) // gain_step) * trail_step)
            if lock_at > 0 and top - entry >= lock_at:
                stop = max(stop, entry + lock_pct * (top - entry))
        last, i = i, i + 1
    return last, float(c[last]), "end of data", top - entry


# ---------------------------------------------------------------- data loading
def to_minutes(ts):
    return ts.values.astype("datetime64[m]").astype("int64")


def read_candles(path):
    df = pd.read_csv(path)
    if df.empty:
        return None
    ts = pd.to_datetime(df["timestamp"], format="ISO8601").dt.tz_localize(None)
    return df, ts


def load_futures(a, tf):
    out = {}
    for f in sorted((DATA_DIR / "futures").glob("NSE_FO_*.csv")):
        try:
            exp = datetime.strptime(f.stem.split("_")[-1], "%d-%m-%Y").date()
        except ValueError:
            continue
        r = read_candles(f)
        if r is None:
            continue
        d5 = resample_frame(r[0], tf)
        d5["ts"] = pd.to_datetime(d5["timestamp"], format="ISO8601").dt.tz_localize(None)
        d5 = build_signals(d5.sort_values("ts").reset_index(drop=True), a)
        d5["min"] = to_minutes(d5["ts"])
        days = {}
        for k, dm in enumerate(d5["min"].to_numpy() // 1440):
            lo, _ = days.get(dm, (k, k))
            days[dm] = (lo, k + 1)
        out[exp] = (d5, days)
    return out


def load_manifest():
    chains = {}
    m = DATA_DIR / "options" / "manifest.csv"
    if not m.exists():
        sys.exit("data/options/manifest.csv not found - run the download first.")
    with m.open(newline="") as fh:
        for row in csv.reader(fh):
            if len(row) < 5 or not row[3]:
                continue
            try:
                exp, strike = date.fromisoformat(row[2]), float(row[3])
            except ValueError:
                continue
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", row[0]) + ".csv"
            chains.setdefault(exp, {})[(strike, row[4])] = (DATA_DIR / "options" / name, row[1])
    return chains


@lru_cache(maxsize=None)
def lot_size(exp, fallback):
    # expired contract list first; live_options_* is written by download_live.py for contracts not expired yet
    for name in (f"options_{exp}.json", f"live_options_{exp}.json"):
        try:
            for c in json.loads((DATA_DIR / "contracts" / name).read_text()):
                if c.get("lot_size"):
                    return int(c["lot_size"])
        except (OSError, ValueError):
            pass
    return fallback


def load_chain(paths):
    chain = {}
    for key, (p, sym) in paths.items():
        if not p.exists():
            continue
        r = read_candles(p)
        if r is None:
            continue
        df, ts = r
        chain[key] = {"sym": sym, "file": p.name, "t": to_minutes(ts), "o": df["open"].to_numpy(float), "h": df["high"].to_numpy(float),
                      "l": df["low"].to_numpy(float), "c": df["close"].to_numpy(float)}
    return chain


def last_close(arr, t, stale=5):
    i = np.searchsorted(arr["t"], t, side="right") - 1
    return float(arr["c"][i]) if i >= 0 and t - arr["t"][i] <= stale else None


def pick_atm(chain, t, fut_close):
    """Strike where call and put prices are closest (looks at the last minute BEFORE entry)."""
    strikes = {k for k, ty in chain if ty == "CE"} & {k for k, ty in chain if ty == "PE"}
    best = None
    for k in strikes:
        if abs(k - fut_close) > 600:
            continue
        ce, pe = last_close(chain[(k, "CE")], t - 1), last_close(chain[(k, "PE")], t - 1)
        if ce is None or pe is None:
            continue
        cand = (abs(ce - pe), abs(k - fut_close), k)
        best = cand if best is None or cand < best else best
    if best:
        return best[2]
    k = round(fut_close / 50) * 50
    return k if (k, "CE") in chain and (k, "PE") in chain else None


# ---------------------------------------------------------------- main loop
def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def backtest(a):
    """Runs every timeframe x variant. Returns (DataFrame of trades, Counter of skipped signals)."""
    chains = load_manifest()
    expiries = sorted(chains)
    lo = (date.fromisoformat(a.date_from) - EPOCH).days if a.date_from else -10 ** 9
    hi = (date.fromisoformat(a.date_to) - EPOCH).days if a.date_to else 10 ** 9
    lo = max(lo, (min(expiries) - timedelta(days=30) - EPOCH).days)  # no option data before this
    start_m, last_m, sq_m = hm(a.entry_start), hm(a.last_entry), hm(a.square_off)
    sig_name = "EMA exit" if a.exit_rule == "ema" else "DI exit"
    trailing = a.trail_gain > 0 and a.trail_step > 0
    cap = a.daily_loss_cap
    trades, skipped = [], Counter()
    tm = lambda x: (datetime(1970, 1, 1) + timedelta(minutes=int(x))).strftime("%Y-%m-%d %H:%M")
    for tf in a.timeframes:
        print(f"Timeframe {tf} minutes: loading futures ...", flush=True)
        futs = load_futures(a, tf)
        if not futs:
            sys.exit("No futures data found in data/futures.")
        cache = {}
        day_idx = sorted({d for _, days in futs.values() for d in days})
        for n_day, di in enumerate(d for d in day_idx if lo <= d <= hi):
            day = EPOCH + timedelta(days=int(di))
            cands = [e for e in futs if e >= day and di in futs[e][1]]
            exp = next((e for e in expiries if (e - day).days >= a.min_dte), None)
            if not cands or exp is None:
                continue
            fut_exp = min(cands)
            d5, days = futs[fut_exp]
            i_lo, i_hi = days[di]
            for e in [e for e in cache if e < day]:
                del cache[e]
            mins, close = d5["min"].to_numpy(), d5["close"].to_numpy()
            call, put = d5["call"].to_numpy(), d5["put"].to_numpy()
            call_x, put_x, put_gx = d5["call_exit"].to_numpy(), d5["put_exit"].to_numpy(), d5["put_gap_exit"].to_numpy()
            call_h, put_h = d5["call_held"].to_numpy(), d5["put_held"].to_numpy()
            ind = d5[["ema", "pdi", "adx", "rsi", "macd"]].to_numpy()
            free_at = {v: 0 for v in a.variants}
            day_pnl = {v: 0.0 for v in a.variants}  # P&L of today's closed trades, per strategy
            for k in range(i_lo, i_hi):
                T = int(mins[k]) + tf  # signal candle closes at T
                mod = T % 1440
                if mod < start_m:
                    continue
                if mod > last_m:
                    break
                if not (call[k] or put[k]):
                    continue
                ty = "CE" if call[k] else "PE"
                atm, tried = None, False
                for v in a.variants:
                    if T < free_at[v]:
                        continue
                    if cap and day_pnl[v] <= -cap + 0.01:  # today's loss limit is used up (to the paisa): no more trades
                        skipped[(tf, v, "signal candles after the daily loss limit")] += 1
                        continue
                    if exp not in cache:
                        cache[exp] = load_chain(chains[exp])
                    chain = cache[exp]
                    if not chain:
                        skipped[(tf, v, "no option data for that expiry")] += 1
                        continue
                    if not tried:
                        atm, tried = pick_atm(chain, T, float(close[k])), True
                    if atm is None:
                        skipped[(tf, v, "no ATM strike with data")] += 1
                        continue
                    off = VARIANTS[v][1]
                    strike = atm - 50 * off if ty == "CE" else atm + 50 * off
                    arr = chain.get((strike, ty))
                    if arr is None:
                        skipped[(tf, v, "no option for that strike")] += 1
                        continue
                    i0 = int(np.searchsorted(arr["t"], T, side="left"))
                    if i0 >= len(arr["t"]) or arr["t"][i0] - T > 3 or arr["t"][i0] // 1440 != di:
                        skipped[(tf, v, "no option candle at entry")] += 1
                        continue
                    entry = float(arr["o"][i0])
                    if entry <= 0:
                        continue
                    qty = a.lots * lot_size(exp, a.lot_size_fallback)
                    nz = np.flatnonzero((call_x if ty == "CE" else put_x)[k + 1:i_hi])
                    ke, sig = (k + 1 + int(nz[0]) if len(nz) else None), sig_name  # candle that fires the exit
                    if ty == "PE":  # the EMA gap exit wins only if it fires before the other exit
                        nz = np.flatnonzero(put_gx[k + 1:i_hi])
                        if len(nz) and (ke is None or k + 1 + nz[0] < ke):
                            ke, sig = k + 1 + int(nz[0]), "EMA gap exit"
                    di_t = int(mins[ke]) + tf if ke is not None else None
                    max_loss = a.call_max_loss if ty == "CE" else a.max_loss
                    if cap and a.daily_cap_mode == "tighten":  # never risk more than what is left of today's limit
                        max_loss = min(max_loss, cap + day_pnl[v])
                    lock_rs = a.profit_lock_at if v in a.profit_lock_variants else 0
                    j, px, why, best = simulate(arr["t"], arr["o"], arr["h"], arr["l"], arr["c"], i0, entry,
                                                max_loss / qty, a.trail_gain, a.trail_step, di_t,
                                                di * 1440 + sq_m, (di + 1) * 1440, sig,
                                                lock_rs / qty, a.profit_lock_pct / 100)
                    free_at[v] = int(arr["t"][j])
                    ci = max(i_lo, int(np.searchsorted(mins + tf, int(arr["t"][j]), side="right")) - 1)
                    upto = ci if ke is None else min(ci, ke)
                    holds = int((call_h if ty == "CE" else put_h)[k + 1:upto + 1].sum())
                    pts = px - entry
                    day_pnl[v] += pts * qty - a.charges_per_trade
                    trades.append({
                        "id": len(trades) + 1, "timeframe": tf, "variant": v, "date": day.isoformat(),
                        "side": "CALL" if ty == "CE" else "PUT", "strike": int(strike), "atm_strike": int(atm),
                        "option_symbol": arr["sym"], "expiry": exp.isoformat(), "days_to_expiry": (exp - day).days,
                        "fut_expiry": fut_exp.isoformat(), "qty": qty, "signal_time": tm(T),
                        "entry_time": tm(arr["t"][i0]), "entry_price": round(entry, 2),
                        "exit_time": tm(arr["t"][j]), "exit_price": round(px, 2), "exit_reason": why,
                        "points": round(pts, 2), "best_points": round(best, 2),
                        "trail_steps": int(best // a.trail_gain) if (trailing and best > 0) else 0,
                        "mean_holds": holds, "minutes_held": int(arr["t"][j] - arr["t"][i0]),
                        "pnl": round(pts * qty - a.charges_per_trade, 2), "stop_rs": round(max_loss, 2),
                        "fut_entry": round(float(close[k]), 2), "fut_exit": round(float(close[ci]), 2),
                        "ema": round(float(ind[k][0]), 2), "pdi": round(float(ind[k][1]), 2),
                        "adx": round(float(ind[k][2]), 2), "rsi": round(float(ind[k][3]), 2),
                        "macd": round(float(ind[k][4]), 2), "option_file": arr["file"]})
            if n_day % 50 == 0:
                print(f"  ... {day} ({len(trades)} trades so far)", flush=True)
    return pd.DataFrame(trades), skipped


# ---------------------------------------------------------------- results
def summarize(t):
    if t.empty:
        return {}
    p = t["pnl"].to_numpy()
    eq = np.concatenate([[0.0], np.cumsum(p)])
    wins, losses = p[p > 0], p[p < 0]
    streak = best = 0
    for x in p:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    return {"trades": len(t), "winners": int((p > 0).sum()), "losers": int((p < 0).sum()),
            "win_rate": round(100 * (p > 0).mean(), 1), "total_pnl": round(p.sum(), 2),
            "avg_trade": round(p.mean(), 2), "avg_win": round(wins.mean(), 2) if len(wins) else 0.0,
            "avg_loss": round(losses.mean(), 2) if len(losses) else 0.0,
            "profit_factor": round(wins.sum() / -losses.sum(), 2) if len(losses) else None,
            "max_drawdown": round((eq - np.maximum.accumulate(eq)).min(), 2),
            "best_trade": round(p.max(), 2), "worst_trade": round(p.min(), 2),
            "longest_losing_streak": best, "avg_minutes_held": round(t["minutes_held"].mean(), 1),
            "trading_days": int(t["date"].nunique())}


def breakdown(t, col):
    g = t.groupby(col)["pnl"]
    return pd.DataFrame({"trades": g.size(), "win %": (g.apply(lambda s: (s > 0).mean()) * 100).round(1),
                         "total P&L": g.sum().round(0), "avg P&L": g.mean().round(0)})


def write_report(t, s, skipped, a):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT_DIR / "trades.csv", index=False)
    (OUT_DIR / "summary.json").write_text(json.dumps(s, indent=1))
    t = t.copy()
    t["month"] = t["date"].str[:7]
    eq = np.cumsum(t["pnl"].to_numpy())
    W, H = 860, 260
    lo_, hi_ = min(0, eq.min()), max(0, eq.max())
    span = (hi_ - lo_) or 1
    pts = " ".join(f"{20 + i * (W - 40) / max(1, len(eq) - 1):.1f},{H - 20 - (v - lo_) / span * (H - 40):.1f}" for i, v in enumerate(eq))
    zero = H - 20 - (0 - lo_) / span * (H - 40)

    def table(df):
        head = "".join(f"<th>{c}</th>" for c in [df.index.name or ""] + list(df.columns))
        body = "".join("<tr>" + f"<td>{i}</td>" + "".join(f"<td>{v:,}</td>" for v in r) + "</tr>"
                       for i, r in zip(df.index, df.itertuples(index=False)))
        return f"<table><tr>{head}</tr>{body}</table>"

    cards ="".join(f"<div class=k><b>{v if v is not None else '-'}</b><span>{k.replace('_', ' ')}</span></div>"
                    for k, v in s.items())
    skip = "".join(f"<li>{k}: {v}</li>" for k, v in skipped.items()) or "<li>none</li>"
    html = f"""<!doctype html><html><head><meta charset=utf-8><title>Backtest report</title>
<style>:root{{--bg:#f6f7f9;--card:#fff;--fg:#1c2330;--m:#6b7280;--l:#e5e7eb;--a:#5b3df5}}
@media(prefers-color-scheme:dark){{:root{{--bg:#10131a;--card:#181c26;--fg:#e8ebf2;--m:#9aa3b2;--l:#2a3040;--a:#8b78ff}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,sans-serif}}
main{{max-width:900px;margin:24px auto;padding:0 16px}}section{{background:var(--card);border:1px solid var(--l);border-radius:12px;padding:18px;margin-bottom:16px}}
h1{{font-size:20px}}h2{{font-size:16px;margin:0 0 10px}}.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.k{{border:1px solid var(--l);border-radius:8px;padding:8px 10px}}.k b{{display:block;font-size:17px}}.k span{{color:var(--m);font-size:12px}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:right;padding:5px 8px;border-bottom:1px solid var(--l)}}th:first-child,td:first-child{{text-align:left}}
.m{{color:var(--m)}}svg{{width:100%;height:auto}}</style></head><body><main>
<h1>Backtest report - gross P&amp;L (taxes, brokerage and slippage excluded)</h1>
<p class=m>{t['date'].min()} to {t['date'].max()} | {a.lots} lot(s) | {describe(a)} | rising mode: {a.rising_mode} | put DI: {a.put_di}</p>
<section><h2>Summary (Rs)</h2><div class=g>{cards}</div></section>
<section><h2>Running profit (Rs) after each trade</h2><svg viewBox="0 0 {W} {H}"><line x1=20 x2={W-20} y1={zero:.1f} y2={zero:.1f} stroke="var(--m)" stroke-dasharray="4"/>
<polyline fill=none stroke="var(--a)" stroke-width=2 points="{pts}"/></svg></section>
<section><h2>By month</h2>{table(breakdown(t, 'month'))}</section>
<section><h2>Calls vs puts</h2>{table(breakdown(t, 'side'))}</section>
<section><h2>How trades ended</h2>{table(breakdown(t, 'exit_reason'))}</section>
<section><h2>By days to expiry</h2>{table(breakdown(t, 'days_to_expiry'))}</section>
<section><h2>Signals that could not be traded</h2><ul>{skip}</ul><p class=m>Missing data on Upstox's side, such as 26 Dec 2024.</p></section>
</main></body></html>"""
    (OUT_DIR / "report.html").write_text(html, encoding="utf-8")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="date_from")
    p.add_argument("--to", dest="date_to")
    p.add_argument("--timeframes", type=int, nargs="+", default=[5, 15, 30], help="candle sizes in minutes")
    p.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS),
                   help="atm = at the money, itm2 / itm5 = that many strikes in the money")
    p.add_argument("--lots", type=int, default=1)
    p.add_argument("--max-loss", type=float, default=2500, help="Rs loss on a PUT trade that triggers the stop")
    p.add_argument("--call-max-loss", type=float, default=3000, help="Rs loss on a CALL trade that triggers the stop")
    p.add_argument("--trail-gain", type=float, default=45, help="step trail: points of option gain per step")
    p.add_argument("--trail-step", type=float, default=0,
                   help="step trail: points the stop moves up per step; 0 = no trail (default since 4 Nov 2026, was 15)")
    p.add_argument("--profit-lock-at", type=float, default=3000,
                   help="Rs of open profit on the trade after which the stop keeps --profit-lock-pct of the best "
                        "profit; 0 = off (default 3000 since 4 Nov 2026)")
    p.add_argument("--profit-lock-pct", type=float, default=50, help="percent of the best profit the stop keeps")
    p.add_argument("--profit-lock-variants", nargs="+", choices=list(VARIANTS), default=["atm"],
                   help="strike choices that use the profit lock (default: ATM only, chosen 4 Nov 2026; "
                        "it lowered profit on the in-the-money strikes)")
    p.add_argument("--exit-rule", choices=["ema", "di"], default="ema",
                   help="ema = exit when a candle closes beyond the 20 EMA (rules of 4 Nov 2026); di = the +DI exits used before")
    p.add_argument("--mean-hold", choices=["on", "off"], default="on",
                   help="on = stay in while the average close since 09:15 trends with the price (ema exit only)")
    p.add_argument("--ema", type=int, default=20)
    p.add_argument("--adx-len", type=int, default=14)
    p.add_argument("--rsi-len", type=int, default=14)
    p.add_argument("--macd-use", choices=["line", "hist"], default="line")
    p.add_argument("--rising-mode", choices=["consecutive", "both"], default="consecutive")
    p.add_argument("--put-di", choices=["plus", "minus"], default="plus")
    p.add_argument("--put-adx", choices=["off", "rising"], default="rising",
                   help="ADX in the PUT entry: rising = as written (default), off = not used (lowered profit when tried)")
    p.add_argument("--daily-loss-cap", type=float, default=3000,
                   help="Rs: once a strategy's closed trades have lost this much in a day, it takes no more trades that "
                        "day (default 3000 since 4 Nov 2026; 0 = no limit)")
    p.add_argument("--daily-cap-mode", choices=["tighten", "block"], default="tighten",
                   help="tighten = a trade's stop is also cut to what is left of the day's limit (default); "
                        "block = only stop new trades once the limit is reached")
    p.add_argument("--entry-gap", type=float, default=20,
                   help="the signal candle must close at least this many points beyond the 20 EMA (default 20 since "
                        "4 Nov 2026; 0 = just beyond, as before)")
    p.add_argument("--ema-exit-closes", type=int, default=2,
                   help="closes in a row beyond the 20 EMA needed for the EMA exit (default 2 since 4 Nov 2026; was 1)")
    p.add_argument("--put-ema-gap", type=float, default=0,
                   help="exit a PUT when the future is more than this many points below the 20 EMA and the gap "
                        "shrank on each of the last two candles; 0 = off (default since 4 Nov 2026, was 80)")
    p.add_argument("--min-dte", type=int, default=0, help="1 = skip trades on expiry day")
    p.add_argument("--entry-start", default="09:25")
    p.add_argument("--last-entry", default="14:25")
    p.add_argument("--square-off", default="14:30")
    p.add_argument("--charges-per-trade", type=float, default=0.0)
    p.add_argument("--lot-size-fallback", type=int, default=75)
    return p.parse_args(argv)


def main():
    a = parse_args()
    print("Running the backtest (several minutes; use --timeframes 5 --variants atm for a quick run)...")
    t, skipped = backtest(a)
    if t.empty:
        print("No trades were generated.", dict(skipped))
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT_DIR / "all_trades.csv", index=False)
    cfg = {"args": vars(a), "variants": {k: v[0] for k, v in VARIANTS.items() if k in a.variants},
           "timeframes": a.timeframes, "data_from": t["date"].min(), "data_to": t["date"].max()}
    (OUT_DIR / "config.json").write_text(json.dumps(cfg, indent=1))
    first = t[(t["timeframe"] == a.timeframes[0]) & (t["variant"] == a.variants[0])]
    reasons = {r: n for (tf, v, r), n in skipped.items() if tf == a.timeframes[0] and v == a.variants[0]}
    if not first.empty:
        s = summarize(first)
        write_report(first, s, reasons, a)
    print("\n=== RESULTS (gross, before taxes and charges) ===")
    rows = []
    for (tf, v), g in t.groupby(["timeframe", "variant"], sort=False):
        s = summarize(g)
        rows.append([f"{tf} min", VARIANTS[v][0], s["trades"], s["win_rate"], s["total_pnl"], s["profit_factor"], s["max_drawdown"]])
    print(pd.DataFrame(rows, columns=["candles", "strategy", "trades", "win %", "total P&L", "profit factor", "max drawdown"]).to_string(index=False))
    if not first.empty:
        print(f"\nDetail for {a.timeframes[0]}-minute, {VARIANTS[a.variants[0]][0]}:")
        for k, v in summarize(first).items():
            print(f"{k.replace('_', ' '):>24}: {v}")
        print("Signals not traded:", reasons or "none")
    print(f"\nInteractive dashboard: double-click backtest_dashboard.bat\nAll trades: {OUT_DIR / 'all_trades.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
