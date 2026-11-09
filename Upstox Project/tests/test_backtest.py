import csv
import json
import pathlib
import re
import sys
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import backtest as bt  # noqa: E402


def arrs(rows):
    """rows: (minute, open, high, low, close) -> arrays like the backtest uses."""
    a = np.array(rows, dtype=float)
    return a[:, 0].astype("int64"), a[:, 1], a[:, 2], a[:, 3], a[:, 4]


BIG = 10 ** 9


def test_stop_loss_hit():
    t, o, h, l, c = arrs([(0, 100, 101, 99, 100), (1, 100, 100, 60, 65)])
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, None, BIG, BIG)
    assert (i, why) == (1, "stop loss") and abs(px - 66.67) < 0.01


def test_gap_through_stop_exits_at_open():
    t, o, h, l, c = arrs([(0, 100, 101, 99, 100), (1, 50, 55, 45, 50)])
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, None, BIG, BIG)
    assert px == 50 and why == "stop loss"


def test_trailing_stop_moves_up_15_per_45():
    # gain of 50 pts -> one step -> stop = 100 - 33.33 + 15 = 81.67
    t, o, h, l, c = arrs([(0, 100, 150, 99, 140), (1, 140, 141, 80, 85)])
    i, px, why, best = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, None, BIG, BIG)
    assert why == "trail stop" and abs(px - 81.67) < 0.01 and best == 50


def test_two_steps():
    t, o, h, l, c = arrs([(0, 100, 195, 99, 190), (1, 190, 191, 96, 100)])  # +95 -> 2 steps -> stop 96.67
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, None, BIG, BIG)
    assert abs(px - 96.67) < 0.01


def test_di_exit_at_open_of_trigger_minute():
    t, o, h, l, c = arrs([(0, 100, 101, 99, 100), (5, 103, 104, 102, 103), (10, 106, 107, 105, 106)])
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, 10, BIG, BIG)
    assert (i, px, why) == (2, 106.0, "DI exit")


def test_square_off():
    t, o, h, l, c = arrs([(0, 100, 101, 99, 100), (5, 103, 104, 102, 103), (10, 106, 107, 105, 106)])
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, None, 5, BIG)
    assert (i, px, why) == (1, 103.0, "square-off")


def test_end_of_data():
    t, o, h, l, c = arrs([(0, 100, 101, 99, 100), (1, 100, 102, 99, 101)])
    assert bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, None, BIG, 5)[2] == "end of data"


def test_rising_modes():
    x = pd.Series([1, 3, 2, 4.0])
    assert list(bt.rising(x, "consecutive")) == [False, False, False, False]
    assert list(bt.rising(x, "both")) == [False, False, False, True]
    assert list(bt.falling(pd.Series([5, 4, 3.0]))) == [False, False, True]


def five_minute_times(n, start="2024-12-02"):
    """09:15, 09:20 ... 15:25 on weekdays, like the 5-minute futures candles."""
    out, day = [], pd.Timestamp(start)
    while len(out) < n:
        if day.weekday() < 5:
            out += list(pd.date_range(day + pd.Timedelta(hours=9, minutes=15), periods=75, freq="5min"))
        day += pd.Timedelta(days=1)
    return pd.Series(out[:n])


def test_rsi_is_100_in_a_straight_rise():
    a = bt.parse_args([])
    n = 80
    c = pd.Series(np.arange(n, dtype=float) + 100)
    d = pd.DataFrame({"ts": five_minute_times(n), "open": c, "high": c + 1, "low": c - 1, "close": c})
    out = bt.build_signals(d, a)
    assert abs(out["rsi"].iloc[-1] - 100) < 1e-6 and out["pdi"].iloc[-1] > out["mdi"].iloc[-1]


def wandering_futures(n=400, seed=3):
    """Random 5-minute closes with a sharp fall in the middle, so the price ends up far below its 20 EMA."""
    steps = np.random.default_rng(seed).normal(0, 8, n)
    steps[150:200] -= 12
    c = pd.Series(25000 + np.cumsum(steps))
    return pd.DataFrame({"ts": five_minute_times(n), "open": c.shift(fill_value=c[0]), "high": c + 5, "low": c - 5,
                         "close": c})


def test_rule_defaults():
    a = bt.parse_args([])  # chosen on 4 Nov 2026 (second change): 20 EMA exits with the 09:15-average hold
    assert (a.exit_rule, a.mean_hold, a.call_max_loss, a.max_loss) == ("ema", "on", 3000, 2500)
    assert (a.trail_step, a.profit_lock_at, a.profit_lock_pct, a.put_ema_gap, a.put_adx) == (0, 3000, 50, 0, "rising")
    assert a.profit_lock_variants == ["atm"]  # the trail is for ATM only (4 Nov 2026)
    assert (a.entry_gap, a.ema_exit_closes) == (20, 2)  # 20-point entry gap, 2 closes for the EMA exit (4 Nov 2026)
    assert (a.daily_loss_cap, a.daily_cap_mode) == (3000, "tighten")  # daily loss limit (4 Nov 2026)
    assert "daily loss limit Rs 3,000" in bt.describe(a)


def test_entry_gap():
    d = wandering_futures()
    out = bt.build_signals(d, bt.parse_args([]))
    loose = bt.build_signals(d, bt.parse_args(["--entry-gap", "0"]))
    gap = out["close"] - out["ema"]
    assert out["call"].equals(loose["call"] & (gap >= 20)) and out["put"].equals(loose["put"] & (-gap >= 20))
    assert loose["call"].sum() + loose["put"].sum() > out["call"].sum() + out["put"].sum()


def test_ema_exit_needs_two_closes():
    d = wandering_futures()
    out = bt.build_signals(d, bt.parse_args([]))
    c, ema = out["close"], out["ema"]
    below2 = (c < ema) & (c.shift(1) < ema.shift(1))
    above2 = (c > ema) & (c.shift(1) > ema.shift(1))
    assert out["call_exit"].equals(below2 & ~out["call_hold"]) and out["put_exit"].equals(above2 & ~out["put_hold"])
    one = bt.build_signals(d, bt.parse_args(["--ema-exit-closes", "1"]))
    assert (out["call_exit"] <= one["call_exit"] | out["call_hold"]).all() and one["call_exit"].sum() > out["call_exit"].sum()


def test_average_since_0915_starts_again_each_day():
    d = wandering_futures()
    out = bt.build_signals(d, bt.parse_args([]))
    for _, g in out.groupby(d["ts"].dt.date):
        closes = g["close"].to_numpy()
        assert np.allclose(g["mean"].to_numpy(), np.cumsum(closes) / np.arange(1, len(closes) + 1))


def test_ema_exit_and_mean_hold():
    d = wandering_futures()
    out = bt.build_signals(d, bt.parse_args(["--ema-exit-closes", "1"]))
    c, ema, mean, day = out["close"], out["ema"], out["mean"], d["ts"].dt.date
    m1, m2 = mean.groupby(day).shift(1), mean.groupby(day).shift(2)  # never compares with the day before
    call_hold = (mean > m1) & (m1 > m2) & (mean < c)
    put_hold = (mean < m1) & (m1 < m2) & (mean > c)
    assert ((c < ema) & call_hold).any() and ((c > ema) & put_hold).any(), "the data should exercise the hold"
    assert out["call_exit"].equals((c < ema) & ~call_hold) and out["put_exit"].equals((c > ema) & ~put_hold)
    assert out["call_held"].equals((c < ema) & call_hold) and out["put_held"].equals((c > ema) & put_hold)
    off = bt.build_signals(d, bt.parse_args(["--mean-hold", "off", "--ema-exit-closes", "1"]))
    assert off["call_exit"].equals(c < ema) and off["put_exit"].equals(c > ema)
    assert not off["call_held"].any() and not off["put_held"].any()


def test_old_di_exits_still_available():
    d = wandering_futures()
    out = bt.build_signals(d, bt.parse_args(["--exit-rule", "di"]))
    assert out["call_exit"].equals(bt.falling(out["pdi"])) and out["put_exit"].equals(bt.rising(out["pdi"]))
    old = bt.parse_args([])  # a config.json from before 4 Nov 2026 has no exit_rule: it used the DI exits
    del old.exit_rule, old.mean_hold, old.call_max_loss, old.entry_gap, old.ema_exit_closes
    assert bt.build_signals(d, old)["call_exit"].equals(out["call_exit"])
    assert "exit: +DI" in bt.describe(old) and "stop loss Rs 2,500 |" in bt.describe(old)


def test_describe_new_rules():
    text = bt.describe(bt.parse_args([]))
    assert "20 EMA" in text and "Rs 3,000 call / Rs 2,500 put" in text
    assert "entry: close 20+ pts beyond the 20 EMA" in text and "2 closes in a row beyond the 20 EMA" in text
    assert "trail keep 50% of the best profit once up Rs 3,000 (ATM buy only)" in text
    every = bt.describe(bt.parse_args(["--profit-lock-variants", "atm", "itm2", "itm5"]))
    assert "once up Rs 3,000 |" in every
    assert "trail off" in bt.describe(bt.parse_args(["--profit-lock-at", "0"]))
    assert "trail 15 pts per 45 pts |" in bt.describe(bt.parse_args(["--trail-step", "15", "--profit-lock-at", "0"]))


def test_no_trail_by_default():
    # up 50 points, then a fall: with no trail the stop stays where it started, so it is a stop loss
    t, o, h, l, c = arrs([(0, 100, 150, 99, 140), (1, 140, 141, 60, 65)])
    i, px, why, best = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 0, None, BIG, BIG)
    assert why == "stop loss" and abs(px - 66.67) < 0.01 and best == 50


def test_profit_lock_keeps_half_of_the_best_gain():
    # up 60 points (lock starts at 40), so the stop moves to 100 + 30 = 130; the fall to 120 exits there
    t, o, h, l, c = arrs([(0, 100, 160, 99, 150), (1, 150, 151, 120, 125)])
    i, px, why, best = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 0, None, BIG, BIG, "EMA exit", 40, 0.5)
    assert (i, why, best) == (1, "trail stop", 60) and abs(px - 130) < 1e-9


def test_profit_lock_waits_for_its_level():
    t, o, h, l, c = arrs([(0, 100, 130, 99, 125), (1, 125, 126, 60, 65)])  # up only 30 of the 40 needed
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 0, None, BIG, BIG, "EMA exit", 40, 0.5)
    assert why == "stop loss" and abs(px - 66.67) < 0.01


def test_stop_never_moves_down():
    # with both trails on, the higher stop wins: the lock's 130, not the step trail's 81.67
    t, o, h, l, c = arrs([(0, 100, 160, 99, 150), (1, 150, 151, 120, 125)])
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, None, BIG, BIG, "EMA exit", 40, 0.5)
    assert why == "trail stop" and abs(px - 130) < 1e-9


def test_put_entry_adx_switch():
    d = wandering_futures()

    def rule(out, adx):
        return ((out["close"] < out["ema"]) & (out["ema"] - out["close"] >= 20) & bt.falling(out["pdi"]) & adx
                & bt.falling(out["rsi"]) & bt.falling(out["macd"]))

    default = bt.build_signals(d, bt.parse_args([]))
    without = bt.build_signals(d, bt.parse_args(["--put-adx", "off"]))
    assert default["put"].equals(rule(default, bt.rising(default["adx"])))
    assert without["put"].equals(rule(without, True))
    assert (default["put"] <= without["put"]).all() and without["put"].sum() > default["put"].sum()


def test_put_ema_gap_exit():
    d = wandering_futures()
    out = bt.build_signals(d, bt.parse_args(["--put-ema-gap", "80"]))
    gap = out["ema"] - out["close"]
    expect = (gap > 80) & (gap < gap.shift(1)) & (gap.shift(1) < gap.shift(2))
    assert expect.any() and out["put_gap_exit"].equals(expect)
    assert not bt.build_signals(d, bt.parse_args([]))["put_gap_exit"].any()  # off by default since 4 Nov 2026


def test_indicator_exit_label():
    t, o, h, l, c = arrs([(0, 100, 101, 99, 100), (5, 103, 104, 102, 103), (10, 106, 107, 105, 106)])
    i, px, why, _ = bt.simulate(t, o, h, l, c, 0, 100, 33.33, 45, 15, 10, BIG, BIG, "EMA gap exit")
    assert (i, px, why) == (2, 106.0, "EMA gap exit")


# ---------------------------------------------------------------- end to end on made-up data
def make_world(root):
    rng = np.random.default_rng(7)
    (root / "futures").mkdir(parents=True)
    (root / "options").mkdir()
    (root / "contracts").mkdir()
    days = [d for d in (date(2024, 12, 2) + timedelta(n) for n in range(0, 60)) if d.weekday() < 5]
    mins = np.arange(375)
    price = {}
    level = 23800.0
    for d in days:  # a wandering price with trends
        steps = rng.normal(0, 3.0, 375) + 0.8 * np.sin(np.arange(375) / 40.0 + d.toordinal())
        price[d] = level + np.cumsum(steps)
        level = price[d][-1]
    H = ["timestamp", "open", "high", "low", "close", "volume", "oi"]

    def ts(d, m):
        return (datetime(d.year, d.month, d.day, 9, 15) + timedelta(minutes=int(m))).isoformat() + "+05:30"

    fut_exp = date(2025, 1, 30)
    with (root / "futures" / "NSE_FO_1_30-01-2025.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(H)
        for d in days:
            if d <= fut_exp:
                p = price[d] + 80
                for m in mins:
                    w.writerow([ts(d, m), p[m - 1] if m else p[0], p[m] + 2, p[m] - 2, p[m], 10, 100])
    man = []
    for e in [date(2025, 1, 2), date(2025, 1, 9), date(2025, 1, 16), date(2025, 1, 23), date(2025, 1, 30)]:
        json.dump([{"lot_size": 75}], (root / "contracts" / f"options_{e}.json").open("w"))
        for strike in range(22800, 24900, 50):
            for ty in ("CE", "PE"):
                key = f"NSE_FO|{strike}{ty}|{e.strftime('%d-%m-%Y')}"
                path = root / "options" / (re.sub(r"[^A-Za-z0-9._-]+", "_", key) + ".csv")
                n = 0
                with path.open("w", newline="") as fh:
                    w = csv.writer(fh)
                    w.writerow(H)
                    for d in days:
                        if not (e - timedelta(days=20) <= d <= e):
                            continue
                        left = (e - d).days
                        tv = 25 + 12 * np.sqrt(left + 0.5)
                        f = price[d]
                        intr = np.maximum(f - strike, 0) if ty == "CE" else np.maximum(strike - f, 0)
                        p = np.maximum(intr + tv, 0.5)
                        for m in mins:
                            w.writerow([ts(d, m), p[max(m - 1, 0)], p[m] + 1.5, max(p[m] - 1.5, 0.05), p[m], 5, 50])
                            n += 1
                man.append([key, f"N {strike} {ty}", e.isoformat(), strike, ty, n])
    with (root / "options" / "manifest.csv").open("w", newline="") as fh:
        csv.writer(fh).writerows(man)


def test_end_to_end(tmp_path):
    make_world(tmp_path)
    bt.DATA_DIR, bt.OUT_DIR = tmp_path, tmp_path / "backtest"
    a = bt.parse_args(["--from", "2024-12-20", "--max-loss", "2500", "--timeframes", "5", "--variants", "atm", "itm2"])
    trades, skipped = bt.backtest(a)
    assert len(trades) > 3, "the made-up market should produce some trades"
    expected = (trades["exit_price"] - trades["entry_price"]) * trades["qty"]
    assert ((trades["pnl"] - expected).abs() <= trades["qty"] * 0.011).all()  # prices are rounded to 2 decimals
    ent = trades["entry_time"].str[11:].map(lambda s: int(s[:2]) * 60 + int(s[3:]))
    ext = trades["exit_time"].str[11:].map(lambda s: int(s[:2]) * 60 + int(s[3:]))
    assert ent.min() >= 9 * 60 + 25 and ent.max() <= 14 * 60 + 28
    assert (ext <= 14 * 60 + 30).all()
    assert trades["pnl"].min() > -3000 * 1.6  # stop works (small overshoot only from gaps)
    assert set(trades["exit_reason"]) <= {"EMA exit", "stop loss", "trail stop", "square-off", "end of data"}
    assert (trades["trail_steps"] == 0).all() and (trades["mean_holds"] >= 0).all()
    assert set(trades["variant"]) == {"atm", "itm2"}
    for _, g in trades.groupby("variant"):  # one trade at a time, per variant
        for (_, r1), (_, r2) in zip(g.iterrows(), g.iloc[1:].iterrows()):
            assert r2["entry_time"] >= r1["exit_time"] or r2["date"] != r1["date"]
    # an ITM 2 call uses a strike 100 below ATM, a put 100 above
    itm = trades[trades["variant"] == "itm2"]
    assert ((itm["side"] == "CALL") & (itm["strike"] == itm["atm_strike"] - 100) | (itm["side"] == "PUT") & (itm["strike"] == itm["atm_strike"] + 100)).all()
    first = trades[trades["variant"] == "atm"]
    s = bt.summarize(first)
    bt.write_report(first, s, {}, a)
    assert (tmp_path / "backtest" / "report.html").exists() and (tmp_path / "backtest" / "trades.csv").exists()
    # tiny stops, so they are hit: a call stops out at its own loss, a put at its own
    tiny = bt.parse_args(["--from", "2024-12-20", "--call-max-loss", "50", "--max-loss", "40", "--timeframes", "5",
                          "--variants", "atm"])
    t2, _ = bt.backtest(tiny)
    # daily loss limit: no trade starts once the day has lost the limit, and none risks more than what is left
    base = ["--from", "2024-12-20", "--timeframes", "5", "--variants", "atm", "--entry-gap", "0", "--max-loss", "60",
            "--call-max-loss", "60"]
    capped, sk = bt.backtest(bt.parse_args(base + ["--daily-loss-cap", "100"]))
    for _, g in capped.groupby("date"):
        before = g["pnl"].cumsum().shift(fill_value=0)
        assert (before > -100 + 0.01).all() and (g["stop_rs"] <= 100 + before + 1e-6).all()
        assert g["pnl"].sum() >= -100 - 0.01 or (g["exit_price"] < g["entry_price"] - g["stop_rs"] / g["qty"]).any()
    assert any("daily loss limit" in r for (_, _, r) in sk), "the made-up market should hit the limit sometimes"
    free, _ = bt.backtest(bt.parse_args(base + ["--daily-loss-cap", "0"]))
    assert len(free) > len(capped) and (free["stop_rs"] == 60).all()
    # the profit lock only on ATM: with a lock level of Rs 1 an ATM trade that gains at all trails, ITM 2 never does
    t3, _ = bt.backtest(bt.parse_args(["--from", "2024-12-20", "--profit-lock-at", "1", "--timeframes", "5",
                                       "--variants", "atm", "itm2"]))
    assert (t3[t3["variant"] == "atm"]["exit_reason"] == "trail stop").any()
    assert not (t3[t3["variant"] == "itm2"]["exit_reason"] == "trail stop").any()
    sl = t2[t2["exit_reason"] == "stop loss"]
    assert set(sl["side"]) == {"CALL", "PUT"}
    assert (sl[sl["side"] == "CALL"]["pnl"] <= -49.99).all() and (sl[sl["side"] == "PUT"]["pnl"] <= -39.99).all()
    assert (sl[sl["side"] == "CALL"]["pnl"] - -50).abs().min() < 0.01 and (sl[sl["side"] == "PUT"]["pnl"] - -40).abs().min() < 0.01
