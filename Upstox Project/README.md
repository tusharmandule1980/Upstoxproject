# Upstox Project

Flask app that logs in to your Upstox account and shows profile, funds, positions and holdings.

## Setup (Windows)
1. Install Python 3.11+ (tick "Add Python to PATH").
2. Put your `keys.txt` in this folder (see format below).
3. Double-click `setup.bat` (creates `.venv`, installs packages, runs tests).
4. Double-click `run.bat`, then click **Login with Upstox**.

Mac/Linux: `./setup.sh`, then `source .venv/bin/activate && python app.py`.

## keys.txt
    API_KEY=your_api_key
    API_SECRET=your_api_secret
    REDIRECT_URI=http://127.0.0.1:5000/callback

The redirect URI must be added exactly like this in your app at account.upstox.com/developer/apps.
Never share keys.txt (it is in .gitignore).

Where keys.txt is read from (first found): the `UPSTOX_KEYS_FILE` environment variable, this folder,
then `C:\Users\tusha\Downloads\Upstox_Project\keys.txt`. Moving it into this folder is safest.

## Layout
- `app.py` routes · `upstox_client.py` API wrapper · `config.py` keys.txt parser
- `templates/`, `static/` UI · `tests/` pytest · `token.json` daily token (auto-created, expires 3:30 AM IST)

Upstox tokens must be refreshed by logging in once each day.

## Download Nifty futures/options history (needs Upstox Plus)
1. Run `run.bat` and log in (token lasts until 3:30 AM IST).
2. Double-click `download.bat` or run `download.bat --dry-run` first to see how many contracts/requests it needs.
3. Test small: `download.bat --limit-expiries 1`. Then the full run: `download.bat`.

Options: `--interval 1minute|3minute|5minute|15minute|30minute|day`, `--band 4` (strikes within +/-4% of Nifty),
`--years 3`, `--kind options|futures|both`.
Files land in `data/options/` and `data/futures/` (one CSV per contract, plus `manifest.csv`).
It is resumable: if the token expires or you stop it, log in again and re-run.
Upstox allows ~2000 requests per 30 minutes, so a full 3-year 1-minute download takes many hours.

## Other candle sizes (3, 5, 15 minute)
Download 1-minute data once (`download.bat`), then double-click `resample.bat`.
It builds `data/options_3minute`, `_5minute`, `_15minute` (and the same for futures) from the 1-minute files in minutes.

## Check the downloaded data
Double-click `check_data.bat`. It reports empty or thin contracts and expiries with missing data, and saves `data/data_check.csv`.

## Backtest (Nifty 5-min signals, buying ATM options)
Double-click `backtest.bat` (takes several minutes). It opens `data\backtest\report.html`; every trade is in `data\backtest\trades.csv`.
Results are GROSS: taxes, brokerage and slippage are not included.

Choices made where the rules left room (change them with options such as `backtest.bat --lots 2`):
- Signals use the nearest-expiry Nifty future; indicators: EMA 20, ADX/+DI/-DI 14, RSI 14, MACD line (12,26,9).
- "Increasing vs previous two candles" means higher than the last candle, which was higher than the one before (`--rising-mode both` = just higher than both).
- Put entry uses +DI exactly as written (falling). `--put-di minus` uses -DI instead.
- Put entry keeps ADX rising, as written. `--put-adx off` drops it (tried on 4 Nov 2026, it lowered profit).
- Entry gap (4 Nov 2026): the signal candle must close at least 20 points beyond the 20 EMA, above it for a call and
  below it for a put (`--entry-gap 0` = just beyond, as before).
- The EMA exit below needs 2 closes in a row beyond the 20 EMA (`--ema-exit-closes 1` = the first close, as before).
- Exits (rules of 4 Nov 2026, shown as "EMA exit"): a call exits when a candle closes below the 20 EMA, a put when a
  candle closes above it. The trade stays open instead while the average close since 09:15 is moving with it: for a
  call, that average rose on each of the last two candles and is below the close; for a put, it fell on each of the
  last two candles and is above the close. `--mean-hold off` exits on the 20 EMA close alone.
- Stop: Rs 3,000 total loss on a call, Rs 2,500 on a put (1 lot by default), checked on every 1-minute candle
  (`--call-max-loss`, `--max-loss`).
- Daily loss limit (4 Nov 2026): once a strategy's closed trades have lost Rs 3,000 in a day, it takes no more trades
  that day, and a trade's stop is cut so it never risks more than what is left of the limit (`--daily-loss-cap 0` turns
  it off; `--daily-cap-mode block` only stops new trades).
- Trailing stop (chosen 4 Nov 2026): once a trade is up Rs 3,000, the stop moves up to keep half of the best profit
  (`--profit-lock-at 3000 --profit-lock-pct 50`; `--profit-lock-at 0` turns it off). It applies to ATM buy only, because it
  lowered profit on the in-the-money strikes (`--profit-lock-variants atm itm2 itm5` puts it on all three).
  The old step trail is `--trail-step 15 --trail-gain 45`.
- The rules used until 4 Nov 2026 are still there: `backtest.bat --exit-rule di --put-ema-gap 80 --call-max-loss 2500 --trail-step 15`
  (+DI exits, the put "EMA gap exit", Rs 2,500 stop, stop raised 15 points for every 45 points of gain).
- Entry at the open of the next 1-minute candle of the ATM option (strike where call and put prices are closest), nearest expiry including expiry day (`--min-dte 1` skips it).
- Last entry on the 14:25 candle close; anything still open is closed at 14:30.

## Backtest dashboard (trade-by-trade audit)
1. Double-click `backtest.bat` (about 10-20 minutes) - it tests 5, 15 and 30-minute candles with three strike choices
   (ATM, ITM 2, deep ITM 5). For a quick run use `backtest.bat --timeframes 5 --variants atm`.
2. Double-click `backtest_dashboard.bat`. The browser opens http://127.0.0.1:5000/backtest.
   Use the filters, click a trade (or press the up/down arrow keys) to see its futures chart with the 20 EMA and the
   average since 09:15, the option premium chart, entry/exit and the indicator readings at the signal.
   "How trades ended" breaks the selected strategy down by exit and by calls/puts, following the filters.
   P&L is gross (no taxes/charges).
