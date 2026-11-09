import pathlib
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import data_download as dd  # noqa: E402


def test_rate_limiter_waits():
    t = [0.0]
    slept = []
    rl = dd.RateLimiter(limits=((1, 2),), now=lambda: t[0], sleep=lambda s: (slept.append(s), t.__setitem__(0, t[0] + s)))
    for _ in range(3):
        rl.wait()
    assert slept and abs(sum(slept) - 1.0) < 1e-6


def test_select_options_band():
    cs = [{"strike_price": k} for k in (23000, 24000, 24500, 25000, 26500)]
    got = [c["strike_price"] for c in dd.select_options(cs, 24500, 4)]
    assert got == [24000, 24500, 25000]
    assert len(dd.select_options(cs, None, 4)) == 5


def test_monthly_expiries():
    ds = [date(2025, 4, 3), date(2025, 4, 10), date(2025, 4, 24), date(2025, 5, 8), date(2025, 5, 29)]
    assert dd.monthly_expiries(ds) == [date(2025, 4, 24), date(2025, 5, 29)]


def test_tidy_sorts_and_dedupes():
    rows = [["2025-01-02T09:16:00+05:30", 1, 2, 0, 1, 5, 9], ["2025-01-02T09:15:00+05:30", 1, 1, 1, 1, 1, 1],
            ["2025-01-02T09:15:00+05:30", 1, 1, 1, 1, 1, 1]]
    out = dd.tidy(rows)
    assert len(out) == 2 and out[0][0].endswith("09:15:00+05:30")


def test_parse_dates():
    assert dd.parse_dates(["2025-04-24", "2025-04-17T00:00"]) == [date(2025, 4, 17), date(2025, 4, 24)]


def test_resample_5min():
    import pandas as pd
    import resample_data as rd
    rows = []
    for i in range(10):  # 09:15 .. 09:24
        rows.append([f"2025-01-02T09:{15+i:02d}:00+05:30", 100 + i, 110 + i, 90 + i, 101 + i, 10, 1000 + i])
    df = pd.DataFrame(rows, columns=rd.COLS)
    out = rd.resample_frame(df, 5)
    assert len(out) == 2
    first = out.iloc[0]
    assert first["timestamp"].startswith("2025-01-02T09:15:00") and first["open"] == 100
    assert first["high"] == 114 and first["low"] == 90 and first["close"] == 105
    assert first["volume"] == 50 and first["oi"] == 1004
    assert out.iloc[1]["timestamp"].startswith("2025-01-02T09:20:00")
    assert len(rd.resample_frame(df.iloc[0:0], 5)) == 0
