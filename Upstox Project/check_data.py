"""Quick health check of the downloaded data. Reads only the ends of each file, so it is fast.

    python check_data.py

Prints a summary and writes data/data_check.csv (one line per contract).
"""
import csv
import sys
from collections import defaultdict
from statistics import median

from config import BASE_DIR

DATA_DIR = BASE_DIR / "data"
SMALL = 200  # fewer 1-minute candles than this = suspiciously thin


def file_info(path):
    """(candle_count, first_timestamp, last_timestamp) without loading the whole file."""
    raw = path.read_bytes()
    lines = [ln for ln in raw.decode("utf-8", "ignore").splitlines() if ln.strip()]
    if len(lines) <= 1:
        return 0, "", ""
    return len(lines) - 1, lines[1].split(",")[0], lines[-1].split(",")[0]


def load_manifest(folder):
    info = {}
    m = folder / "manifest.csv"
    if m.exists():
        with m.open(newline="") as fh:
            for row in csv.reader(fh):
                if len(row) >= 6:
                    key = row[0].replace("|", "_")
                    info[key] = {"symbol": row[1], "expiry": row[2], "strike": row[3], "type": row[4]}
    return info


def check(kind):
    folder = DATA_DIR / kind
    if not folder.exists():
        print(f"\n{kind}: folder not found")
        return []
    man = load_manifest(folder)
    rows = []
    for f in sorted(folder.glob("*.csv")):
        if f.name == "manifest.csv":
            continue
        n, first, last = file_info(f)
        m = man.get(f.stem, {})
        rows.append({"kind": kind, "file": f.name, "symbol": m.get("symbol", ""), "expiry": m.get("expiry", ""),
                     "strike": m.get("strike", ""), "type": m.get("type", ""), "candles": n,
                     "first": first, "last": last})
    empty = [r for r in rows if r["candles"] == 0]
    thin = [r for r in rows if 0 < r["candles"] < SMALL]
    print(f"\n=== {kind} ===")
    print(f"contract files: {len(rows)}")
    print(f"empty (no candles at all): {len(empty)}  ({100 * len(empty) / max(1, len(rows)):.1f}%)")
    print(f"thin (< {SMALL} candles):   {len(thin)}  ({100 * len(thin) / max(1, len(rows)):.1f}%)")
    if rows:
        firsts = sorted(r["first"] for r in rows if r["first"])
        lasts = sorted(r["last"] for r in rows if r["last"])
        if firsts:
            print(f"data runs from {firsts[0][:10]} to {lasts[-1][:10]}")
    by_exp = defaultdict(lambda: [0, 0])  # expiry -> [files, files with data]
    for r in rows:
        if r["expiry"]:
            by_exp[r["expiry"]][0] += 1
            by_exp[r["expiry"]][1] += 1 if r["candles"] else 0
    if kind == "options" and by_exp:
        typical = median(v[1] for v in by_exp.values())
        weak = sorted(e for e, v in by_exp.items() if v[1] < 0.5 * typical)
        print(f"expiries covered: {len(by_exp)}  (typical contracts with data per expiry: {typical:.0f})")
        if weak:
            print(f"expiries with less than half the usual contracts ({len(weak)}): " + ", ".join(weak[:15])
                  + (" ..." if len(weak) > 15 else ""))
        else:
            print("no expiry looks badly short of data")
    return rows


def main():
    all_rows = []
    for kind in ("options", "futures"):
        all_rows += check(kind)
    log = DATA_DIR / "problems.log"
    n = len([x for x in log.read_text().splitlines() if x.strip()]) if log.exists() else 0
    print(f"\nproblems logged during download: {n}" + ("  (see data/problems.log)" if n else ""))
    if all_rows:
        out = DATA_DIR / "data_check.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"details saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
