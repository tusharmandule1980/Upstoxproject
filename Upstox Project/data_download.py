"""Download expired Nifty options/futures candles from Upstox into ./data as CSV.

Needs: Upstox Plus plan + a valid login today (run the web app and log in first).
Resumable: contracts already saved are skipped, so you can stop and re-run any time.

Examples
    python data_download.py --dry-run                 # count contracts/requests, download nothing
    python data_download.py --limit-expiries 1        # small test run
    python data_download.py                           # full run: 3 years, 1-minute, options + futures
    python data_download.py --interval 5minute --band 3
"""
import argparse
import csv
import json
import math
import re
import sys
import time
from collections import deque
from datetime import date, datetime, timedelta
from urllib.parse import quote

import requests

import upstox_client as ux
from config import API_BASE, BASE_DIR

DATA_DIR = BASE_DIR / "data"
V3_BASE = API_BASE.replace("/v2", "/v3")
UNDERLYING = "NSE_INDEX|Nifty 50"
INTERVALS = ("1minute", "3minute", "5minute", "15minute", "30minute", "day")
HEADER = ["timestamp", "open", "high", "low", "close", "volume", "oi"]


class TokenExpired(Exception):
    pass


class ApiError(Exception):
    def __init__(self, status, text):
        super().__init__(f"HTTP {status}: {text}")
        self.status = status


class RateLimiter:
    """Stays under Upstox's 50/s, 500/min and 2000/30min limits (with a safety margin)."""

    def __init__(self, limits=((1, 8), (60, 400), (1800, 1800)), now=time.monotonic, sleep=time.sleep):
        self.limits = [(w, n, deque()) for w, n in limits]
        self.now, self.sleep = now, sleep

    def wait(self):
        while True:
            t, delay = self.now(), 0.0
            for w, n, q in self.limits:
                while q and t - q[0] >= w:
                    q.popleft()
                if len(q) >= n:
                    delay = max(delay, w - (t - q[0]))
            if delay <= 0:
                break
            self.sleep(delay)
        t = self.now()
        for _, _, q in self.limits:
            q.append(t)


class Api:
    def __init__(self, token, limiter=None):
        self.s = requests.Session()
        self.s.headers.update({"Accept": "application/json", "Authorization": f"Bearer {token}"})
        self.rl = limiter or RateLimiter()
        self.calls = 0

    def get(self, path, params=None, base=API_BASE, retries=4):
        last = None
        for attempt in range(retries + 1):
            self.rl.wait()
            self.calls += 1
            try:
                r = self.s.get(base + path, params=params, timeout=30)
            except requests.RequestException as e:
                last = ApiError(0, str(e))
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 401:
                raise TokenExpired()
            if r.status_code == 200:
                body = r.json()
                if body.get("status") == "success":
                    return body.get("data")
            if r.status_code == 429 or r.status_code >= 500:
                last = ApiError(r.status_code, r.text[:200])
                time.sleep(2 ** attempt * 2)
                continue
            raise ApiError(r.status_code, r.text[:300])
        raise last


# ---------- helpers ----------

def folder_for(kind, interval):
    """1-minute data keeps the plain folder names (data/options); other intervals get their own."""
    return kind if interval == "1minute" else f"{kind}_{interval}"


def has_candles(path):
    try:
        with path.open() as fh:
            return sum(1 for _ in zip(range(2), fh)) > 1
    except OSError:
        return False


def safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s))


def select_options(contracts, spot, band_pct):
    """Keep strikes within +/- band_pct % of spot (all of them if spot is unknown)."""
    if spot is None:
        return list(contracts)
    lo, hi = spot * (1 - band_pct / 100), spot * (1 + band_pct / 100)
    out = []
    for c in contracts:
        k = c.get("strike_price")
        if k is None or lo <= float(k) <= hi:
            out.append(c)
    return out


def monthly_expiries(expiries):
    """Last expiry date of each calendar month (used for futures)."""
    last = {}
    for d in sorted(expiries):
        last[(d.year, d.month)] = d
    return sorted(last.values())


def spot_on(spots, d):
    """Close of the latest trading day on or before d."""
    for i in range(10):
        v = spots.get(d - timedelta(days=i))
        if v is not None:
            return v
    return None


def parse_dates(data):
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])
    out = []
    for x in data or []:
        try:
            out.append(date.fromisoformat(str(x)[:10]))
        except ValueError:
            pass
    return sorted(set(out))


def tidy(rows):
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r[0]):
        if r[0] not in seen:
            seen.add(r[0])
            out.append(r[:7] + [0] * (7 - len(r)))
    return out


# ---------- data fetchers ----------

def load_spots(api, start, end):
    """Nifty 50 daily closes, cached in data/nifty_daily.csv."""
    f = DATA_DIR / "nifty_daily.csv"
    spots = {}
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        with f.open() as fh:
            for row in csv.DictReader(fh):
                spots[date.fromisoformat(row["date"])] = float(row["close"])
        return spots
    cur_end = end
    while cur_end >= start:
        cur_start = max(start, cur_end - timedelta(days=364))
        path = f"/historical-candle/{quote(UNDERLYING, safe='')}/days/1/{cur_end}/{cur_start}"
        data = api.get(path, base=V3_BASE)
        for c in (data or {}).get("candles", []):
            spots[date.fromisoformat(c[0][:10])] = float(c[4])
        cur_end = cur_start - timedelta(days=1)
    DATA_DIR.mkdir(exist_ok=True)
    with f.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "close"])
        for d in sorted(spots):
            w.writerow([d.isoformat(), spots[d]])
    return spots


def list_contracts(api, kind, expiry):
    """Expired contracts for one expiry, cached in data/contracts/."""
    f = DATA_DIR / "contracts" / f"{kind}_{expiry}.json"
    if f.exists():
        return json.loads(f.read_text())
    ep = "option" if kind == "options" else "future"
    try:
        data = api.get(f"/expired-instruments/{ep}/contract",
                       params={"instrument_key": UNDERLYING, "expiry_date": expiry.isoformat()})
    except ApiError as e:
        if e.status in (400, 404):
            data = []
        else:
            raise
    data = data or []
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data))
    return data


def fetch_candles(api, key, interval, start, end, chunk_days, problems):
    """Candles for [start, end], split into chunk_days windows (newest window first)."""
    rows, cur_end = [], end
    while cur_end >= start:
        cur_start = max(start, cur_end - timedelta(days=chunk_days - 1))
        path = f"/expired-instruments/historical-candle/{quote(key, safe='')}/{interval}/{cur_end}/{cur_start}"
        try:
            data = api.get(path)
            rows.extend((data or {}).get("candles", []))
        except ApiError as e:
            span = (cur_end - cur_start).days
            if e.status == 400 and span > 2:  # window too big? retry in smaller pieces
                rows.extend(fetch_candles(api, key, interval, cur_start, cur_end, max(1, chunk_days // 2), problems))
            else:
                problems.append(f"{key} {cur_start}..{cur_end}: {e}")
        cur_end = cur_start - timedelta(days=1)
    return tidy(rows)


# ---------- main flow ----------

def window_for(expiry, kind, start, today, lookback_opt, lookback_fut):
    lb = lookback_opt if kind == "options" else lookback_fut
    return max(start, expiry - timedelta(days=lb)), min(expiry, today)


def run(api, args, today):
    start = today - timedelta(days=int(365.25 * args.years))
    DATA_DIR.mkdir(exist_ok=True)
    problems = []

    expiries = [d for d in parse_dates(api.get("/expired-instruments/expiries", {"instrument_key": UNDERLYING}))
                if start <= d <= today]
    print(f"{len(expiries)} Nifty expiries between {start} and {today}")
    if args.limit_expiries:
        expiries = expiries[-args.limit_expiries:]

    spots = load_spots(api, start - timedelta(days=10), today) if "options" in args.kinds else {}
    plan = []  # (kind, expiry, contract)
    for kind in args.kinds:
        exps = expiries  # futures too: the "last expiry of month" guess missed Apr 2025
        for e in exps:
            cs = list_contracts(api, kind, e)
            if kind == "options":
                cs = select_options(cs, spot_on(spots, e), args.band)
            plan += [(kind, e, c) for c in cs]
    if plan:
        print("Sample contract from the API (check field names look right):")
        print(json.dumps(plan[0][2], indent=1)[:600])

    # files saved by download_live.py before the contract expired: download them again in full now
    partial = load_partial() if args.interval == "1minute" else {}
    todo, requests_needed = [], 0
    for kind, e, c in plan:
        key = c.get("expired_instrument_key") or c.get("instrument_key")
        if not key:
            continue
        out = DATA_DIR / folder_for(kind, args.interval) / f"{safe(key)}.csv"
        if out.exists() and not (args.retry_empty and not has_candles(out)) and out.name not in partial:
            continue
        s, en = window_for(e, kind, start, today, args.lookback_options, args.lookback_futures)
        step = 1 if args.interval == "day" else args.chunk_days
        n = max(1, math.ceil(((en - s).days + 1) / (366 if args.interval == "day" else step)))
        requests_needed += n
        todo.append((kind, e, c, key, out, s, en))
    hours = requests_needed / 3600  # ~2000 requests per 30 min is the binding limit
    print(f"{len(plan)} contracts selected, {len(todo)} still to download, ~{requests_needed} requests "
          f"(~{hours:.1f} h at Upstox's 2000-per-30-min limit)")
    if args.dry_run:
        return 0
    if not todo:
        finish_partial(partial, today)
        return 0

    failed_in_row = 0
    for i, (kind, e, c, key, out, s, en) in enumerate(todo, 1):
        before = len(problems)
        rows = fetch_candles(api, key, args.interval, s, en, 366 if args.interval == "day" else args.chunk_days, problems)
        if len(problems) > before and not rows:
            failed_in_row += 1
            if failed_in_row >= 10:
                print("10 contracts in a row failed - stopping. See data/problems.log", file=sys.stderr)
                break
            continue  # don't mark as done; retry on next run
        failed_in_row = 0
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(HEADER)
            w.writerows(rows)
        if out.name in partial:          # now complete: rebuild its 3/5/15-minute copies, no new manifest row
            del partial[out.name]
            drop_resampled(kind, out.name)
        else:
            with (DATA_DIR / folder_for(kind, args.interval) / "manifest.csv").open("a", newline="") as fh:
                csv.writer(fh).writerow([key, c.get("trading_symbol", ""), e, c.get("strike_price", ""),
                                         c.get("instrument_type", ""), len(rows)])
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] {c.get('trading_symbol', key)} ({len(rows)} candles) - {api.calls} requests")
    finish_partial(partial, today)
    if problems:
        with (DATA_DIR / "problems.log").open("a") as fh:
            fh.write("\n".join(problems) + "\n")
        print(f"{len(problems)} problems logged to data/problems.log")
    return 0


# ---------- part-downloaded contracts (download_live.py) ----------

PARTIAL = DATA_DIR / "partial_files.csv"


def load_partial():
    if not PARTIAL.exists():
        return {}
    with PARTIAL.open(newline="") as fh:
        return {r["file"]: r for r in csv.DictReader(fh)}


def drop_resampled(kind, name):
    for iv in ("3minute", "5minute", "15minute"):
        f = DATA_DIR / f"{kind}_{iv}" / name
        if f.exists():
            f.unlink()


def finish_partial(partial, today):
    """Save the list again. A partial file whose expiry is past but that the expired-contract list does not
    contain (its name differs) is deleted, so the same contract is never counted twice."""
    if not PARTIAL.exists():
        return
    for name, r in list(partial.items()):
        cache = DATA_DIR / "contracts" / f"{r['kind']}_{r['expiry']}.json"
        if date.fromisoformat(r["expiry"]) >= today or not cache.exists():
            continue
        names = {f"{safe(c.get('expired_instrument_key') or c.get('instrument_key'))}.csv" for c in json.loads(cache.read_text())}
        if names and name not in names:
            (DATA_DIR / r["kind"] / name).unlink(missing_ok=True)
            drop_resampled(r["kind"], name)
            del partial[name]
            print(f"removed part-downloaded {name}: the expired list names this contract differently")
    with PARTIAL.open("w", newline="") as fh:
        w = csv.DictWriter(fh, ["kind", "file", "expiry", "updated"])
        w.writeheader()
        w.writerows(sorted(partial.values(), key=lambda r: (r["expiry"], r["file"])))
    if partial:
        print(f"{len(partial)} part-downloaded files still waiting for their contract to expire")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--kind", choices=["options", "futures", "both"], default="both")
    p.add_argument("--years", type=float, default=3)
    p.add_argument("--interval", choices=INTERVALS, default="1minute")
    p.add_argument("--band", type=float, default=4.0, help="options: keep strikes within +/- this %% of Nifty (default 4)")
    p.add_argument("--chunk-days", type=int, default=28, help="days per candle request for minute intervals")
    p.add_argument("--lookback-options", type=int, default=27, help="days of history per option contract")
    p.add_argument("--lookback-futures", type=int, default=95, help="days of history per futures contract")
    p.add_argument("--limit-expiries", type=int, default=0, help="only the latest N expiries (for testing)")
    p.add_argument("--retry-empty", action="store_true", help="download again the contracts that came back empty")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    a.kinds = ["options", "futures"] if a.kind == "both" else [a.kind]
    return a


def main():
    args = parse_args()
    token = ux.load_token()
    if not token:
        print("No valid token. Start the app (run.bat), click 'Login with Upstox', then run this again.")
        return 1
    today = datetime.now(ux.IST).date()
    try:
        return run(Api(token), args, today)
    except TokenExpired:
        print("Upstox rejected the token (they expire 3:30 AM IST). Log in again, then re-run to resume.")
        return 1
    except KeyboardInterrupt:
        print("\nStopped. Re-run to resume where you left off.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
