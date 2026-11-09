import secrets

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

import upstox_client as ux
from backtest_web import bp as backtest_bp
from config import load_keys
from rally_live_web import bp as rally_live_bp

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # sessions reset on restart; fine for local use
app.register_blueprint(backtest_bp)
app.register_blueprint(rally_live_bp)   # /live: Rally paper trading (read only, no orders)


def keys_or_none():
    try:
        return load_keys(), None
    except FileNotFoundError as e:
        return None, str(e)


def current_client():
    token = ux.load_token()
    return ux.Upstox(token) if token else None


@app.route("/")
def index():
    # Upstox sends you back here (or to /callback) with ?code=... after login,
    # depending on the redirect URI registered in your Upstox app.
    if request.args.get("code") or request.args.get("error"):
        return callback()
    keys, key_error = keys_or_none()
    if current_client():
        return redirect(url_for("dashboard"))
    return render_template(
        "index.html",
        key_error=key_error,
        has_key=bool(keys and keys.get("API_KEY")),
        has_secret=bool(keys and keys.get("API_SECRET")),
        redirect_uri=keys["REDIRECT_URI"] if keys else "",
        error=request.args.get("error"),
    )


@app.route("/login")
def login():
    keys, err = keys_or_none()
    if err or not keys.get("API_KEY"):
        return redirect(url_for("index", error=err or "API_KEY missing in keys.txt"))
    # If a ready-made access token is in keys.txt, use it directly.
    if keys.get("ACCESS_TOKEN"):
        ux.save_token(keys["ACCESS_TOKEN"])
        return redirect(url_for("dashboard"))
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    return redirect(ux.login_url(keys["API_KEY"], keys["REDIRECT_URI"], state))


@app.route("/callback")
def callback():
    if request.args.get("error"):
        return redirect(url_for("index", error=request.args["error"]))
    if request.args.get("state") != session.pop("oauth_state", None):
        return redirect(url_for("index", error="Login state mismatch. Please try again."))
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index", error="No authorization code received."))
    keys = load_keys()
    try:
        token = ux.exchange_code(code, keys["API_KEY"], keys["API_SECRET"], keys["REDIRECT_URI"])
    except ux.UpstoxError as e:
        return redirect(url_for("index", error=str(e)))
    ux.save_token(token)
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    ux.clear_token()
    return redirect(url_for("index"))


def fetch(section, fn):
    """Run one API call and return (data, error) so one failure doesn't break the page."""
    try:
        return fn(), None
    except ux.UpstoxError as e:
        if getattr(e, "status", None) == 401:
            ux.clear_token()
        return None, str(e)


@app.route("/dashboard")
def dashboard():
    client = current_client()
    if not client:
        return redirect(url_for("index"))
    sections = {
        "profile": fetch("profile", client.profile),
        "funds": fetch("funds", client.funds),
        "positions": fetch("positions", client.positions),
        "holdings": fetch("holdings", client.holdings),
    }
    if not ux.load_token():  # token was rejected
        return redirect(url_for("index", error="Session expired. Please log in again."))
    return render_template("dashboard.html", s=sections)


@app.route("/api/<section>")
def api(section):
    client = current_client()
    if not client:
        return jsonify(error="not logged in"), 401
    fns = {"profile": client.profile, "funds": client.funds, "positions": client.positions,
           "holdings": client.holdings, "orders": client.orders}
    if section not in fns:
        return jsonify(error="unknown section"), 404
    data, err = fetch(section, fns[section])
    return (jsonify(error=err), 502) if err else jsonify(data)


if __name__ == "__main__":
    # 127.0.0.1 only: this app handles your broker session, so don't expose it to the network.
    app.run(host="127.0.0.1", port=5000, debug=True)
