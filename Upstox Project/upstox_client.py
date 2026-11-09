"""Thin wrapper over the Upstox v2 REST API (login, profile, funds, positions...)."""
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

from config import API_BASE, TOKEN_FILE

IST = ZoneInfo("Asia/Kolkata")


class UpstoxError(Exception):
    pass


def login_url(api_key: str, redirect_uri: str, state: str) -> str:
    qs = urlencode({
        "client_id": api_key,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    })
    return f"{API_BASE}/login/authorization/dialog?{qs}"


def exchange_code(code: str, api_key: str, api_secret: str, redirect_uri: str) -> str:
    r = requests.post(
        f"{API_BASE}/login/authorization/token",
        headers={"Accept": "application/json"},
        data={
            "code": code,
            "client_id": api_key,
            "client_secret": api_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if r.status_code != 200:
        raise UpstoxError(f"Token exchange failed ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def _token_expiry() -> float:
    """Upstox access tokens expire at 3:30 AM IST the next day."""
    now = datetime.now(IST)
    expiry = now.replace(hour=3, minute=30, second=0, microsecond=0)
    if now >= expiry:
        expiry += timedelta(days=1)
    return expiry.timestamp()


def save_token(token: str) -> None:
    TOKEN_FILE.write_text(json.dumps({"access_token": token, "expires_at": _token_expiry()}))


def load_token():
    if not TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_FILE.read_text())
    except ValueError:
        return None
    if data.get("expires_at", 0) <= time.time():
        TOKEN_FILE.unlink(missing_ok=True)
        return None
    return data["access_token"]


def clear_token() -> None:
    TOKEN_FILE.unlink(missing_ok=True)


class Upstox:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({"Accept": "application/json", "Authorization": f"Bearer {token}"})

    def _get(self, path: str, **params):
        r = self.s.get(f"{API_BASE}{path}", params=params or None, timeout=15)
        try:
            body = r.json()
        except ValueError:
            raise UpstoxError(f"{path}: non-JSON response ({r.status_code})")
        if r.status_code != 200 or body.get("status") != "success":
            errs = body.get("errors") or [{"message": r.text}]
            msg = "; ".join(e.get("message", str(e)) for e in errs)
            err = UpstoxError(f"{path}: {msg}")
            err.status = r.status_code
            raise err
        return body["data"]

    def profile(self):
        return self._get("/user/profile")

    def funds(self, segment: str | None = None):
        return self._get("/user/get-funds-and-margin", **({"segment": segment} if segment else {}))

    def positions(self):
        return self._get("/portfolio/short-term-positions")

    def holdings(self):
        return self._get("/portfolio/long-term-holdings")

    def orders(self):
        return self._get("/order/retrieve-all")
