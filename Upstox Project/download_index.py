"""Download 1-minute Nifty 50 INDEX candles from Upstox into data/index (one CSV per month).

Read only (market data). Uses the login saved by run.bat (token.json). Used by the Rally EMA 50/200 study.
Usage:  python download_index.py                 (Jul 2024 .. yesterday; skips months already complete)
        python download_index.py 2024-07 2026-11
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests

HERE = Path(__file__).parent
OUT = HERE / "data" / "index"
KEY = "NSE_INDEX|Nifty 50"
URL = "https://api.upstox.com/v3/historical-candle/{key}/minutes/1/{to}/{frm}"


def token():
    d = json.loads((HERE / "token.json").read_text())
    if d.get("expires_at", 0) <= time.time():
        sys.exit("Upstox login expired - log in with run.bat first.")
    return d["access_token"]


def month_range(a, b):
    y, m = a
    while (y, m) <= b:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    start = tuple(map(int, (args[0] if args else "2024-07").split("-")))
    end_d = date.today() - timedelta(days=1)
    end = tuple(map(int, args[1].split("-"))) if len(args) > 1 else (end_d.year, end_d.month)
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"Accept": "application/json", "Authorization": f"Bearer {token()}"})
    for y, m in month_range(start, end):
        first = date(y, m, 1)
        last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
        last = min(last, end_d)
        f = OUT / f"NSE_INDEX_Nifty50_1minute_{y}-{m:02d}.csv"
        complete = last < end_d.replace(day=1)
        if f.exists() and complete:
            print(f"{y}-{m:02d}: already downloaded")
            continue
        for k in range(3):
            r = s.get(URL.format(key=quote(KEY, safe=""), to=last, frm=first), timeout=60)
            if r.status_code == 200:
                break
            time.sleep(2 + 2 * k)
        body = r.json()
        if r.status_code != 200 or body.get("status") != "success":
            print(f"{y}-{m:02d}: FAILED {r.status_code} {body.get('errors') or body}")
            continue
        c = body["data"]["candles"]
        df = pd.DataFrame(c, columns=["timestamp", "open", "high", "low", "close", "volume", "oi"][:len(c[0])] if c else
                          ["timestamp", "open", "high", "low", "close", "volume", "oi"])
        df = df.sort_values("timestamp")
        df.to_csv(f, index=False)
        days = df.timestamp.str[:10].nunique() if len(df) else 0
        print(f"{y}-{m:02d}: {len(df)} candles, {days} days")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
