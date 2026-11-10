"""Download Nifty contracts that have NOT expired yet (current futures + the nearest weekly options).

data_download.py only fetches expired contracts, so the newest days are missing until they expire.
This script fills that gap with Upstox's normal history service (read only, no orders):
- futures: the nearest monthly future (95 days of 1-minute candles, like data_download.py)
- options: weekly expiries within the next 10 days, strikes within +/- 4 % of Nifty (27 days each)
- today's candles are added only after 15:35 (the day is complete then)

Files get the same names data_download.py will use after expiry (NSE_FO_<token>_<DD-MM-YYYY>.csv) and are
listed in data/partial_files.csv. After the contract expires, data_download.py downloads it again in full
and removes it from that list. Files already downloaded in full are never touched.

    python download_live.py            # then: python resample_data.py
"""
import csv
import gzip
import json
import sys
from datetime import date, datetime, timedelta
from urllib.parse import quote

import requests

import data_download as dd
import upstox_client as ux

DATA = dd.DATA_DIR
PARTIAL = dd.PARTIAL
INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
BAND = 4.0
LOOKBACK = {"futures": 95, "options": 27}
load_partial, drop_resampled = dd.load_partial, dd.drop_resampled   # drop_resampled: resample_data rebuilds them


def save_partial(rows):
    with PARTIAL.open("w", newline="") as fh:
        w = csv.DictWriter(fh, ["kind", "file", "expiry", "updated"])
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: (r["expiry"], r["file"])))


def nifty_contracts():
    r = requests.get(INSTRUMENTS_URL, timeout=90)
    r.raise_for_status()
    out = []
    for x in json.loads(gzip.decompress(r.content)):
        if x.get("segment") != "NSE_FO" or x.get("instrument_type") not in ("FUT", "CE", "PE"):
            continue
        if x.get("name") != "NIFTY" and x.get("underlying_symbol") != "NIFTY":
            continue
        x["exp"] = datetime.fromtimestamp(x["expiry"] / 1000, ux.IST).date()
        out.append(x)
    return out


def candles(api, key, start, end, today_too):
    rows, cur_end = [], end
    while cur_end >= start:
        cur_start = max(start, cur_end - timedelta(days=27))
        data = api.get(f"/historical-candle/{quote(key, safe='')}/minutes/1/{cur_end}/{cur_start}", base=dd.V3_BASE)
        rows.extend((data or {}).get("candles", []))
        cur_end = cur_start - timedelta(days=1)
    if today_too:
        data = api.get(f"/historical-candle/intraday/{quote(key, safe='')}/minutes/1", base=dd.V3_BASE)
        rows.extend((data or {}).get("candles", []))
    return dd.tidy(rows)


def manifest_add(kind, key, c, n):
    m = DATA / kind / "manifest.csv"
    have = set()
    if m.exists():
        with m.open(newline="") as fh:
            have = {r[0] for r in csv.reader(fh) if r}
    if key not in have:
        with m.open("a", newline="") as fh:
            csv.writer(fh).writerow([key, c.get("trading_symbol", ""), c["exp"], c.get("strike_price", "") if kind == "options" else "",
                                     c["instrument_type"], n])


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    token = ux.load_token()
    if not token:
        print("No valid token. Start run.bat, log in, then run this again.")
        return 1
    now = datetime.now(ux.IST)
    today = now.date()
    today_too = now.hour * 60 + now.minute >= 15 * 60 + 35 and today.weekday() < 5
    end = today - timedelta(days=1)
    print(f"Fetching up to {'today ' + str(today) if today_too else str(end) + ' (today is added after 15:35)'}")
    api = dd.Api(token)
    allc = nifty_contracts()

    futs = sorted((c for c in allc if c["instrument_type"] == "FUT" and c["exp"] >= today), key=lambda c: c["exp"])
    picks = [("futures", futs[0])] if futs else []
    spot = api.get("/market-quote/ltp", {"instrument_key": dd.UNDERLYING}) or {}
    spot = float(next(iter(spot.values()))["last_price"]) if spot else None
    opt_exps = sorted({c["exp"] for c in allc if c["instrument_type"] in ("CE", "PE") and today <= c["exp"] <= today + timedelta(days=10)})
    for e in opt_exps:
        cs = [c for c in allc if c["instrument_type"] in ("CE", "PE") and c["exp"] == e]
        picks += [("options", c) for c in dd.select_options(cs, spot, BAND)]
    print(f"Nifty {spot}; future {futs[0]['trading_symbol'] if futs else '-'}; option expiries {[str(e) for e in opt_exps]}; "
          f"{len(picks)} contracts")

    partial = load_partial()
    # contracts that expired after their partial download: they leave the live list at once, but Upstox can take
    # days to list the expiry - the expired-candle service already answers by key, so fetch them in full now
    problems, finished = [], 0
    for name, r in sorted(partial.items()):
        exp = date.fromisoformat(r["expiry"])
        if exp >= today:
            continue
        tok = name.split("_")[2]
        key = f"NSE_FO|{tok}|{exp:%d-%m-%Y}"
        rows = dd.fetch_candles(api, key, "1minute", exp - timedelta(days=LOOKBACK[r["kind"]]), exp, 28, problems)
        if not rows:
            continue                                       # leave it partial; data_download.py tries later
        with (DATA / r["kind"] / name).open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(dd.HEADER)
            w.writerows(rows)
        drop_resampled(r["kind"], name)
        del partial[name]
        finished += 1
    if finished or problems:
        print(f"Expired since the last run: {finished} contracts downloaded in full ({len(problems)} problems)")
    lots = {}
    done = skipped = 0
    for kind, c in picks:
        key_exp = f"{c['instrument_key']}|{c['exp']:%d-%m-%Y}"       # the name it gets after expiry
        name = dd.safe(key_exp) + ".csv"
        out = DATA / kind / name
        if out.exists() and name not in partial:
            skipped += 1                                            # full expired download already there
            continue
        start = c["exp"] - timedelta(days=LOOKBACK[kind])
        rows = candles(api, c["instrument_key"], start, min(end, c["exp"]), today_too)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(dd.HEADER)
            w.writerows(rows)
        drop_resampled(kind, name)
        manifest_add(kind, key_exp, c, len(rows))
        partial[name] = dict(kind=kind, file=name, expiry=str(c["exp"]), updated=f"{now:%Y-%m-%d %H:%M}")
        if kind == "options" and c.get("lot_size"):
            lots[str(c["exp"])] = int(c["lot_size"])
        done += 1
        if done % 25 == 0:
            print(f"  {done} files ({api.calls} requests)")
    save_partial(partial)
    for e, lot in lots.items():   # lot size for the backtest until the expired contract list exists
        (DATA / "contracts" / f"live_options_{e}.json").write_text(json.dumps([{"lot_size": lot}]))
    print(f"Saved {done} files ({skipped} already complete), {api.calls} requests. Listed in {PARTIAL.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
