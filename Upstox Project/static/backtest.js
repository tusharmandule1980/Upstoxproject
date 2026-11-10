// Rally backtest page: S1 Opening Drive, S2 Against-gap PUT, S3 Expiry Supertrend PUT (data: Rally/live/backtest_web.json)
(() => {
  const $ = (s) => document.querySelector(s);
  const inr = (n) => (n < 0 ? "-" : "") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN");
  const sgn = (n) => (n > 0 ? "+" : "") + inr(n);
  const cls = (n) => (n > 0 ? "pos" : n < 0 ? "neg" : "");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const clock = (m) => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  const tmin = (s) => parseInt(s.slice(0, 2), 10) * 60 + parseInt(s.slice(3, 5), 10);
  const num = (v, d = 2) => (v == null ? "-" : Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sp = (v) => (v > 0 ? "+" : "") + num(v, 1);
  const NAME = { 1: "S1 Opening Drive", 2: "S2 Against-gap PUT", 3: "S3 Expiry Supertrend PUT" };
  const SHORT = { 1: "S1", 2: "S2", 3: "S3" };
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  let data = null, meta = null, dayMap = new Map(), cur = [], sel = null, month = null, selDay = null;
  const filt = { strat: "", outcome: "", reason: "", d1: "", d2: "" };

  function show(msg) { const m = $("#msg"); m.hidden = !msg; m.innerHTML = msg || ""; $("#app").hidden = !!msg; }

  async function boot() {
    const r = await fetch("/api/rally/backtest");
    if (!r.ok) { show("<b>No Rally backtest data yet.</b><br>Run <code>Rally\\export_backtest_web.py</code> (or update_data.bat), then reload this page."); return; }
    data = await r.json(); meta = data.meta; show("");
    dayMap = new Map(data.days.map((d) => [d.date, d]));
    $("#range").textContent = "Data " + meta.data_from + " → " + meta.data_to;
    const reasons = [...new Set(data.trades.map((t) => t.why))].sort();
    $("#fReason").innerHTML = '<option value="">All</option>' + reasons.map((x) => `<option>${esc(x)}</option>`).join("");
    const h = location.hash.slice(1);
    if (/^\d{4}-\d{2}-\d{2}$/.test(h) && dayMap.has(h)) selDay = h;   // /backtest#2026-03-02 opens that day
    render();
  }

  function passes(t, anyStrat) {
    if (!anyStrat && filt.strat && String(t.strategy) !== filt.strat) return false;
    if (filt.outcome === "win" && !(t.net > 0)) return false;
    if (filt.outcome === "loss" && !(t.net < 0)) return false;
    if (filt.reason && t.why !== filt.reason) return false;
    if (filt.d1 && t.date < filt.d1) return false;
    if (filt.d2 && t.date > filt.d2) return false;
    return true;
  }

  function stats(list) {
    const s = { n: list.length, w: 0, l: 0, total: 0, gw: 0, gl: 0, dd: 0, best: 0, worst: 0, curve: [0] };
    let eq = 0, peak = 0;
    for (const t of list) {
      eq += t.net; peak = Math.max(peak, eq); s.dd = Math.min(s.dd, eq - peak); s.curve.push(eq);
      if (t.net > 0) { s.w++; s.gw += t.net; } else { s.l++; s.gl -= t.net; }
      s.best = Math.max(s.best, t.net); s.worst = Math.min(s.worst, t.net);
    }
    s.total = eq; s.winRate = s.n ? (s.w / s.n) * 100 : 0; s.exp = s.n ? eq / s.n : 0;
    s.pf = s.gl ? s.gw / s.gl : s.gw ? Infinity : 0;
    return s;
  }
  const pfText = (v) => (v === Infinity ? "∞" : v.toFixed(2));

  function spark(curve, good) {
    const n = curve.length, lo = Math.min(0, ...curve), hi = Math.max(0, ...curve), r = hi - lo || 1;
    const X = (i) => 2 + (i * 296) / Math.max(1, n - 1), Y = (v) => 52 - ((v - lo) / r) * 48;
    return `<svg viewBox="0 0 300 56" preserveAspectRatio="none"><line x1="0" x2="300" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)" stroke-dasharray="3"/><polyline fill="none" stroke="var(--${good ? "pos" : "neg"})" stroke-width="1.6" points="${curve.map((v, i) => X(i).toFixed(1) + "," + Y(v).toFixed(1)).join(" ")}"/></svg>`;
  }

  function table(groups, total, head) {
    const row = (name, s, tot) => `<tr${tot ? ' class="tot"' : ""}><td>${esc(name)}</td><td>${s.n}</td><td>${s.winRate.toFixed(1)}%</td>
      <td class="${cls(s.total)}">${sgn(s.total)}</td><td class="${cls(s.exp)}">${sgn(s.exp)}</td></tr>`;
    return `<table class="tbl"><tr><th>${head}</th><th>Trades</th><th>Win rate</th><th>Net P&amp;L</th><th>Avg / trade</th></tr>
      ${groups.map(([k, s]) => row(k, s)).join("")}${row("All trades", total, true)}</table>`;
  }
  function groupBy(list, key) {
    const m = new Map();
    for (const t of list) { const k = key(t); if (!m.has(k)) m.set(k, []); m.get(k).push(t); }
    return [...m.entries()].map(([k, v]) => [k, stats(v)]);
  }

  // ---------------------------------------------------------------- top: KPIs, strategy cards, breakdown
  function render() {
    cur = data.trades.filter((t) => passes(t, false));
    const s = stats(cur);
    $("#kpis").innerHTML = [
      ["Total trades", s.n, `${s.w} wins · ${s.l} losses`],
      ["Win rate", s.winRate.toFixed(1) + "%", `Average ${inr(s.exp)} / trade`],
      ["Net P&L", `<span class="${cls(s.total)}">${sgn(s.total)}</span>`, "After slippage + Rs 60 charges"],
      ["Max drawdown", `<span class="${s.dd < 0 ? "neg" : ""}">${inr(s.dd)}</span>`, `Best ${inr(s.best)} · Worst ${inr(s.worst)}`],
      ["Profit factor", pfText(s.pf), filt.strat ? NAME[filt.strat] : "S1 + S2 + S3"],
    ].map(([a, b, c]) => `<div class="kpi"><small>${a.toUpperCase()}</small><b>${b}</b><small>${c}</small></div>`).join("");

    $("#cards").innerHTML = ["1", "2", "3"].map((k) => {
      const v = stats(data.trades.filter((t) => String(t.strategy) === k && passes(t, true)));
      return `<div class="vc ${filt.strat === k ? "on" : ""}" data-s="${k}"><div class="t"><span>${NAME[k]}</span><span class="${cls(v.total)}">${sgn(v.total)}</span></div>
        <small>${v.n} trades · Win ${v.winRate.toFixed(1)}% · PF ${pfText(v.pf)} · Max DD ${inr(v.dd)}</small>${spark(v.curve, v.total >= 0)}</div>`;
    }).join("");

    let bk = `<div class="ph"><span>How trades ended · ${filt.strat ? NAME[filt.strat] : "all three strategies"}</span><span class="hint">Follows the filters above · net P&amp;L</span></div>`;
    if (!cur.length) bk += '<div class="empty">No trades match these filters.</div>';
    else bk += `<div class="bk"><div><h3>By exit</h3>${table(groupBy(cur, (t) => (filt.strat ? "" : SHORT[t.strategy] + " · ") + t.why).sort((a, b) => (a[0] < b[0] ? -1 : 1)), s, "How the trade ended")}</div>
      <div><h3>By year</h3>${table(groupBy(cur, (t) => t.date.slice(0, 4)), s, "Year")}</div></div>`;
    $("#breakdown").innerHTML = bk;

    if (!month) month = (cur.length ? cur[cur.length - 1].date : meta.data_to).slice(0, 7);
    if (sel && !cur.find((t) => t.id === sel)) sel = null;
    drawCalendar();
    if (!selDay) pickDay(cur.length ? cur[cur.length - 1].date : meta.data_to);
    else pickDay(selDay);
  }

  // ---------------------------------------------------------------- calendar
  function tradesOn(date) { return cur.filter((t) => t.date === date); }

  function drawCalendar() {
    const [y, m] = month.split("-").map(Number);
    const mt = cur.filter((t) => t.date.startsWith(month));
    const tot = mt.reduce((a, t) => a + t.net, 0);
    $("#mTitle").innerHTML = `${MONTHS[m - 1]} ${y} <span class="mtot ${cls(tot)}">${mt.length ? sgn(tot) + " · " + mt.length + " trade" + (mt.length > 1 ? "s" : "") : "no trades"}</span>`;
    let h = ["Mon", "Tue", "Wed", "Thu", "Fri"].map((d) => `<div class="wd">${d}</div>`).join("");
    const first = new Date(y, m - 1, 1), days = new Date(y, m, 0).getDate();
    let lead = (first.getDay() + 6) % 7;                      // Monday = 0
    if (lead > 4) lead = 0;                                   // month starts on a weekend
    for (let i = 0; i < lead; i++) h += '<div class="cd blank"></div>';
    for (let d = 1; d <= days; d++) {
      const wd = new Date(y, m - 1, d).getDay();
      if (wd === 0 || wd === 6) continue;
      const ds = `${month}-${String(d).padStart(2, "0")}`, day = dayMap.get(ds), ts = tradesOn(ds);
      if (!day) { h += `<div class="cd none"><span class="n">${d}</span><span class="s">no data</span></div>`; continue; }
      const net = ts.reduce((a, t) => a + t.net, 0);
      const c = ts.length ? (net >= 0 ? "w tr1" : "l tr1") : "tr0";
      h += `<div class="cd ${c} ${selDay === ds ? "on" : ""}" data-d="${ds}" title="${esc(dayTitle(day))}"><span class="n">${d}</span>${day.expiry ? '<span class="dot"></span>' : ""}
        ${ts.length ? `<span class="v ${cls(net)}">${sgn(net)}</span><span class="s">${[...new Set(ts.map((t) => SHORT[t.strategy]))].join(" ")}</span>` : '<span class="s">no trade</span>'}</div>`;
    }
    $("#calendar").innerHTML = `<div class="cg">${h}</div>`;
  }
  function dayTitle(day) {
    return (day.expiry ? "Weekly expiry (S3 day)" : "Normal day (S1 / S2)") + (day.gap != null ? ` · gap ${sp(day.gap)}` : "");
  }
  function shiftMonth(k) {
    const [y, m] = month.split("-").map(Number), d = new Date(y, m - 1 + k, 1);
    month = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    drawCalendar();
  }

  function pickDay(ds) {
    selDay = ds; month = ds.slice(0, 7);
    drawCalendar();
    const day = dayMap.get(ds), ts = tradesOn(ds);
    if (!day) { $("#dayPanel").innerHTML = ""; return; }
    const head = new Date(ds + "T00:00:00").toLocaleDateString("en-GB", { weekday: "long", day: "2-digit", month: "short", year: "numeric" });
    const strat = day.expiry ? ["3"] : ["1", "2"];
    $("#dayPanel").innerHTML = `<div><b>${head}</b> <span class="muted">· ${day.expiry ? "weekly expiry" : "normal day"}</span><br>
      <span class="muted">Prev close ${num(day.prev_close)} · Open ${num(day.open)} · Gap ${day.gap == null ? "-" : sp(day.gap)}</span></div>
      <div class="st">${strat.map((k) => `<b>${SHORT[k]}</b><span>${esc(day.status[k] || "")}</span>`).join("")}</div>
      ${ts.length ? `<div class="tb">${ts.map((t) => `<button data-t="${t.id}" class="${t.id === sel ? "on" : ""}">${SHORT[t.strategy]} ${t.entry_t} <span class="${cls(t.net)}">${sgn(t.net)}</span></button>`).join("")}</div>` : ""}`;
    const keep = ts.find((t) => t.id === sel);
    pickTrade(keep ? keep.id : ts.length ? ts[0].id : null, day);
  }

  // ---------------------------------------------------------------- trade view
  function pickTrade(id, day) {
    sel = id;
    document.querySelectorAll(".tb button").forEach((b) => b.classList.toggle("on", b.dataset.t === id));
    const t = data.trades.find((x) => x.id === id);
    drawTiles(t, day); drawRules(t, day); drawChart(t, day); drawEvents(day);
  }

  function drawTiles(t, day) {
    if (!t) { $("#detail").innerHTML = `<div class="empty">No trade on this day - the reason for each strategy is shown under the calendar.</div>`; return; }
    const k = t.strategy, p = k === 1 ? meta.s1 : k === 2 ? meta.s2 : null;
    const basis = t.entry + meta.slip, high = t.best + meta.slip;   // engine stores best high - 1 slippage
    let trail = "None - S3 exits on a Supertrend flip, the Rs 3,000 loss limit or 14:30";
    if (p) {
      const armAt = basis + p.arm, armed = high - basis >= p.arm;
      trail = armed ? `Armed once the option reached ${num(armAt)} (+${p.arm} pts) · stop raised to ${num(t.stop)}` : `Not armed - needed ${num(armAt)} (+${p.arm} pts), high was ${num(high)}`;
      trail += ` · trails ${p.dist} pts below the best`;
    }
    const tiles = [
      ["Strategy", `<span class="tag s${k}">${SHORT[k]}</span> ${NAME[k].slice(3)}`],
      ["Option bought", `${esc(t.option)} <span class="tag ${t.ty === "CE" ? "c" : "p"}">${t.side}</span>`],
      ["Signal", `${t.signal} candle <span class="muted">· ATM ${t.atm}, strike ${t.strike}</span>`],
      ["Entry", `${t.entry_t} at ${num(t.entry)} <span class="muted">(+1 slip = ${num(basis)})</span>`],
      ["Initial stop", `${num(t.stop0)} <span class="muted">(${num(basis - t.stop0, 1)} pts below cost)</span>`],
      ["Trailing stop", trail],
      ["Best price (option high)", `${num(high)} <span class="muted">(${sp(high - t.entry)} pts from entry)</span>`],
      ["Exit", `${t.exit_t} at ${num(t.exit)} <span class="muted">· ${esc(t.why)}${t.flip_at ? " (flip " + t.flip_at + ")" : ""}</span>`],
      ["Net P&L", `<span class="${cls(t.net)}">${sgn(t.net)}</span> <span class="muted">(${sp(t.exit - t.entry)} pts × ${meta.qty} − costs, held ${t.exit_min - t.entry_min} min)</span>`],
    ];
    $("#detail").innerHTML = `<div class="grid">${tiles.map(([a, b]) => `<div><label>${a}</label><b>${b}</b></div>`).join("")}</div>`;
  }

  const Y_ = (ok, text, note) => `<li><i class="${ok ? "y" : "n"}">${ok ? "✓" : "–"}</i><span>${text}${note ? ` <small>${note}</small>` : ""}</span></li>`;
  const H_ = (t) => `<h4>${t}</h4>`;

  function drawRules(t, day) {
    if (!t) { $("#rules").innerHTML = ""; return; }
    const k = t.strategy, f = day.first || {}, g = day.gap, basis = t.entry + meta.slip;
    let L = [];
    if (k === 1) {
      const p = meta.s1, body = f.c - f.o, rng = f.h - f.l, fr = (body > 0 ? f.h - f.c : f.c - f.l) / (rng || 1);
      const riskStop = basis - t.risk * p.delta;
      L = [H_("Day filter"),
        Y_(!day.expiry, "Not a weekly expiry day", "S1 and S2 trade normal days only"),
        Y_(Math.abs(g) >= p.gap_min && Math.abs(g) <= p.gap_max, `Gap ${sp(g)} pts is between ${p.gap_min} and ${p.gap_max}`, `open ${num(day.open)} − previous close ${num(day.prev_close)}`),
        H_("Signal - first 5-min candle (09:15-09:19)"),
        Y_(Math.abs(body) >= p.body, `Body ${sp(body)} pts is ${p.body}+`, `O ${num(f.o)} H ${num(f.h)} L ${num(f.l)} C ${num(f.c)}`),
        Y_(Math.sign(body) === Math.sign(g), `${body > 0 ? "Green" : "Red"} candle in the gap's direction (gap ${g > 0 ? "up" : "down"})`),
        Y_(fr <= p.fr, `Closes in its outer 40% (${(fr * 100).toFixed(0)}% from the ${body > 0 ? "high" : "low"})`),
        H_("Entry"),
        Y_(true, `Buy ITM 2 ${t.side}: ATM ${t.atm} ${t.ty === "CE" ? "−" : "+"} ${p.itm} = ${t.strike}`, "current-week expiry"),
        Y_(true, `Entry 09:20 at the option open ${num(t.entry)} (+1 slippage = ${num(basis)})`),
        H_("Stop and exit"),
        Y_(true, `Futures risk ${num(t.risk, 1)} pts (${body > 0 ? "close − (low − 5)" : "(high + 5) − close"}, max ${p.risk_cap}) × ${p.delta} → stop ${num(riskStop)}`),
        Y_(t.best - t.entry >= p.arm, `Trail: from +${p.arm} pts on the option, stop ${p.dist} pts below the best`, `option high ${num(t.best + meta.slip)}`),
        Y_(true, `Exit: ${t.why} at ${t.exit_t}, ${num(t.exit)}`, "time exit is 14:30")];
    } else if (k === 2) {
      const p = meta.s2, body = f.c - f.o, rh = t.range_high, rl = t.range_low;
      const rangeStop = basis - t.risk * p.delta, lossStop = t.entry - p.max_loss / meta.qty;
      L = [H_("Day filter"),
        Y_(!day.expiry, "Not a weekly expiry day"),
        Y_(Math.abs(g) >= p.gap_min, `Gap ${sp(g)} pts is ${p.gap_min}+`, "no upper limit for S2"),
        Y_((g > 0 && body < 0) || (g < 0 && body > 0), `First 5-min candle against the gap (${body > 0 ? "green" : "red"}, body ${sp(body)})`),
        H_("Signal"),
        Y_(true, `Range 09:15-09:44: high ${num(rh)}, low ${num(rl)}`),
        Y_(t.sig_close < rl && tmin(t.signal) + 5 <= 720, `First 5-min close outside the range was BELOW it: ${t.signal} candle closed ${num(t.sig_close)} < ${num(rl)}`, "by 12:00; a first close above the high means no trade"),
        H_("Entry"),
        Y_(true, `Buy ITM 2 PUT: ATM ${t.atm} + ${p.itm} = ${t.strike} at ${t.entry_t}, ${num(t.entry)} (+1 = ${num(basis)})`),
        H_("Stop and exit"),
        Y_(true, `Range stop: risk ${num(t.risk, 1)} pts (range high − close, max ${p.cap}) × ${p.delta} → ${num(rangeStop)}`),
        Y_(true, `Loss limit Rs ${p.max_loss.toLocaleString("en-IN")} → ${num(lossStop)}; the tighter one is used: ${num(t.stop0)}`),
        Y_(t.best - t.entry >= p.arm, `Trail: from +${p.arm} pts, stop ${p.dist} pts below the best`, `option high ${num(t.best + meta.slip)}`),
        Y_(true, `Exit: ${t.why} at ${t.exit_t}, ${num(t.exit)}`, "time exit is 14:30")];
    } else {
      const p = meta.s3, bar = (day.bars || []).find((b) => b[0] === tmin(t.signal));
      const o = bar ? bar[1] : null, c = t.sig_close;
      L = [H_("Day filter"),
        Y_(day.expiry, "Weekly expiry day", "S3 trades expiry days only"),
        H_(`Signal - ${t.signal} 5-min candle`),
        Y_(c < t.st, `Supertrend ${meta.s3.st} bearish (line ${num(t.st, 1)} above the close ${num(c, 1)})`),
        Y_(o != null && o < t.ema9 && c < t.ema9, `Open ${num(o, 1)} and close ${num(c, 1)} below EMA 9 (${num(t.ema9, 1)})`),
        Y_(t.ema9 < t.ema20, `EMA 9 ${num(t.ema9, 1)} below EMA 20 ${num(t.ema20, 1)}`),
        Y_(Math.abs(c - t.ema9) < 30, `Close within 30 pts of EMA 9 (${num(Math.abs(c - t.ema9), 1)})`),
        Y_(true, `ADX rising 2 candles: ${esc(t.adx)}`),
        Y_(true, `Fisher falling 2 candles: ${esc(t.fish)}`),
        Y_(tmin(t.signal) + 5 <= p.last_entry, "Signal by 14:00"),
        H_("Entry"),
        Y_(true, `Buy NEXT-week ITM 1 PUT: ATM ${t.atm} + ${p.itm} = ${t.strike} at ${t.entry_t}, ${num(t.entry)} (+1 = ${num(basis)})`),
        H_("Exit"),
        Y_(true, `Loss limit Rs ${p.max_loss.toLocaleString("en-IN")} → ${num(t.stop0)}`),
        Y_(true, `Exit on the first of: Supertrend flips bullish${t.flip_at ? " (" + t.flip_at + ")" : ""}, loss limit, 14:30 → ${t.why} at ${t.exit_t}, ${num(t.exit)}`)];
    }
    $("#rules").innerHTML = `<div class="ph"><span>How the ${SHORT[k]} rules were followed</span><span class="hint">values from the backtest engine</span></div><ul class="chk">${L.join("")}</ul>`;
  }

  // ---------------------------------------------------------------- futures chart (5-min) with the strategy's own lines
  const W = 860, PAD = { l: 8, r: 58, t: 14, b: 24 };
  function frame(x0, x1, y0, y1, H) {
    const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
    return { iw, X: (m) => PAD.l + ((m - x0) / (x1 - x0)) * iw, Y: (v) => PAD.t + (1 - (v - y0) / (y1 - y0)) * ih };
  }
  function axes(f, x0, x1, y0, y1, H) {
    let g = "";
    for (let i = 0; i <= 4; i++) { const v = y0 + ((y1 - y0) * i) / 4, y = f.Y(v); g += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${W - PAD.r + 5}" y="${y + 4}">${num(v, 0)}</text>`; }
    for (let m = 570; m <= x1; m += 60) { const x = f.X(m); g += `<line x1="${x}" x2="${x}" y1="${PAD.t}" y2="${H - PAD.b}" stroke="var(--line)"/><text x="${x - 14}" y="${H - 7}">${clock(m)}</text>`; }
    return g;
  }
  function vline(f, m, color, label, H, dash = "4 3", row = 0) {
    const x = f.X(m);
    return `<line x1="${x}" x2="${x}" y1="${PAD.t}" y2="${H - PAD.b}" stroke="${color}" stroke-dasharray="${dash}" opacity=".85"/>` +
      (label ? `<text x="${Math.min(x + 4, W - PAD.r - 60)}" y="${PAD.t + 11 + row * 14}" style="fill:${color};font-weight:600">${label}</text>` : "");
  }
  function hline(f, v, color, label, x0m, x1m, right) {
    const y = f.Y(v), a = f.X(x0m), b = f.X(x1m);
    const txt = right ? `<text x="${b - 4}" y="${y - 4}" text-anchor="end" style="fill:${color}">${label}</text>` : `<text x="${a + 4}" y="${y - 4}" style="fill:${color}">${label}</text>`;
    return `<line x1="${a}" x2="${b}" y1="${y}" y2="${y}" stroke="${color}" stroke-dasharray="6 4" stroke-width="1.4"/>${txt}`;
  }

  function drawChart(t, day) {
    const el = $("#chartFut"), bars = day ? day.bars : [], H = 340;
    $("#futTitle").textContent = day ? `NIFTY futures · 5-minute candles · ${day.date}` : "NIFTY futures";
    if (!bars.length) { el.innerHTML = '<div class="empty">No futures candles for this day.</div>'; $("#legend").innerHTML = ""; return; }
    const k = t ? t.strategy : day.expiry ? 3 : 0;
    const vals = bars.flatMap((b) => [b[2], b[3]]);
    if (k === 3 && day.s3) vals.push(...day.s3.ema9.filter((v) => v != null), ...day.s3.ema20.filter((v) => v != null));
    if ((k === 1 || k === 0) && day.prev_close) vals.push(day.prev_close);
    let y0 = Math.min(...vals), y1 = Math.max(...vals); const pad = (y1 - y0) * 0.06 || 1; y0 -= pad; y1 += pad;
    const x0 = 555, x1 = 930, f = frame(x0, x1, y0, y1, H), bw = Math.max(2, (f.iw * 5 * 0.7) / (x1 - x0));
    let s = axes(f, x0, x1, y0, y1, H), legend = "";
    if (k === 1 || k === 2) {
      s += `<rect x="${f.X(555)}" y="${PAD.t}" width="${f.X(560) - f.X(555)}" height="${H - PAD.t - PAD.b}" fill="var(--accentbg)"/>`;
      if (day.prev_close) s += hline(f, day.prev_close, "var(--muted)", `Prev close ${num(day.prev_close, 1)}`, 555, 930);
      legend += '<i style="background:var(--accentbg)"></i>First candle ';
    }
    if (k === 2 && t) {
      s += `<rect x="${f.X(555)}" y="${f.Y(t.range_high)}" width="${f.X(585) - f.X(555)}" height="${f.Y(t.range_low) - f.Y(t.range_high)}" fill="var(--chip)" opacity=".9"/>`;
      s += hline(f, t.range_high, "var(--ema)", `Range high ${num(t.range_high, 1)}`, 555, 930, true) + hline(f, t.range_low, "var(--neg)", `Range low ${num(t.range_low, 1)}`, 555, 930, true);
      s += vline(f, 720, "var(--muted)", "12:00", H, "2 4");
      legend += '<i style="background:var(--ema)"></i>Range high <i style="background:var(--neg)"></i>Range low ';
    }
    for (const b of bars) {
      const cx = f.X(b[0] + 2.5), up = b[4] >= b[1], col = up ? "var(--pos)" : "var(--neg)";
      s += `<g><title>${clock(b[0])}  O ${num(b[1])}  H ${num(b[2])}  L ${num(b[3])}  C ${num(b[4])}</title><line x1="${cx}" x2="${cx}" y1="${f.Y(b[2])}" y2="${f.Y(b[3])}" stroke="${col}"/>
        <rect x="${cx - bw / 2}" y="${f.Y(Math.max(b[1], b[4]))}" width="${bw}" height="${Math.max(1, Math.abs(f.Y(b[1]) - f.Y(b[4])))}" fill="${col}"/></g>`;
    }
    if (k === 3 && day.s3) {
      const line = (arr, color, w, dash) => {
        const pts = arr.map((v, i) => (v == null ? null : f.X(bars[i][0] + 2.5).toFixed(1) + "," + f.Y(v).toFixed(1))).filter(Boolean).join(" ");
        return `<polyline fill="none" stroke="${color}" stroke-width="${w}" ${dash ? `stroke-dasharray="${dash}"` : ""} points="${pts}"/>`;
      };
      s += line(day.s3.ema9, "var(--accent)", 1.5) + line(day.s3.ema20, "var(--ema)", 1.5);
      let run = [], bull = null;
      const flush = () => { if (run.length > 1) s += `<polyline fill="none" stroke="var(--${bull ? "pos" : "neg"})" stroke-width="2" stroke-dasharray="5 3" points="${run.join(" ")}"/>`; run = []; };
      day.s3.st.forEach((v, i) => { const b = day.s3.bull[i]; if (b !== bull) { flush(); bull = b; } if (v != null) run.push(f.X(bars[i][0] + 2.5).toFixed(1) + "," + f.Y(v).toFixed(1)); });
      flush();
      s += vline(f, 840, "var(--muted)", "14:00", H, "2 4");
      legend += '<i style="background:var(--accent)"></i>EMA 9 <i style="background:var(--ema)"></i>EMA 20 <i style="background:var(--neg)"></i>Supertrend (bearish) <i style="background:var(--pos)"></i>(bullish) ';
    }
    if (t) {
      const sigM = tmin(t.signal);
      if (k !== 1) s += `<rect x="${f.X(sigM) - 1}" y="${PAD.t}" width="${f.X(sigM + 5) - f.X(sigM) + 2}" height="${H - PAD.t - PAD.b}" fill="var(--accent)" opacity=".12"/>`;
      const near = f.X(t.exit_min) - f.X(t.entry_min) < 75;      // labels would overlap: exit label one row lower
      s += vline(f, t.entry_min, "var(--pos)", `Entry ${t.entry_t}`, H) + vline(f, t.exit_min, "var(--neg)", `Exit ${t.exit_t}`, H, "4 3", near ? 1 : 0);
      legend += '<i style="background:var(--pos)"></i>Entry <i style="background:var(--neg)"></i>Exit';
    }
    $("#legend").innerHTML = legend;
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%">${s}</svg>`;
  }

  function drawEvents(day) {
    const ev = day ? day.events || [] : [];
    $("#events").innerHTML = `<div class="ph"><span>What the engine did that day</span></div>` +
      (ev.length ? `<div class="ev">${ev.map((e) => `<span>${e.t}</span><span>${esc(e.text)}</span>`).join("")}</div>` : '<div class="muted">No signals - see the reasons under the calendar.</div>');
  }

  // ---------------------------------------------------------------- events
  document.addEventListener("click", (e) => {
    const cd = e.target.closest(".cd[data-d]"); if (cd) return pickDay(cd.dataset.d);
    const tb = e.target.closest(".tb button"); if (tb) return pickTrade(tb.dataset.t, dayMap.get(selDay));
    const vc = e.target.closest(".vc"); if (vc) { filt.strat = filt.strat === vc.dataset.s ? "" : vc.dataset.s; $("#fStrat").value = filt.strat; return render(); }
  });
  $("#mPrev").addEventListener("click", () => shiftMonth(-1));
  $("#mNext").addEventListener("click", () => shiftMonth(1));
  const bind = (id, key) => $(id).addEventListener("change", (e) => { filt[key] = e.target.value; render(); });
  bind("#fStrat", "strat"); bind("#fOutcome", "outcome"); bind("#fReason", "reason"); bind("#fD1", "d1"); bind("#fD2", "d2");
  $("#reset").addEventListener("click", () => {
    Object.assign(filt, { strat: "", outcome: "", reason: "", d1: "", d2: "" });
    for (const [id, k] of [["#fStrat", "strat"], ["#fOutcome", "outcome"], ["#fReason", "reason"], ["#fD1", "d1"], ["#fD2", "d2"]]) $(id).value = filt[k];
    render();
  });
  $("#reload").addEventListener("click", () => { selDay = null; sel = null; month = null; boot(); });
  $("#theme").addEventListener("click", () => {
    const r = document.documentElement, dark = r.dataset.theme !== "dark";
    r.dataset.theme = dark ? "dark" : "light"; $("#theme").textContent = dark ? "Light" : "Dark";
    try { localStorage.setItem("bt-theme", r.dataset.theme); } catch (e) {}
  });
  try { const t = localStorage.getItem("bt-theme"); if (t === "dark") { document.documentElement.dataset.theme = "dark"; $("#theme").textContent = "Light"; } } catch (e) {}
  document.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes((document.activeElement || {}).tagName)) return;
    const i = cur.findIndex((t) => t.id === sel);
    const n = i < 0 ? cur.length - 1 : Math.max(0, Math.min(cur.length - 1, i + (e.key === "ArrowRight" ? 1 : -1)));
    if (cur[n]) { e.preventDefault(); sel = cur[n].id; pickDay(cur[n].date); }
  });
  boot();
})();
