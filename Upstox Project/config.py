"""Reads credentials from keys.txt (same folder as this file).

Supported formats (use whichever you already have):

    API_KEY=xxxxxxxx
    API_SECRET=yyyyyyyy
    REDIRECT_URI=http://127.0.0.1:5000/callback

or, with no labels, just plain lines in this order:

    <api key>
    <api secret>
    <redirect uri>        (optional)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# keys.txt is looked for in these places, first match wins:
#   1. the path in the UPSTOX_KEYS_FILE environment variable (if set)
#   2. next to this file (the project folder)
#   3. C:\Users\tusha\Downloads\Upstox_Project\keys.txt
KEYS_CANDIDATES = [
    *([Path(os.environ["UPSTOX_KEYS_FILE"])] if os.environ.get("UPSTOX_KEYS_FILE") else []),
    BASE_DIR / "keys.txt",
    Path(r"C:\Users\tusha\Downloads\Upstox_Project\keys.txt"),
]


def find_keys_file() -> Path:
    for p in KEYS_CANDIDATES:
        if p.is_file():
            return p
    return KEYS_CANDIDATES[-2 if len(KEYS_CANDIDATES) > 2 else 0]


KEYS_FILE = find_keys_file()
TOKEN_FILE = BASE_DIR / "token.json"

DEFAULT_REDIRECT_URI = "http://127.0.0.1:5000/callback"
API_BASE = "https://api.upstox.com/v2"

_ALIASES = {
    "api_key": "API_KEY", "apikey": "API_KEY", "client_id": "API_KEY", "key": "API_KEY",
    "api_secret": "API_SECRET", "apisecret": "API_SECRET", "secret": "API_SECRET",
    "client_secret": "API_SECRET",
    "redirect_uri": "REDIRECT_URI", "redirect_url": "REDIRECT_URI", "redirect": "REDIRECT_URI",
    "access_token": "ACCESS_TOKEN", "token": "ACCESS_TOKEN",
}


def parse_keys(text: str) -> dict:
    labelled, plain = {}, []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sep = "=" if "=" in line else None
        if sep is None and ":" in line:  # "key: value" only when the label is known
            if line.split(":", 1)[0].strip().lower().replace(" ", "_") in _ALIASES:
                sep = ":"
        if sep:
            name, _, value = line.partition(sep)
            name = name.strip().lower().replace(" ", "_")
            value = value.strip().strip("'\"")
            if name in _ALIASES:
                labelled[_ALIASES[name]] = value
                continue
        plain.append(line.strip("'\""))
    if not labelled and plain:
        for name, value in zip(("API_KEY", "API_SECRET", "REDIRECT_URI"), plain):
            labelled[name] = value
    labelled.setdefault("REDIRECT_URI", DEFAULT_REDIRECT_URI)
    return labelled


def load_keys() -> dict:
    path = find_keys_file()
    if not path.is_file():
        tried = "; ".join(str(p) for p in KEYS_CANDIDATES)
        raise FileNotFoundError(f"keys.txt not found. Looked in: {tried}")
    return parse_keys(path.read_text(encoding="utf-8-sig"))
