# Upstox Trading Project – Session Notes

Nov 4, 2026 · @Tushar

## Continue on the laptop

Open this same Claude Project on the laptop, copy the project folder (with its data) across, run setup once, then log in to Upstox again.

**Claude side.** Sign in to claude.ai with the same account, open the **Upstox Trading Project**, and click **New chat** inside it. The project's saved notes come with you; the files on your PC do not. Paste the message from the last section of this doc as your first message.

**Moving the project files**

1. On the PC, close every black window (the app and any downloader).
2. Copy the whole folder `C:\Users\tusha\Downloads\Upstox_Project` to a USB drive or external disk. It holds `keys.txt` and the inner `Upstox Project` folder with the `data` folder (several GB). Leave out the `.venv` folder: it only works on the PC where it was made.
3. On the laptop, paste it into `Downloads`, so you get `...\Downloads\Upstox_Project\Upstox Project`. If the laptop's Windows user name is not `tusha`, move `keys.txt` into the inner `Upstox Project` folder (the app looks there first).
4. Install Python 3 from python.org with **Add python.exe to PATH** ticked, then double-click `setup.bat`.
5. Double-click `run.bat` and click **Login with Upstox**. This is needed once a day (access ends 3:30 AM IST).

The redirect address `http://127.0.0.1:5000/` works on any computer, so nothing changes in Upstox. Upstox accepts orders only from your registered static IP, so the laptop on another network will not be able to place orders; login, profile, funds, data download, backtest and dashboard all work.

If copying the data is not possible, download it again on the laptop: `download.bat` (about 2.5 hours), then `resample.bat`.

## Where things stand

Setup, Upstox login, the data download, the backtest and the dashboard all work; the next step is your review of the strategy rules.

| Area | Status |
| --- | --- |
| Project setup (Python, Flask, tools) | Done. App runs at `http://127.0.0.1:5000` |
| Upstox login (API key and secret in `keys.txt`) | Working. Redirect address `http://127.0.0.1:5000/` |
| Account page (profile, funds, positions, holdings) | Working |
| Data download (Upstox Plus, expired contracts) | Done: 1-minute Nifty options and futures, Sep 2024 to Oct 2026 |
| 3, 5 and 15-minute data | Built with `resample.bat` |
| Backtest | Built and run on real data: 5, 15, 30-minute candles x ATM, ITM 2, Deep ITM 5 buying; rerun on 4 Nov 2026 with the new exit rules (20 EMA close with the 09:15-average hold; stop Rs 3,000 call / Rs 2,500 put; trail keeps half the profit once up Rs 3,000, ATM buy only; exit after 2 closes beyond the EMA; entry only 20+ points beyond the EMA) |
| Backtest dashboard | Working at `http://127.0.0.1:5000/backtest` (start with `backtest_dashboard.bat`) |
| Strategy rule review | Waiting for your answers (see Strategy rules below) |
| Live market page, order placing | Not started |

## Project folder and tools

Everything lives in `C:\Users\tusha\Downloads\Upstox_Project\Upstox Project`; `keys.txt` currently sits one level up, in `C:\Users\tusha\Downloads\Upstox_Project`. You start everything by double-clicking a `.bat` file.

| File | What it does | When |
| --- | --- | --- |
| `setup.bat` | Installs the Python packages into `.venv` and runs the tests | Once per computer |
| `run.bat` | Starts the app at `http://127.0.0.1:5000`: Upstox login, profile, funds, positions, holdings | Daily login |
| `download.bat` | Downloads expired Nifty options and futures, 1-minute candles. Options: `--dry-run`, `--limit-expiries 1`, `--kind futures`, `--kind options --retry-empty` | Needs today's login |
| `resample.bat` | Builds 3, 5 and 15-minute files from the 1-minute data | After a download |
| `check_data.bat` | Counts empty or thin files and writes `data\data_check.csv` | After a download |
| `backtest.bat` | Runs the strategy backtest; saves `data\backtest\all_trades.csv`, `report.html`, `config.json` | After any rule change |
| `backtest_dashboard.bat` | Starts the app and opens `http://127.0.0.1:5000/backtest`; keep its black window open | To review results |
| `keys.txt` | `API_KEY=`, `API_SECRET=`, `REDIRECT_URI=http://127.0.0.1:5000/`; never share it | Set once |
| `token.json` | Today's Upstox login, created automatically | Automatic |
| `data\` | `options\`, `futures\` (1-minute), the `_3minute`, `_5minute`, `_15minute` folders, `contracts\`, `backtest\` | Automatic |

The program files behind these are `app.py`, `upstox_client.py`, `config.py`, `data_download.py`, `resample_data.py`, `check_data.py`, `backtest.py`, `backtest_web.py`, plus the `templates`, `static` and `tests` folders. The latest full set is in `Upstox_Project.zip` from the chat.

## Data downloaded

You have about two years of 1-minute Nifty options and futures data, 6 Sep 2024 to 27 Oct 2026. Upstox's expired-contract data appears to start around October 2024, so a full three years was not available.

| Item | Result |
| --- | --- |
| Option contract files | 8,492 (strikes within +/-4% of Nifty, 109 expiries) |
| Futures contract files | 25 monthly contracts (April 2025 added on a second run) |
| Empty option files | 93: 76 are the whole 26 Dec 2024 expiry, 17 scattered |
| Empty futures files | 1 (the Dec 2024 contract) |
| Thin files (under 200 candles) | 8 |
| Problems logged during download | 0 |

Treat the week before 26 Dec 2024 with caution; the backtest skips signals there and counts them. Some 2026 futures files run to 15:39, and some start with a 6 PM candle on 1 Nov 2024 (probably the Diwali session). The Nifty lot size changed during this period: early trades use 25 quantity, later ones more.

## Strategy rules (your review is pending)

Your rules are below exactly as you gave them, with how each was coded. Rows marked **Yes** under Review are choices I made that you still need to confirm or change.

**Common to both sides**

| Your rule | How it is coded | Review |
| --- | --- | --- |
| Nifty Future 5 min analysis | Nearest-month Nifty future, 5-minute candles | - |
| ATM option for call or put buying | ATM = strike where call and put prices are closest; nearest expiry, including expiry day | Yes |
| Trade time 9:25 to 2:30 only | Entries from the 9:25 candle to the 14:25 candle; any open trade closed at 14:30 | Yes |
| No limit on trades per day | No limit | - |
| One trade at a time; new signal only after the previous trade has closed | As written; a new entry can follow right after an exit, even after a stop loss | Yes |

**CALL entry (all five true on the same candle)**

| Your rule | How it is coded | Review |
| --- | --- | --- |
| Current 5 min candle closes above 20 EMA | Close at least 20 points above the 20 EMA (20-point gap from 4 Nov 2026 night) | - |
| +DI increasing compared to previous two 5 min candles | +DI higher than the last candle, which was higher than the one before | Yes |
| ADX increasing compared to previous two 5 min candles | Same reading as +DI | Yes |
| RSI increasing compared to previous two 5 min candles | Same reading as +DI | Yes |
| Current MACD increasing compared to previous two 5 min candles | Same reading, using the MACD line (not the histogram) | Yes |

**CALL exit (whichever comes first)**

| Your rule | How it is coded | Review |
| --- | --- | --- |
| Exit if the current candle closes below the 20 EMA (4 Nov 2026, replaces the +DI exit) | Two 5-minute closes in a row below the 20 EMA (2 closes from 4 Nov 2026 night); shown as EMA exit | - |
| Do not exit while the mean price from the 9:15 candle keeps increasing and is below the current price | The average of the 5-minute closes since 09:15 (starting again each day) rose on each of the last two candles and is below the close, so the EMA exit waits; the stop still applies | Yes |
| Exit if the loss reaches Rs 3,000 | Total loss on the trade, checked on every 1-minute candle's low | Yes |
| Trailing stop (the 15-per-45 trail was removed on 4 Nov 2026) | Once up Rs 3,000, the stop keeps half of the best profit; shown as trail stop (applied 4 Nov 2026, ATM buy only) | Yes |

**PUT entry (all five true on the same candle)**

| Your rule | How it is coded | Review |
| --- | --- | --- |
| Current 5 min candle closes below 20 EMA | Close at least 20 points below the 20 EMA (20-point gap from 4 Nov 2026 night) | - |
| +DI decreasing compared to previous two 5 min candles | +DI lower than the last candle, which was lower than the one before; +DI used exactly as written | Yes |
| ADX increasing compared to previous two 5 min candles | ADX rising, as written, even for puts. Dropping it was tried on 4 Nov 2026 and lowered profit | - |
| RSI decreasing compared to previous two 5 min candles | Same reading, falling | Yes |
| Current MACD decreasing compared to previous two 5 min candles | Same reading, falling, MACD line | Yes |

**PUT exit (whichever comes first)**

| Your rule | How it is coded | Review |
| --- | --- | --- |
| Exit if the current candle closes above the 20 EMA (4 Nov 2026, replaces the +DI exit and the EMA gap exit) | Two 5-minute closes in a row above the 20 EMA (2 closes from 4 Nov 2026 night); shown as EMA exit | - |
| Do not exit while the mean price from the 9:15 candle keeps decreasing and is above the current price | The average of the 5-minute closes since 09:15 fell on each of the last two candles and is above the close, so the EMA exit waits; the stop still applies | Yes |
| Exit if the loss reaches Rs 2,500 | Total loss on the trade, checked on every 1-minute candle's low | Yes |
| Trailing stop (the 15-per-45 trail was removed on 4 Nov 2026) | Same as the call (applied 4 Nov 2026, ATM buy only) | Yes |

Settings you did not specify: EMA 20, ADX and DI 14 (Wilder), RSI 14, MACD 12/26/9. Entry fills use the next minute's opening price with no slippage. P&L is gross: taxes, brokerage and slippage excluded, as you asked.

**Questions to answer**

1. "Increasing compared to previous two candles": two rises in a row (current), or just higher than both? Test: `backtest.bat --rising-mode both`
2. Puts: keep +DI as written, or use -DI? Test: `--put-di minus`
3. MACD line or histogram? Test: `--macd-use hist`
4. Rs 2,500 stop: total per trade at the real lot size, or a fixed number of points? How many lots do you trade? Answered on 4 Nov 2026: Rs 3,000 for calls and Rs 2,500 for puts, total per trade.
5. Trailing: stop up 15 points per 45 points gained (current), or stop kept 15 points behind the price once up 45? Option price points? Replaced on 4 Nov 2026: no trail for now; see the suggestion under New exit rules.
6. Close everything at 14:30, or let trades run later?
7. Skip expiry day? Test: `--min-dte 1`
8. Re-enter straight after an exit, even after a stop loss?
9. Do EMA 20, ADX/DI 14, RSI 14 and MACD 12/26/9 match your chart?

**Your answers (4 Nov 2026):** 1. two rises in a row, each candle higher than the last; 2. +DI for the put entry; 3. MACD line; 4. Rs 3,000 calls / Rs 2,500 puts; 5. keep half the best profit once up Rs 3,000; 6. close at 14:30; 7. trade on expiry day too; 8. re-entry as already coded (a new signal after an exit is taken); 9. indicator settings match your chart. Only answer 5 changed the backtest; the rest confirmed what was already coded.

## Backtest results so far

On 5-minute candles with 1 lot, before taxes and charges, ATM buy made +Rs 90,680 over about two years; buying further in the money did better. These come from the first run, before your rule review.

| Strategy (5-minute) | Trades | Win rate | Total P&L (gross) | After Rs 150 per trade | Profit factor | Max drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| ATM buy (your rule) | 1,163 | 39.3% | +Rs 90,680 | -Rs 83,770 | 1.16 | -Rs 62,576 |
| ITM 2 buy | 1,170 | 41.5% | +Rs 1,28,595 | -Rs 46,905 | 1.18 | -Rs 64,987 |
| Deep ITM buy (ITM 5) | 1,165 | 42.1% | +Rs 1,81,671 | +Rs 6,921 | 1.23 | -Rs 73,254 |

The 15 and 30-minute results are in the dashboard (click 15m or 30m). For ATM buy the average is about Rs 78 per trade, best trade +Rs 19,733, worst -Rs 2,614.

- **Thin edge.** At an assumed Rs 150 per round trip for charges and slippage, only Deep ITM buy stays in profit on 5-minute candles, and only just. ATM buy breaks even only if costs stay under about Rs 78 per trade. Test: `backtest.bat --timeframes 5 --variants atm --charges-per-trade 150`, then run plain `backtest.bat` to restore all strategies on the dashboard.
- **Large drawdown.** -Rs 62,576 is about two-thirds of the total profit, with long flat and falling stretches.
- **Stop width changed.** Rs 2,500 total is about 100 option points at 25 quantity but far fewer at the later, larger lot sizes.
- **Only two years.** Compare the first and second year with the dashboard's From and To boxes.
- **Profit by exit condition.** The trades still open at 14:30 made the money and the stop losses gave it back; see the table below.

**ATM buy by exit condition (5-minute, 1 lot)**

| How the trade ended | Trades | Win rate | Total P&L (gross) | Average per trade | After Rs 150 per trade |
| --- | --- | --- | --- | --- | --- |
| Square-off at 14:30 | 121 | 63.6% | +Rs 1,12,668 | +Rs 931 | +Rs 94,518 |
| DI exit | 994 | 38.1% | +Rs 86,033 | +Rs 87 | -Rs 63,067 |
| Trail stop | 4 | 25.0% | +Rs 2,150 | +Rs 538 | +Rs 1,550 |
| Stop loss | 44 | 0% | -Rs 1,10,171 | -Rs 2,504 | -Rs 1,16,771 |
| All trades | 1,163 | 39.3% | +Rs 90,680 | +Rs 78 | -Rs 83,770 |

DI exits are 85% of trades but average only Rs 87, below the estimated Rs 100-200 cost of a trade. The 10 best trades add up to Rs 95,022, more than the whole total. 15 and 30-minute candles show the same pattern, with DI exits losing money there too.

**What this means for the open questions**

- **Question 2 (puts).** Puts are 37 of the 44 stop losses and 101 of the 121 square-offs, and are held 41 minutes on average against 15 for calls. With +DI as written, a put exits only after +DI rises on two candles in a row. Using -DI instead cuts stop-loss exits to 13; see Stop-loss review below.
- **Question 4 (stop).** None of the 179 trades at 25 quantity, where Rs 2,500 is a 100-point stop, hit the stop; 44 of the 984 trades at 65 and 75 quantity did.
- **Question 5 (trailing).** The trail stop fired only 4 times: 162 trades were ever up 45 points, and nearly all of them ended on a DI exit or at 14:30 first. Three of the four were small losses, because one or two 15-point steps still leave the stop below the entry price.
- **Question 6 (14:30 close).** 110 of the 121 square-off trades were entered from 13:00 onward, so a later close would mainly change those trades.

## Stop-loss review

Changing the stop does not turn the 44 stop-loss trades into profit. Using -DI for puts, the second reading under question 2, does most of the work: stop-loss exits fall from 44 to 13. All figures are ATM buy on 5-minute candles with 1 lot, gross unless marked, under the put rules from before 4 Nov 2026.

**The stopped trades were losing trades anyway.** Replayed with no stop, 42 of the 44 still lose and 33 lose more than Rs 2,500. Together they would have lost Rs 99,551 instead of Rs 1,10,171. One put on 1 Feb 2026 that recovered to +Rs 13,344 accounts for more than that whole gap; on the other 43 trades the stop saved about Rs 5,200. Most stopped trades were puts (37), entered before 10:00 (20), and stopped within about 17 minutes.

**Stop rules tested.** Each rule went through the full backtest, so later trades shift too. No rule is profitable after Rs 150 per trade, and the gross result moves by at most about Rs 14,000 either way with no clear pattern: 30 points is best, 40 and 60 points match the current rule, and 50 points is worse. That zig-zag means the differences are mostly chance.

| Stop rule | Gross P&L | After Rs 150 per trade | Sep 2024 to Sep 2025 | Oct 2025 to Oct 2026 | Stop-loss exits | Worst trade |
| --- | --- | --- | --- | --- | --- | --- |
| Rs 2,500 per trade, on touch (current) | +Rs 90,680 | -Rs 83,770 | +Rs 5,272 | +Rs 85,408 | 44 | -Rs 2,614 |
| Rs 2,500, checked on the 1-minute close | +Rs 89,412 | -Rs 84,888 | +Rs 8,212 | +Rs 81,200 | 37 | -Rs 3,224 |
| Rs 3,750 per trade | +Rs 93,993 | -Rs 80,007 | +Rs 5,500 | +Rs 88,494 | 8 | -Rs 3,750 |
| Rs 5,000 per trade | +Rs 95,840 | -Rs 78,010 | +Rs 6,005 | +Rs 89,834 | 0 | -Rs 4,267 |
| No hard stop | +Rs 96,167 | -Rs 77,683 | +Rs 6,333 | +Rs 89,834 | 0 | -Rs 4,267 |
| 30 option points | +Rs 1,00,748 | -Rs 73,852 | +Rs 9,435 | +Rs 91,313 | 88 | -Rs 2,265 |
| 40 option points | +Rs 91,043 | -Rs 83,107 | +Rs 7,425 | +Rs 83,618 | 39 | -Rs 3,000 |
| 50 option points | +Rs 80,737 | -Rs 93,413 | +Rs 5,378 | +Rs 75,359 | 18 | -Rs 3,750 |
| 60 option points | +Rs 91,410 | -Rs 82,590 | +Rs 3,366 | +Rs 88,044 | 6 | -Rs 4,500 |
| 25% of entry premium | +Rs 76,676 | -Rs 1,02,724 | -Rs 5,092 | +Rs 81,768 | 226 | -Rs 4,368 |
| 35% of entry premium | +Rs 82,832 | -Rs 93,418 | -Rs 2,564 | +Rs 85,396 | 116 | -Rs 3,900 |
| 50% of entry premium | +Rs 84,684 | -Rs 89,916 | -Rs 1,850 | +Rs 86,534 | 42 | -Rs 4,267 |
| Rs 2,500 plus exit when the future closes back across the 20 EMA | +Rs 88,557 | -Rs 88,143 | +Rs 1,904 | +Rs 86,654 | 34 | -Rs 2,614 |

Rs 7,500 per trade and 80 option points never triggered, so they match No hard stop. Wider stops and no stop move losses from the Stop loss row into the DI exit row rather than removing them: with no hard stop, DI exits total -Rs 13,511 instead of +Rs 86,033. The worst trade without a stop was -Rs 4,267 in this period, but a crash day could make it far larger.

**The -DI reading for puts (question 2).** With +DI as written, puts were held 41 minutes on average against 15 for calls and caused 37 of the 44 stops. With -DI, puts behave like calls: 15 minutes on average and 6 stops. It improves both years and halves the worst drawdown. It is one of the two readings listed before any testing, not a setting tuned on these results, so it is less likely to be luck. Skipping entries before 10:00 made results worse.

| Rule change (stop stays Rs 2,500) | Trades | Win rate | Gross P&L | After Rs 150 per trade | Max drawdown | Sep 2024 to Sep 2025 | Oct 2025 to Oct 2026 | Stop-loss exits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current: +DI for puts, entries from 09:25 | 1,163 | 39.3% | +Rs 90,680 | -Rs 83,770 | -Rs 62,576 | +Rs 5,272 | +Rs 85,408 | 44 |
| -DI for puts | 1,037 | 41.6% | +Rs 1,01,887 | -Rs 53,663 | -Rs 30,742 | +Rs 6,474 | +Rs 95,413 | 13 |
| Entries from 10:00 | 942 | 38.5% | +Rs 71,325 | -Rs 69,975 | -Rs 50,173 | +Rs 17,764 | +Rs 53,561 | 27 |
| -DI for puts, entries from 10:00 | 855 | 40.1% | +Rs 62,281 | -Rs 65,969 | -Rs 28,715 | +Rs 3,869 | +Rs 58,412 | 10 |

**Breakdown by exit condition with -DI for puts**

| How the trade ended | Trades | Win rate | Gross P&L | Average per trade | After Rs 150 per trade | Current rule, gross |
| --- | --- | --- | --- | --- | --- | --- |
| DI exit | 975 | 41.1% | +Rs 99,672 | +Rs 102 | -Rs 46,578 | +Rs 86,033 |
| Square-off at 14:30 | 47 | 61.7% | +Rs 30,847 | +Rs 656 | +Rs 23,797 | +Rs 1,12,668 |
| Trail stop | 2 | 50.0% | +Rs 3,925 | +Rs 1,963 | +Rs 3,625 | +Rs 2,150 |
| Stop loss | 13 | 0% | -Rs 32,558 | -Rs 2,504 | -Rs 34,508 | -Rs 1,10,171 |
| All trades | 1,037 | 41.6% | +Rs 1,01,887 | +Rs 98 | -Rs 53,663 | +Rs 90,680 |

After Rs 150 per trade it still loses Rs 53,663; it breaks even only if costs stay under about Rs 98 per trade. To see it on the dashboard, run `backtest.bat --put-di minus`; plain `backtest.bat` restores the current rules.

**Check on 15 and 30-minute candles.** The -DI reading cuts stop-loss exits on every timeframe, but it adds profit only on 5 and 15-minute candles. On 15-minute candles both years improve. On 30-minute candles both years get worse, because with +DI, 101 puts were held to 14:30 and made Rs 1,54,132 there.

| Candles | Stop-loss exits, +DI | Stop-loss exits, -DI | Gross P&L, +DI | Gross P&L, -DI |
| --- | --- | --- | --- | --- |
| 5-minute (your rule) | 44 | 13 | +Rs 90,680 | +Rs 1,01,887 |
| 15-minute | 56 | 21 | -Rs 7,659 | +Rs 24,252 |
| 30-minute | 43 | 21 | +Rs 23,973 | -Rs 22,110 |

## PUT rule changes (4 Nov 2026)

You kept the EMA gap exit and brought ADX back for puts. That was the default in `backtest.bat` until the new exit rules later that day. On its own, the EMA gap exit raises 5-minute ATM profit from Rs 90,680 to Rs 1,02,209 gross, improves both years and slightly cuts the drawdown. Dropping ADX from the put entry, tried alongside it, added about 610 put trades that lose money as a group.

| Put rules (ATM buy, 5-minute, 1 lot) | Trades | Win rate | Gross P&L | After Rs 150 per trade | Max drawdown | Sep 2024 to Sep 2025 | Oct 2025 to Oct 2026 | Stop-loss exits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Before: ADX in entry, no EMA gap exit | 1,163 | 39.3% | +Rs 90,680 | -Rs 83,770 | -Rs 62,576 | +Rs 5,272 | +Rs 85,408 | 44 |
| EMA gap exit only (now the default) | 1,214 | 39.8% | +Rs 1,02,209 | -Rs 79,891 | -Rs 59,410 | +Rs 11,524 | +Rs 90,685 | 42 |
| No ADX in entry only | 1,773 | 36.8% | +Rs 22,463 | -Rs 2,43,487 | -Rs 75,734 | -Rs 2,068 | +Rs 24,531 | 84 |
| Both rules | 1,829 | 37.1% | +Rs 32,744 | -Rs 2,41,606 | -Rs 74,004 | +Rs 4,035 | +Rs 28,709 | 82 |

Calls are unchanged at 453 trades and +Rs 42,800, so all of the difference is in puts. Puts made +Rs 47,880 before, +Rs 59,410 with the EMA gap exit alone, and lose Rs 10,056 with both rules.

**Breakdown by exit condition with the EMA gap exit (now the default)**

| How the trade ended | Trades | Win rate | Gross P&L | Average per trade | After Rs 150 per trade | Before, gross |
| --- | --- | --- | --- | --- | --- | --- |
| EMA gap exit | 114 | 58.8% | +Rs 1,06,616 | +Rs 935 | +Rs 89,516 | - |
| Square-off at 14:30 | 119 | 63.0% | +Rs 93,684 | +Rs 787 | +Rs 75,834 | +Rs 1,12,668 |
| Trail stop | 2 | 50.0% | +Rs 3,925 | +Rs 1,963 | +Rs 3,625 | +Rs 2,150 |
| DI exit | 937 | 36.3% | +Rs 3,156 | +Rs 3 | -Rs 1,37,394 | +Rs 86,033 |
| Stop loss | 42 | 0% | -Rs 1,05,171 | -Rs 2,504 | -Rs 1,11,471 | -Rs 1,10,171 |
| All trades | 1,214 | 39.8% | +Rs 1,02,209 | +Rs 84 | -Rs 79,891 | +Rs 90,680 |

The new exit takes profit on put trades that used to run on to a DI exit or 14:30, so those rows shrink. The stop-loss row barely changes; in the Stop-loss review, the -DI reading under question 2 was what cut it.

With both rules, the EMA gap exit's 119 trades made Rs 1,70,221, but the extra put entries without ADX mostly ended on a DI exit or the stop. To compare on the dashboard, `backtest.bat --put-adx off` adds the no-ADX entry back, and `backtest.bat --put-ema-gap 0` gives the old rules.

"More than 80" is checked on the current candle. Reading it as "more than 80 when the gap started shrinking" gave a similar result, +Rs 37,572 gross.

**All strategies after the rerun with the EMA gap exit (1 lot)**

On 5-minute candles, the timeframe of your rule, the EMA gap exit raises gross profit for all three strike choices. The 80-point level was set for 5-minute candles; on 15 and 30-minute candles the same exit lowers profit. The dashboard shows these results, and the 5-minute ATM trades match the rule-by-rule test above exactly.

| Candles and strike | Trades now | Gross P&L before | Gross P&L now | After Rs 150 per trade, now | Max drawdown, now |
| --- | --- | --- | --- | --- | --- |
| 5-minute ATM buy | 1,214 | +Rs 90,680 | +Rs 1,02,209 | -Rs 79,891 | -Rs 59,410 |
| 5-minute ITM 2 buy | 1,221 | +Rs 1,28,595 | +Rs 1,35,028 | -Rs 48,122 | -Rs 65,957 |
| 5-minute Deep ITM buy | 1,213 | +Rs 1,81,671 | +Rs 1,95,401 | +Rs 13,451 | -Rs 72,663 |
| 15-minute ATM buy | 509 | -Rs 7,659 | -Rs 11,891 | -Rs 88,241 | -Rs 60,578 |
| 15-minute ITM 2 buy | 510 | +Rs 42,418 | +Rs 38,216 | -Rs 38,284 | -Rs 48,542 |
| 15-minute Deep ITM buy | 507 | +Rs 93,008 | +Rs 91,232 | +Rs 15,182 | -Rs 35,781 |
| 30-minute ATM buy | 300 | +Rs 23,973 | +Rs 11,633 | -Rs 33,366 | -Rs 29,809 |
| 30-minute ITM 2 buy | 302 | +Rs 60,738 | +Rs 42,561 | -Rs 2,739 | -Rs 26,474 |
| 30-minute Deep ITM buy | 304 | +Rs 91,443 | +Rs 59,156 | +Rs 13,556 | -Rs 24,560 |

These were the rules until the new exits later on 4 Nov 2026 (next section). To see them again on the dashboard, run `backtest.bat --exit-rule di --put-ema-gap 80 --call-max-loss 2500 --trail-step 15`.

## New exit rules (4 Nov 2026, afternoon)

Your new exits replaced the +DI exits, the EMA gap exit and the trail on both sides. They are the default in `backtest.bat` from now on and the dashboard shows them; entries did not change. On 5-minute candles, ATM buy, 1 lot, gross profit rises from Rs 1,02,209 to Rs 1,23,602 on 340 fewer trades, so after Rs 150 per trade the loss shrinks from Rs 79,891 to Rs 7,498. Both years are positive before charges and the worst drawdown is smaller.

- **Call:** exits when a 5-minute candle of the future closes below the 20 EMA. It stays open instead while the average close since 09:15 has risen on each of the last two candles and is below the close.
- **Put:** exits when a candle closes above the 20 EMA, unless the average since 09:15 fell on each of the last two candles and is above the close.
- **Always on:** the stop (Rs 3,000 on a call, Rs 2,500 on a put, checked every minute) and the 14:30 square-off. No trailing stop.
- **"Mean price from 9:15"** is the plain average of the 5-minute closes from the 09:15 candle to the current one, starting again each day. A volume-weighted average (VWAP) did worse, Rs 1,10,855 gross, so the plain average stays.

**Breakdown by exit condition (ATM buy, 5-minute, 1 lot)**

| How the trade ended | Trades | Win rate | Gross P&L | Average per trade | After Rs 150 per trade |
| --- | --- | --- | --- | --- | --- |
| Square-off at 14:30 | 335 | 71.6% | +Rs 6,84,529 | +Rs 2,043 | +Rs 6,34,279 |
| EMA exit | 447 | 17.2% | -Rs 3,17,369 | -Rs 710 | -Rs 3,84,419 |
| Stop loss | 92 | 0% | -Rs 2,43,558 | -Rs 2,647 | -Rs 2,57,358 |
| **All trades** | **874** | **36.3%** | **+Rs 1,23,602** | **+Rs 141** | **-Rs 7,498** |

The profit comes from trades still open at 14:30. EMA exits are mostly trades cut after they turned, at -Rs 710 on average. The 09:15-average hold earns its place: it kept 349 trades open at least once, and those trades made +Rs 1,86,158 between them. With the hold switched off, the same rules make Rs 65,189.

**Calls vs puts**

| Side | Stop | Trades | Win rate | Gross P&L | After Rs 150 per trade |
| --- | --- | --- | --- | --- | --- |
| Calls | Rs 3,000 | 334 | 33.5% | +Rs 30,710 | -Rs 19,390 |
| Puts | Rs 2,500 | 540 | 38.0% | +Rs 92,892 | +Rs 11,892 |

**Compared with this morning's rules**

| Rules (ATM buy, 5-minute, 1 lot) | Trades | Win rate | Gross P&L | After Rs 150 per trade | Max drawdown | Sep 2024 to Sep 2025 | Oct 2025 to Oct 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| This morning: +DI exits, EMA gap exit, Rs 2,500 stop, 15-per-45 trail | 1,214 | 39.8% | +Rs 1,02,209 | -Rs 79,891 | -Rs 59,410 | +Rs 11,524 | +Rs 90,685 |
| New exit rules (now the default) | 874 | 36.3% | +Rs 1,23,602 | -Rs 7,498 | -Rs 42,756 | +Rs 57,770 | +Rs 65,833 |
| New exit rules without the 09:15-average hold | 942 | 34.3% | +Rs 65,189 | -Rs 76,111 | -Rs 45,978 | +Rs 11,800 | +Rs 53,390 |

Trades now last 92 minutes on average, against 28 before. Gross profit works out to about Rs 141 per trade, so the result after charges depends on keeping brokerage and slippage below that.

**Trailing stop suggestion (not switched on)**

Once a trade is up Rs 3,000, move the stop up to keep half of the best profit so far: `backtest.bat --profit-lock-at 3000 --profit-lock-pct 50`. 25 trailing rules were tested on the new exits. This one sits in the middle of the group that beats no trail (keep 40-50% once up Rs 2,500-3,500) rather than being the single best. It adds Rs 9,310 gross and cuts the worst drawdown from Rs 42,756 to Rs 31,115. After charges it is about even with no trail, because closing winners earlier frees the position for 71 more trades.

| Trail on the new exits (ATM buy, 5-minute, 1 lot) | Trades | Gross P&L | After Rs 150 per trade | Max drawdown | Sep 2024 to Sep 2025 | Oct 2025 to Oct 2026 |
| --- | --- | --- | --- | --- | --- | --- |
| No trail (your rules, now the default) | 874 | +Rs 1,23,602 | -Rs 7,498 | -Rs 42,756 | +Rs 57,770 | +Rs 65,833 |
| Keep 50% once up Rs 3,000 (suggested) | 945 | +Rs 1,32,912 | -Rs 8,838 | -Rs 31,115 | +Rs 54,049 | +Rs 78,864 |
| Keep 50% once up Rs 2,500 | 979 | +Rs 1,38,565 | -Rs 8,285 | -Rs 30,988 | +Rs 54,124 | +Rs 84,441 |
| Keep 40% once up Rs 3,500 | 914 | +Rs 1,31,592 | -Rs 5,508 | -Rs 38,756 | +Rs 53,929 | +Rs 77,663 |
| Keep 60% once up Rs 3,000 | 985 | +Rs 1,09,908 | -Rs 37,842 | -Rs 33,116 | +Rs 37,389 | +Rs 72,520 |
| Old trail: stop up 15 points per 45 points | 874 | +Rs 1,30,171 | -Rs 929 | -Rs 40,740 | +Rs 57,646 | +Rs 72,525 |
| Stop to the entry price once up Rs 1,500 | 931 | +Rs 91,277 | -Rs 48,373 | -Rs 40,887 | +Rs 43,005 | +Rs 48,272 |
| Stop follows Rs 1,000 below the best once up Rs 1,000 | 1,295 | +Rs 57,618 | -Rs 1,36,632 | -Rs 35,225 | +Rs 26,296 | +Rs 31,322 |

The old 15-per-45 trail does best after charges, but it keeps the stop below the entry price until the option has gained at least 135 points, so it does not lock in a profit. Moving the stop to the entry price, or trailing tightly, cuts short the winners this strategy lives on. The suggestion helps puts and costs calls: calls go from +Rs 30,710 to +Rs 9,247, puts from +Rs 92,892 to +Rs 1,23,666. Every rule tested is in the Trailing options sheet of ATM\_5min\_new\_exit\_rules\_2026-11-04.xlsx.

**All strategies after the rerun with the new exits (1 lot)**

Every strategy improves, and 8 of the 9 now stay in profit after Rs 150 per trade. The exception is 5-minute ATM, your main one, at -Rs 7,498. On 5-minute candles the second year is the stronger one. On 15 and 30-minute candles most of the profit came in the first year (15-minute ATM: Rs 84,614, then Rs 7,685), so those results are less steady. Deep ITM options trade with wider spreads than ATM, so Rs 150 per trade may be too low for them.

| Candles and strike | Trades | Gross P&L, this morning | Gross P&L, new exits | After Rs 150 per trade, new | Max drawdown, new | Sep 2024 to Sep 2025 | Oct 2025 to Oct 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5-minute ATM buy | 874 | +Rs 1,02,209 | +Rs 1,23,602 | -Rs 7,498 | -Rs 42,756 | +Rs 57,770 | +Rs 65,833 |
| 5-minute ITM 2 buy | 886 | +Rs 1,35,028 | +Rs 2,07,675 | +Rs 74,775 | -Rs 52,078 | +Rs 83,774 | +Rs 1,23,901 |
| 5-minute Deep ITM buy | 894 | +Rs 1,95,401 | +Rs 2,85,846 | +Rs 1,51,746 | -Rs 56,595 | +Rs 1,01,823 | +Rs 1,84,023 |
| 15-minute ATM buy | 389 | -Rs 11,891 | +Rs 92,299 | +Rs 33,949 | -Rs 35,326 | +Rs 84,614 | +Rs 7,685 |
| 15-minute ITM 2 buy | 395 | +Rs 38,216 | +Rs 1,44,282 | +Rs 85,032 | -Rs 34,897 | +Rs 1,09,196 | +Rs 35,086 |
| 15-minute Deep ITM buy | 401 | +Rs 91,232 | +Rs 1,74,936 | +Rs 1,14,786 | -Rs 39,105 | +Rs 1,20,598 | +Rs 54,338 |
| 30-minute ATM buy | 246 | +Rs 11,633 | +Rs 44,060 | +Rs 7,160 | -Rs 33,179 | +Rs 41,146 | +Rs 2,915 |
| 30-minute ITM 2 buy | 249 | +Rs 42,561 | +Rs 97,264 | +Rs 59,914 | -Rs 25,775 | +Rs 69,019 | +Rs 28,246 |
| 30-minute Deep ITM buy | 260 | +Rs 59,156 | +Rs 1,02,785 | +Rs 63,785 | -Rs 31,615 | +Rs 71,139 | +Rs 31,645 |

The dashboard now has a How trades ended panel (by exit and by calls/puts, following the filters) and draws the average since 09:15 on the futures chart. Every 5-minute ATM trade, with the reason it ended, is in ATM\_5min\_new\_exit\_rules\_2026-11-04.xlsx in the Upstox\_Project folder.

**Trailing stop applied (4 Nov 2026, evening)**

You chose to apply the trail: once a trade is up Rs 3,000, the stop keeps half of the best profit. It is now the default in `backtest.bat` (`--profit-lock-at 0` turns it off). On 5-minute ATM it does what the test showed: +Rs 1,32,912 gross on 945 trades, -Rs 8,838 after Rs 150 per trade, and the worst drawdown falls from Rs 42,756 to Rs 31,115. It was tuned on 5-minute ATM, though, and it lowers gross profit on 7 of the other 8 strategies. In-the-money options move more per Nifty point, so they reach Rs 3,000 quickly and are stopped out of the big moves. 30-minute ATM is the only other strategy it helps.

| How the trade ended (5-minute ATM, with the trail) | Trades | Win rate | Gross P&L | Average per trade | After Rs 150 per trade |
| --- | --- | --- | --- | --- | --- |
| Trail stop | 195 | 100% | +Rs 4,51,705 | +Rs 2,316 | +Rs 4,22,455 |
| Square-off at 14:30 | 275 | 60.7% | +Rs 3,31,308 | +Rs 1,205 | +Rs 2,90,058 |
| Stop loss | 95 | 0% | -Rs 2,50,714 | -Rs 2,639 | -Rs 2,64,964 |
| EMA exit | 380 | 5.3% | -Rs 3,99,387 | -Rs 1,051 | -Rs 4,56,387 |
| **All trades** | **945** | **40.4%** | **+Rs 1,32,912** | **+Rs 141** | **-Rs 8,838** |

Calls made +Rs 9,247 (355 trades) and puts +Rs 1,23,666 (590 trades).

| Candles and strike | Gross P&L, no trail | Gross P&L, with trail | After Rs 150 per trade, with trail | Max drawdown, with trail |
| --- | --- | --- | --- | --- |
| 5-minute ATM buy | +Rs 1,23,602 | +Rs 1,32,912 | -Rs 8,838 | -Rs 31,115 |
| 5-minute ITM 2 buy | +Rs 2,07,675 | +Rs 1,78,410 | +Rs 29,160 | -Rs 55,895 |
| 5-minute Deep ITM buy | +Rs 2,85,846 | +Rs 1,92,370 | +Rs 38,170 | -Rs 63,571 |
| 15-minute ATM buy | +Rs 92,299 | +Rs 42,197 | -Rs 21,103 | -Rs 40,072 |
| 15-minute ITM 2 buy | +Rs 1,44,282 | +Rs 1,15,022 | +Rs 49,172 | -Rs 29,359 |
| 15-minute Deep ITM buy | +Rs 1,74,936 | +Rs 1,52,308 | +Rs 82,408 | -Rs 28,969 |
| 30-minute ATM buy | +Rs 44,060 | +Rs 60,339 | +Rs 19,689 | -Rs 21,560 |
| 30-minute ITM 2 buy | +Rs 97,264 | +Rs 75,650 | +Rs 33,200 | -Rs 29,991 |
| 30-minute Deep ITM buy | +Rs 1,02,785 | +Rs 63,861 | +Rs 17,211 | -Rs 33,778 |

Every 5-minute ATM trade with the trail is in ATM\_5min\_rules\_with\_trail\_2026-11-04.xlsx in the Upstox\_Project folder.

**Decision (4 Nov 2026, evening): the trail is for ATM buy only.** ITM 2 and Deep ITM buy run without it, so their results are back to the no-trail figures above (5-minute ITM 2 +Rs 2,07,675, Deep ITM +Rs 2,85,846). The setting is `--profit-lock-variants` (default `atm`). ATM keeps the trail on every timeframe, which includes 15-minute ATM, where it lowers gross profit from Rs 92,299 to Rs 42,197. 5-minute ATM, your strategy, is unchanged at +Rs 1,32,912.

**Trade-by-trade web page (5-minute ATM, with the trail):** [ATM 5-min Trade Book](https://claude.ai/artifact/F7M7KeRqMtwGE6ZT6xTFxm). It lists all 945 trades by month and date in the Excel column layout, with the reason each trade ended, filters, a go-to-date box and an adjustable charges figure.

**EMA exit review (4 Nov 2026, not applied)**

The 380 EMA exits (-Rs 3,99,387) are mostly slow losers, not quick whipsaws: median hold 50 minutes, and 202 of them were never more than 10 option points in profit. The EMA exit itself is worth keeping: without it, stop losses rise from 95 to 209 and gross profit falls to Rs 1,09,919. What helps is making it wait for confirmation. All rows are 5-minute ATM with the current stop and trail.

| Change tested | Trades | Gross P&L | After Rs 150 per trade | Max drawdown | Sep 2024 to Sep 2025 | Oct 2025 to Oct 2026 |
| --- | --- | --- | --- | --- | --- | --- |
| Current rules | 945 | +Rs 1,32,912 | -Rs 8,838 | -Rs 31,115 | +Rs 54,049 | +Rs 78,864 |
| Exit after 2 closes in a row beyond the 20 EMA (suggested) | 912 | +Rs 1,66,737 | +Rs 29,937 | -Rs 29,047 | +Rs 86,128 | +Rs 80,609 |
| Exit after 3 closes in a row | 898 | +Rs 1,64,789 | +Rs 30,089 | -Rs 30,031 | +Rs 81,322 | +Rs 83,467 |
| 2 closes + enter only if the close is 20+ pts beyond the EMA | 845 | +Rs 1,80,059 | +Rs 53,309 | -Rs 29,211 | +Rs 91,457 | +Rs 88,602 |
| 1 close more than 10 pts beyond the EMA | 898 | +Rs 1,49,445 | +Rs 14,745 | -Rs 34,933 | +Rs 63,719 | +Rs 85,726 |
| Exit on the 10 EMA instead | 965 | +Rs 1,52,781 | +Rs 8,031 | -Rs 30,376 | +Rs 65,593 | +Rs 87,188 |
| Exit at 30 min if never up Rs 500 | 1,019 | +Rs 1,42,260 | -Rs 10,590 | -Rs 30,348 | +Rs 47,027 | +Rs 95,233 |
| No EMA exit at all | 760 | +Rs 1,09,919 | -Rs 4,081 | -Rs 31,937 | +Rs 64,074 | +Rs 45,846 |

The EMA exit row stays negative under any rule, because it is where losing trades are cut. The gain comes from trades that a single close would have cut and that recovered into square-offs and trail stops. The 2-close rule helps calls and puts and both years; 10, 20 and 30-point entry filters all add to it. These were measured on the same data, so paper trading should confirm them.

**Applied (4 Nov 2026, night): 2 closes for the EMA exit + 20-point entry gap**

Both are now the default in `backtest.bat` (`--ema-exit-closes 1 --entry-gap 0` gives the earlier rules). A call needs the signal candle to close at least 20 points above the 20 EMA, a put at least 20 points below; the EMA exit waits for two closes in a row beyond the EMA. 5-minute ATM matches the study trade for trade.

| How the trade ended (5-minute ATM) | Trades | Win rate | Gross P&L | Average per trade | After Rs 150 per trade |
| --- | --- | --- | --- | --- | --- |
| Trail stop | 192 | 100% | +Rs 4,51,193 | +Rs 2,350 | +Rs 4,22,393 |
| Square-off at 14:30 | 267 | 59.6% | +Rs 3,38,816 | +Rs 1,269 | +Rs 2,98,766 |
| Stop loss | 105 | 0% | -Rs 2,77,219 | -Rs 2,640 | -Rs 2,92,969 |
| EMA exit | 281 | 6.8% | -Rs 3,32,731 | -Rs 1,184 | -Rs 3,74,881 |
| **All trades** | **845** | **43.8%** | **+Rs 1,80,059** | **+Rs 213** | **+Rs 53,309** |

Worst drawdown -Rs 29,211; Sep 2024 to Sep 2025 +Rs 91,457, Oct 2025 to Oct 2026 +Rs 88,602. Calls +Rs 26,229 (335 trades), puts +Rs 1,53,830 (510 trades).

| Candles and strike | Gross P&L before | Gross P&L now | After Rs 150 per trade, now | Max drawdown, now |
| --- | --- | --- | --- | --- |
| 5-minute ATM buy | +Rs 1,32,912 | +Rs 1,80,059 | +Rs 53,309 | -Rs 29,211 |
| 5-minute ITM 2 buy | +Rs 2,07,675 | +Rs 2,34,423 | +Rs 1,15,023 | -Rs 58,150 |
| 5-minute Deep ITM buy | +Rs 2,85,846 | +Rs 3,02,458 | +Rs 1,80,808 | -Rs 50,570 |
| 15-minute ATM buy | +Rs 42,197 | +Rs 38,039 | -Rs 23,761 | -Rs 40,603 |
| 15-minute ITM 2 buy | +Rs 1,44,282 | +Rs 1,29,234 | +Rs 71,184 | -Rs 36,920 |
| 15-minute Deep ITM buy | +Rs 1,74,936 | +Rs 1,58,685 | +Rs 99,735 | -Rs 40,624 |
| 30-minute ATM buy | +Rs 60,339 | +Rs 59,176 | +Rs 18,676 | -Rs 22,673 |
| 30-minute ITM 2 buy | +Rs 97,264 | +Rs 95,195 | +Rs 57,995 | -Rs 26,580 |
| 30-minute Deep ITM buy | +Rs 1,02,785 | +Rs 1,02,854 | +Rs 64,004 | -Rs 31,615 |

The change was tested on 5-minute candles; all three 5-minute strategies improve, while 15 and 30-minute results are about the same or slightly lower. The trade book page and the dashboard show these rules, and every trade is in ATM\_5min\_current\_rules\_2026-11-04.xlsx in the Upstox\_Project folder (sheets: Trades, Exit breakdown, Changes tested).

**ITM and 15-minute check (4 Nov 2026, night)**

Each change tested on its own and together, gross P&L, 1 lot. The study reproduces the full backtest runs exactly.

| Strategy | Previous rules | 2-close exit only | 20-pt entry gap only | Both (current) | Both: Sep 2024 to Sep 2025 / Oct 2025 to Oct 2026 |
| --- | --- | --- | --- | --- | --- |
| 5-minute ITM 2 | +Rs 2,07,675 | +Rs 2,24,565 | +Rs 2,14,994 | +Rs 2,34,423 | +Rs 1,01,049 / +Rs 1,33,374 |
| 5-minute Deep ITM | +Rs 2,85,846 | +Rs 2,90,976 | +Rs 2,97,358 | +Rs 3,02,458 | +Rs 1,25,233 / +Rs 1,77,225 |
| 15-minute ATM | +Rs 42,197 | +Rs 41,913 | +Rs 39,709 | +Rs 38,039 | +Rs 37,761 / +Rs 278 |
| 15-minute ITM 2 | +Rs 1,44,282 | +Rs 1,39,184 | +Rs 1,36,196 | +Rs 1,29,234 | +Rs 95,971 / +Rs 33,263 |
| 15-minute Deep ITM | +Rs 1,74,936 | +Rs 1,70,377 | +Rs 1,65,636 | +Rs 1,58,685 | +Rs 1,07,074 / +Rs 51,611 |

On 5-minute candles both changes help every strike (ITM 2's worst drawdown rises from Rs 52,078 to Rs 58,150; Deep ITM's year 2 is a little lower). On 15-minute candles neither helps: two closes means waiting 30 minutes, and the signals the 20-point gap skips there were winners as a group (+Rs 21,056 for Deep ITM). If 15-minute candles are ever traded, the previous rules suit them better.

**Trade-by-trade web page for 5-minute ITM 2 (current rules, no trail):** [ITM 2 5-min Trade Book](https://claude.ai/artifact/K5sdo9M2b7y7ha2g2r9kpH). Same layout as the ATM page: 796 trades by month and date, calendar, filters and the reason each trade ended.

**Daily loss limit applied (5 Nov 2026): Rs 3,000 per day, per strategy**

Once a strategy's closed trades have lost Rs 3,000 in a day, it takes no more trades that day, and a trade's stop is cut so it never risks more than what is left of the limit (for example Rs 500 after a Rs 2,500 loss). Default in `backtest.bat` (`--daily-loss-cap 0` turns it off; `--daily-cap-mode block` only stops new trades).

| 5-minute strategy | Trades | Gross P&L | After Rs 150 per trade | Max drawdown | Worst day | Days worse than -Rs 3,000 |
| --- | --- | --- | --- | --- | --- | --- |
| ATM, no limit (before) | 845 | +Rs 1,80,059 | +Rs 53,309 | -Rs 29,211 | -Rs 8,058 | 51 |
| ATM, block new trades only | 795 | +Rs 1,76,607 | +Rs 57,357 | -Rs 32,498 | -Rs 5,500 | 48 |
| **ATM, block + tighten (applied)** | 793 | +Rs 1,66,928 | +Rs 47,978 | -Rs 34,514 | -Rs 3,000 | 0 |
| ITM 2, no limit (before) | 796 | +Rs 2,34,423 | +Rs 1,15,023 | -Rs 58,150 | -Rs 9,527 | 77 |
| **ITM 2, block + tighten (applied)** | 716 | +Rs 1,99,301 | +Rs 91,901 | -Rs 62,528 | -Rs 3,000 | 0 |
| Deep ITM, no limit (before) | 811 | +Rs 3,02,458 | +Rs 1,80,808 | -Rs 50,570 | -Rs 9,815 | 88 |
| **Deep ITM, block + tighten (applied)** | 700 | +Rs 2,50,718 | +Rs 1,45,718 | -Rs 61,169 | -Rs 3,144 | 4 |

The limit does its job: no day loses more than Rs 3,000 (Deep ITM has 4 days slightly over, when the option jumped past a tightened stop). It costs profit and does not shrink the worst drawdown, because some days that started badly used to recover. Blocking alone keeps more profit but still allows -Rs 5,500 days. Both trade book pages show the limit, and each day that reached it is marked. Every 5-minute ATM trade under these rules is in ATM\_5min\_current\_rules\_2026-11-05.xlsx in the Upstox\_Project folder (sheets: Trades, Exit breakdown, Daily limit tested).

## Open items and next steps

Rules are settled as of 4 Nov 2026 evening. The trail applies to ATM buy only. Next: paper trading.

- [x] Copy the project folder to the laptop and run `setup.bat` (see Continue on the laptop)
- [x] Answer the nine questions under Strategy rules
- [x] Decided on 4 Nov 2026: ADX stays in the put entry and the EMA gap exit is kept
- [ ] Decided on 4 Nov 2026 (afternoon): new exits for both sides (20 EMA close with the 09:15-average hold, Rs 3,000 call / Rs 2,500 put stop); the +DI exits, the EMA gap exit and the trail are removed
- [x] Decide on the trailing stop suggestion: once up Rs 3,000, keep half of the best profit (`backtest.bat --profit-lock-at 3000`)
- [x] Get the ATM buy profit by exit condition: upload `data\backtest\all_trades.csv` in the new chat
- [x] Run the charges test (`--charges-per-trade 150`) to see profit after costs
- [ ] Decide whether to add a fixed-quantity setting so every trade has the same stop width (offered, not built yet)
- [ ] Rerun `backtest.bat` after the rule changes and review the dashboard
- [ ] Later: live market page (Nifty and option chain with live prices)
- [ ] Later, after paper trading only: order placing, once Upstox's current API and algo rules and the static IP are checked
- [x] Decide on the EMA exit change: exit after 2 closes in a row beyond the 20 EMA, optionally with a 20-point entry filter (see EMA exit review)

## Discussion log (4 Nov 2026)

What was asked and decided in the chat of 4 Nov 2026, in order. The sections named hold the details.

1. **Continued on the laptop.** Read these notes and broke the ATM buy results down by exit condition (Backtest results so far).
2. **Stop-loss review.** The 44 stop-loss trades (-Rs 1,10,171) cannot be turned into profit by changing the stop: they were losing trades anyway, and puts caused 37 of them (Stop-loss review).
3. **Two put rules tried:** no ADX in the put entry, and a put exit when the future is more than 80 points below the 20 EMA and the gap shrinks two candles in a row. Dropping ADX lowered profit and the EMA gap exit raised it, so you kept the EMA gap exit and brought ADX back (PUT rule changes).
4. **Excel files:** the exit breakdown (ATM\_5min\_exit\_breakdown\_2026-11-04.xlsx) and every trade in your column layout (ATM\_5min\_trades\_2026-11-04.xlsx), both in the Upstox\_Project folder.
5. **New exit rules for calls and puts (afternoon).** The +DI exits, the EMA gap exit and the old trail were replaced by an exit on a 5-minute close beyond the 20 EMA, held while the average since 09:15 moves with the trade, plus a stop of Rs 3,000 for calls and Rs 2,500 for puts. 5-minute ATM made +Rs 1,23,602 gross on 874 trades (-Rs 7,498 after Rs 150 per trade, against -Rs 79,891 before), and all 9 strategies improved. The dashboard got a How trades ended panel and the 09:15 average line, and every trade is in ATM\_5min\_new\_exit\_rules\_2026-11-04.xlsx (New exit rules).
6. **Trailing stop suggestion:** once a trade is up Rs 3,000, keep half of the best profit. Tested but not switched on; it is your decision (Open items).
7. **Current rules:** listed below, exactly as applied for these results.
8. **Rule questions answered** (evening): everything as coded, and the trail applied. 5-minute ATM now makes +Rs 1,32,912 gross on 945 trades with a Rs 31,115 worst drawdown, but the trail lowers profit on 7 of the other 8 strategies (Trailing stop applied, under New exit rules). Excel: ATM\_5min\_rules\_with\_trail\_2026-11-04.xlsx.
9. **Trail for ATM only:** you chose to stick to the ATM rule, so the trail now applies to ATM buy only and the in-the-money strategies run without it (Trailing stop applied, under New exit rules).
10. **EMA exit review:** suggested waiting for 2 closes in a row beyond the 20 EMA (+Rs 33,825 gross, positive after charges), optionally with a 20-point entry filter. Not applied yet (EMA exit review, under New exit rules).
11. **Chart for reviewing trades:** signals stay on the Nifty futures chart, as the rule says, and the Nifty 50 index is not downloaded. The index and the future can sit on opposite sides of their 20 EMAs (14 Aug 2025 09:20: future 7.8 points below, index above). Review trades on the current-month NIFTY futures chart; the chart labels a candle by its start, so the signal candle is labelled 5 minutes before the entry time. The trade book page now names the futures contract and signal candle for each day.
12. **Applied 2 closes + 20-point entry gap:** 5-minute ATM now makes +Rs 1,80,059 gross on 845 trades, +Rs 53,309 after Rs 150 per trade, worst drawdown Rs 29,211. Dashboard and trade book page updated (Applied, under New exit rules).
13. **ITM 2 trade book:** the current rules already apply to 5-minute ITM 2 (+Rs 2,34,423 gross on 796 trades); published its own trade book page alongside the ATM one.
14. **Daily loss limit (5 Nov 2026):** Rs 3,000 a day per strategy, applied as a hard limit (no more trades, and the last trade's stop cut to what is left). 5-minute ATM: +Rs 1,66,928 gross on 793 trades, worst day -Rs 3,000. Both trade book pages updated.
15. **Web trade books:** published the ATM and ITM 2 5-minute trade books (every trade by month and date in your Excel columns, a green/red profit and loss calendar to filter by month or date, the futures contract and signal candle for each day). Links are under New exit rules.
16. **Worked examples:** five trades for the 2-close exit and 20-point gap, and five for ITM 2, Deep ITM and 15-minute candles. Correction made on the way: the 20-point gap does not just skip a signal; the next candle that meets all conditions with a 20-point gap is taken (14 Aug 2025 entered at 09:35, 29 Aug 2025 at 13:10).
17. **ITM and 15-minute check:** both changes help all three 5-minute strategies; on 15-minute candles neither helps, so the previous rules would suit 15-minute trading better (ITM and 15-minute check, under New exit rules).
18. **Excel files:** ATM\_5min\_current\_rules\_2026-11-04.xlsx (2 closes + 20-point gap) and ATM\_5min\_current\_rules\_2026-11-05.xlsx (with the daily loss limit, the latest), both in the Upstox\_Project folder. Older files kept.
19. **Trade check, 4 Sep 2026 (ITM 2, NIFTY 23900 CE):** exit at 12:10 confirmed. On the NIFTY 29 SEP 26 FUT 5-minute chart the candles labelled 12:00 (close 24,076.0, EMA 24,092.9) and 12:05 (close 24,088.0, EMA 24,092.4) both closed below the 20 EMA; the 09:15 average was not rising, so no hold. Sold at the 12:10 minute's open, 154.70, for +Rs 175.50 (bought 152.00 at 09:55).

### Rules in use on 5 Nov 2026 (latest)

**Setup:** Nifty futures (nearest expiry), 5-minute candles; EMA 20, +DI and ADX 14, RSI 14, MACD line (12, 26). "Increasing" or "decreasing" = two candles in a row. Buy 1 lot of the ATM option (call and put prices closest), nearest expiry, expiry day included. Entry at the next 1-minute option price after the signal candle closes; signals 09:25 to 14:25; one trade at a time. Review trades on the futures chart: a candle is labelled by its start, 5 minutes before the entry time.

**CALL entry (all on one candle):** close at least 20 points above the 20 EMA; +DI, ADX, RSI and MACD increasing.

**PUT entry (all on one candle):** close at least 20 points below the 20 EMA; +DI decreasing; ADX increasing; RSI and MACD decreasing.

**CALL exit (whichever comes first):** two 5-minute closes in a row below the 20 EMA, unless the average close since 09:15 rose on each of the last two candles and is below the close; loss reaches Rs 3,000; once up Rs 3,000 the stop keeps half of the best profit (ATM only); 14:30 square-off.

**PUT exit (whichever comes first):** two 5-minute closes in a row above the 20 EMA, unless the average close since 09:15 fell on each of the last two candles and is above the close; loss reaches Rs 2,500; the same trail (ATM only); 14:30 square-off.

**Daily loss limit:** once the day's closed trades have lost Rs 3,000, no more trades that day, and a trade's stop is cut so it never risks more than what is left of the limit.

**Result (5-minute ATM, 1 lot, gross):** 793 trades, +Rs 1,66,928; +Rs 47,978 after Rs 150 per trade; worst drawdown Rs 34,514; worst day -Rs 3,000.

### Rules in use on 4 Nov 2026 afternoon (superseded, see the latest above)

**Setup**

- Signals: Nifty futures (nearest expiry), 5-minute candles. Indicators: EMA 20, +DI and ADX 14, RSI 14, MACD line (12, 26).
- "Increasing" or "decreasing" means two candles in a row: higher (or lower) than the last candle, which was higher (or lower) than the one before.
- Buy 1 lot of the ATM option at the nearest expiry, expiry day included. ATM is the strike where the call and put prices are closest.
- Entry at the next 1-minute option price after the signal candle closes. Signals count from 09:25 to 14:25, one trade at a time.

**CALL entry (all five on the same candle):** close above the 20 EMA; +DI increasing; ADX increasing; RSI increasing; MACD increasing.

**PUT entry (all five on the same candle):** close below the 20 EMA; +DI decreasing; ADX increasing; RSI decreasing; MACD decreasing.

**CALL exit (whichever comes first)**

1. A 5-minute candle closes below the 20 EMA, unless the average close since 09:15 has risen on each of the last two candles and is below the close (then the trade stays open).
2. The loss reaches Rs 3,000.
3. 14:30 square-off.

**PUT exit (whichever comes first)**

1. A 5-minute candle closes above the 20 EMA, unless the average close since 09:15 has fallen on each of the last two candles and is above the close.
2. The loss reaches Rs 2,500.
3. 14:30 square-off.

**Not used any more:** the +DI exits, the EMA gap exit for puts and the 15-per-45 trailing stop. Trailing stop, applied later on 4 Nov 2026 for ATM buy only: once a trade is up Rs 3,000, the stop keeps half of the best profit.

**Details that affect the numbers**

- An EMA exit fills at the next 1-minute option price after the candle closes. The stop fills at the stop price, or at the opening price if the option jumps below it.
- The stop is the total loss on the trade, checked on every 1-minute candle. With a 65 lot the Rs 3,000 call stop sits 46.15 points below entry.
- The 09:15 average is the plain average of the 5-minute closes, including the current candle, and starts again each day.
- P&L is gross (no brokerage, taxes or slippage). Data runs from 6 Sep 2024 to 27 Oct 2026, with each expiry's lot size (25, then 75, then 65).
- The dashboard's other strategies use the same rules with 15 or 30-minute candles, or with in-the-money strikes.

### 5 Nov 2026 – Rally project (separate from these rules)

A new folder `C:\Users\tusha\Downloads\Rally` holds fresh Nifty futures studies that ignore the Upstox rules above. Full log and current state: `Rally\Rally_Session_Notes.md`; all numbers: `Rally\Rally_Findings.md`.

- Indicator and opening-range breakout strategies lost or broke even over 2 years of futures data.
- Price-action **Opening Drive** chosen: first 5-min futures candle (body ≥ 20, closes in its outer 40%, same direction as the gap ≥ 15 pts) → buy CALL/PUT at 09:20; ITM 2 on normal days, ITM 3 on expiry day; stop = futures risk (max 120) × delta; trail starts at +28, stays 56 pts below the best price (ITM 2); exit 14:30; 1 lot.
- Backtest (65 qty, net): 134 trades, Rs 1,01,893; Sep 2024–Dec 2025 Rs 54,949, 2026 Rs 46,944; max drawdown Rs −21,164. Expiry days −Rs 10,580 on 20 trades (watch).
- Built `Nifty_Gap_Analysis.xlsx` (09:15 open vs previous close, gap fill, trend vs previous close, 12 statistics tables) and a 1-min vs 5-min first-candle comparison.
- Built `Rally_Paper_Trading_Tracker.xlsx` and an automatic paper trader (reads Upstox prices only, never orders). Both still use older rules; update once the strategy is confirmed.

Later on 5 Nov (Rally):

- **Final strategy confirmed:** Opening Drive with ITM 2, skipping expiry days (next-week ATM made only +Rs 2,118 on 16 trades – not worth the charges) and gaps above 120 pts; exit 14:30. Backtest: 87 trades, net Rs 1,23,875, max drawdown Rs −10,852, 10/10 quarters positive. Review: `Rally\Rally_Final_Strategy_Backtest.xlsx` and [web trade book](https://claude.ai/artifact/5EDgBtXSkCz5wnfjbZoLn8).
- Against-gap days (first candle opposite the gap) lost with any 09:16/09:20 entry. Of 27 rule families, only a PUT-only 30-min range breakdown held up → **strategy 2, Against-Gap Breakdown** (proposed): 43 trades, net Rs 53,951, both periods positive. Review: `Rally\Rally_Strategy2_Against_Gap_Backtest.xlsx` and [web trade book](https://claude.ai/artifact/C99tAuuRSkAux2unyeoLi4).
- You are reviewing both outputs; next step after your findings: decide on strategy 2, then update the paper tracker and paper trader.

Rally review, 5 Nov (log items 26–31 in `Rally\Rally_Session_Notes.md`):

- **Strategy 2 loss limit Rs 3,000** per lot (sell at once; the closer of this and the range stop applies). First strategy unchanged. Strategy 2 now 44 trades, net Rs 55,139 (was 55,968), drawdown Rs −6,380 (was −7,070), worst trade Rs −3,190.
- Trade checks: 16 Jul 2026 missed the +28 trail by 0.15 pts (bad luck, no rule change); 24 Jun 2026 option reached 402 because Nifty futures rallied 288 pts. The web book shows best/stop 1 pt low – user said no action needed.
- **379 of 512 days (74%) had no trade** from either strategy (133 traded: 89 + 44).
- Strategy 2 rules on flat-open (gap < 15) and gap > 120 days lost (PUT −Rs 21,923, CALL −Rs 8,909). These days move a lot (median range 190 and 252 pts) but in no favoured direction → keep them as no-trade days.

Rally, 6 Nov (log items 32–38 in `Rally\Rally_Session_Notes.md`):

- **Decided: no trading on flat-open (gap < 15) and gap > 120 days.** The user's Supertrend/EMA/ADX/Fisher rules also lost there (−Rs 36,785 on 152 trades). Day list: `Rally\Rally_Excluded_Days.xlsx`.
- Expiry-day volatility workbook `Rally\Rally_Expiry_Days_Volatility.xlsx` (109 expiry vs 401 normal days): similar range (202 vs 214 pts) but expiry days lean down (fall from open 105 vs rise 62).
- Opening Drive on expiry days with next-week options: flat or negative for every strike.
- **Strategy 3 (proposed): Expiry-Day Supertrend PUT** – the user's indicator rules, next week's ITM 1 PUT, Rs 3,000 loss limit, exit on Supertrend flip or 14:30: 84 trades, Rs 60,062, both periods positive, but depends on a few big trades. Review: `Rally\Rally_Strategy3_Expiry_Supertrend_Backtest.xlsx` and [web trade book](https://claude.ai/artifact/Jc71W6HwoVc6jDWRJCurJ4).
- The user is reviewing the expiry-day statistics and will come back with findings.

Rally, 7 Nov (log items 41–44 in `Rally\Rally_Session_Notes.md`):

- Strategy 3 with Supertrend 10,2 made less (Rs 51,641 vs 60,062). **Decided: keep Supertrend 10,3.** Review chart fixed (the green Supertrend line no longer bridges bearish stretches).
- **All three Rally strategies together (backtest): 217 trades, 56.2% win, net Rs 2,33,975**, drawdown −11,371, 23 of 26 months positive, never two strategies on the same day. Workbook `Rally\Rally_All_Strategies_Statistics.xlsx`.
- **Paper trading of Rally S1, S2, S3 starts Mon 9 Nov 2026 – paper only, no real orders.** New live engine replays all 217 backtest trades exactly; the paper trader reads live Upstox prices only. Windows task "Rally Paper Trader" starts it at 09:05 Mon–Fri (the user created it). S2 keeps gap > 120 days as backtested (decided).
- Live check with a fresh login passed (contracts, history to 15:39, previous close 25,008, prices, ATM). Mon 9 Nov is a weekly expiry day (Tue 10 Nov likely a holiday) → only S3 can trade.
- **Upstox app: new Live button on /backtest → http://127.0.0.1:5000/live** = the Rally S1/S2/S3 paper-trading page (read only, rules shown). Added `rally_live_web.py` + one line in `app.py` + the button in `templates/backtest.html`; the EMA 20 strategy is unchanged; 33 tests pass. One link only (the 8765 page is just a spare).
- **Each morning:** run `run.bat` → Login before 09:15 and keep it open; watch http://127.0.0.1:5000/live.

## Troubleshooting

Most problems so far came from a closed black window, an expired login, or running a command in the wrong folder.

| What you see | What to do |
| --- | --- |
| `127.0.0.1 refused to connect` | The app is not running. Double-click `backtest_dashboard.bat` (or `run.bat`) and keep its black window open |
| "No valid token" or "token expired" | Run `run.bat`, click Login with Upstox, then run the command again. Login lasts until 3:30 AM IST |
| Login error UDAPI100068 (client\_id or redirect\_uri incorrect) | `REDIRECT_URI` in `keys.txt` must match the Redirect URL in your Upstox app exactly (now `http://127.0.0.1:5000/`); no spaces around the key |
| "download.bat is not recognized" | Open the black window inside the `Upstox Project` folder: click the folder's address bar, type `cmd`, press Enter |
| Downloader stops moving | It is pausing for Upstox's limit (up to about 25 minutes). If the window title starts with "Select", click inside it and press Enter |
| Window closed during a download | Run `download.bat` again; it resumes where it stopped |
| Funds box shows an error at night | Upstox funds data is unavailable roughly midnight to 5:30 AM IST |
| Dashboard says "No results yet" | Run `backtest.bat` once |
| `setup.bat` says Python not found | Reinstall Python with "Add python.exe to PATH" ticked |

## Message to paste into a new chat on the laptop

Copy this into a new chat inside the Upstox Trading Project, filling in your answers where shown.

```
I'm continuing my Upstox Trading Project.
Please read my session notes doc first: https://claude.ai/artifact/SyizuGXMTPezuSBwKiDHE8

Where I left off (5 Nov 2026): the rules are settled and are the backtest default
(enter only on a close 20+ points beyond the 20 EMA; exit after 2 closes in a row beyond it, held while the average since 09:15 moves with the trade;
stop Rs 3,000 call / Rs 2,500 put; once up Rs 3,000 the stop keeps half the best profit, ATM only; daily loss limit Rs 3,000; 14:30 square-off).
See "Discussion log" and "New exit rules" in the doc.
Project folder: ...\Downloads\Upstox_Project\Upstox Project

Paper trading plan: ...
Separate Rally project: read ...\Downloads\Rally\Rally_Session_Notes.md
What I want to do next: ...
```
