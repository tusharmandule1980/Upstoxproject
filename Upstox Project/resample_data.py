"""Build 3, 5 and 15-minute candles from the downloaded 1-minute files.

    python resample_data.py                 # 3, 5 and 15 minute, options + futures
    python resample_data.py --minutes 5 10  # choose your own

Reads  data/options/*.csv and data/futures/*.csv  (1-minute)
Writes data/options_3minute/, data/options_5minute/ ... (same file names).
Candles start at 09:15 like the exchange's: 3-min = 9:15, 9:18, ...; 15-min = 9:15, 9:30, ...
Safe to re-run: files already built are skipped.
"""
import argparse
import sys

import pandas as pd

from config import BASE_DIR

DATA_DIR = BASE_DIR / "data"
COLS = ["timestamp", "open", "high", "low", "close", "volume", "oi"]


def resample_frame(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLS)
    df = df.copy()
    ts = pd.to_datetime(df["timestamp"], format="ISO8601")
    session_start = ts.dt.normalize() + pd.Timedelta(hours=9, minutes=15)
    bucket = ((ts - session_start).dt.total_seconds() // 60 // minutes).astype(int)
    df["candle"] = session_start + pd.to_timedelta(bucket * minutes, unit="m")
    g = df.groupby("candle", sort=True)
    out = pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
        "close": g["close"].last(), "volume": g["volume"].sum(), "oi": g["oi"].last(),
    }).reset_index()
    out["timestamp"] = out["candle"].apply(lambda t: t.isoformat())
    return out[COLS]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--minutes", type=int, nargs="+", default=[3, 5, 15])
    a = p.parse_args(argv)
    made = skipped = 0
    for kind in ("options", "futures"):
        src = DATA_DIR / kind
        if not src.exists():
            continue
        files = sorted(src.glob("*.csv"))
        files = [f for f in files if f.name != "manifest.csv"]
        for m in a.minutes:
            dst = DATA_DIR / f"{kind}_{m}minute"
            dst.mkdir(exist_ok=True)
            for f in files:
                out = dst / f.name
                if out.exists():
                    skipped += 1
                    continue
                resample_frame(pd.read_csv(f), m).to_csv(out, index=False)
                made += 1
            man = src / "manifest.csv"
            if man.exists():
                (dst / "manifest.csv").write_bytes(man.read_bytes())
            print(f"{kind} {m}-minute done")
    print(f"Created {made} files, skipped {skipped} already built.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
