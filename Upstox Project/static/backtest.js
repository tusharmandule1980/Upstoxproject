(() => {
  const $ = (s) => document.querySelector(s);
  const inr = (n) => (n < 0 ? "-" : "") + "₹" + Math.abs(Math.round(n)).toLocaleString("en-IN");
  const sgn = (n) => (n > 0 ? "+" : "") + inr(n);
  const cls = (n) => (n > 0 ? "pos" : n < 0 ? "neg" : "");
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const mm = (s) => parseInt(s.slice(11, 13), 10) * 60 + parseInt(s.slice(14, 16), 10);
  const hhmm = (s) => s.slice(11, 16);
  const clock = (m) => String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  const num = (v, d = 2) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
  const dayName = (d) => new Date(d + "T00:00:00").toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", month: "short", year: "numeric" }).replace(/,/g, "").toUpperCase();

  let meta = null, tf = null, rows = [], cur = [], sel = null, variant = null, tok = 0;
  const detailCache = new Map();
  const filt = { dir: "", from: "09:25", to: "14:30", outcome: "", reason: "", dte: "", d1: "", d2: "" };

  function show(msg) { const m = $("#msg"); m.hidden = !msg; m.innerHTML = msg || ""; $("#app").hidden = !!msg; }

  async function boot() {
    const r = await fetch("/api/bt/meta");
    if (!r.ok) { const j = await r.json().catch(() => ({})); show("<b>No results yet.</b><br>" + esc(j.error || "Double-click backtest.bat first, then reload this page.")); return; }
    meta = await r.json();
    show("");
    $("#range").textContent = "Data " + meta.data_from + " → " + meta.data_to;
    $("#fVariant").innerHTML = Object.entries(meta.variants).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
    variant = variant && meta.variants[variant] ? variant : Object.keys(meta.variants)[0];
    $("#fVariant").value = variant;
    if (!meta.timeframes.includes(tf)) tf = meta.timeframes[0];
    $("#tfSeg").innerHTML = meta.timeframes.map((t) => `<button data-tf="${t}">${t}m</button>`).join("");
    await loadTf(tf);
  }

  async function loadTf(t) {
    tf = t;
    const r = await fetch("/api/bt/trades/" + t);
    const j = await r.json();
    rows = j.data.map((a) => Object.fromEntries(j.columns.map((c, i) => [c, a[i]])));
    const reasons = [...new Set(rows.map((x) => x.exit_reason))].sort();
    $("#fReason").innerHTML = '<option value="">All</option>' + reasons.map((x) => `<option>${esc(x)}</option>`).join("");
    $("#fReason").value = reasons.includes(filt.reason) ? filt.reason : "";
    render();
  }

  function passes(t, anyVariant) {
    if (!anyVariant && t.variant !== variant) return false;
    if (filt.dir && t.side !== filt.dir) return false;
    const m = mm(t.entry_time);
    if (filt.from && m < parseInt(filt.from.slice(0, 2), 10) * 60 + parseInt(filt.from.slice(3), 10)) return false;
    if (filt.to && m > parseInt(filt.to.slice(0, 2), 10) * 60 + parseInt(filt.to.slice(3), 10)) return false;
    if (filt.outcome === "win" && !(t.pnl > 0)) return false;
    if (filt.outcome === "loss" && !(t.pnl < 0)) return false;
    if (filt.reason && t.exit_reason !== filt.reason) return false;
    if (filt.dte !== "") { const d = t.days_to_expiry; if (filt.dte === "3" ? d < 3 : d !== Number(filt.dte)) return false; }
    if (filt.d1 && t.date < filt.d1) return false;
    if (filt.d2 && t.date > filt.d2) return false;
    return true;
  }

  function stats(list) {
    const s = { n: list.length, w: 0, l: 0, total: 0, gw: 0, gl: 0, dd: 0, best: 0, worst: 0, curve: [0] };
    const sorted = [...list].sort((a, b) => (a.exit_time < b.exit_time ? -1 : a.exit_time > b.exit_time ? 1 : 0));
    let eq = 0, peak = 0;
    for (const t of sorted) {
      eq += t.pnl; peak = Math.max(peak, eq); s.dd = Math.min(s.dd, eq - peak); s.curve.push(eq);
      if (t.pnl > 0) { s.w++; s.gw += t.pnl; } else if (t.pnl < 0) { s.l++; s.gl += -t.pnl; }
      s.best = Math.max(s.best, t.pnl); s.worst = Math.min(s.worst, t.pnl);
    }
    s.total = eq;
    s.winRate = s.n ? (s.w / s.n) * 100 : 0;
    s.exp = s.n ? s.total / s.n : 0;
    s.pf = s.gl ? s.gw / s.gl : s.gw ? Infinity : 0;
    s.payoff = s.w && s.l ? s.gw / s.w / (s.gl / s.l) : 0;
    return s;
  }
  const pfText = (v) => (v === Infinity ? "∞" : v.toFixed(2));

  // ---------------------------------------------------------------- how trades ended (follows the filters)
  const REASON = { "EMA exit": "EMA exit · closed beyond the 20 EMA", "stop loss": "Stop loss", "trail stop": "Trail stop",
    "DI exit": "DI exit", "EMA gap exit": "EMA gap exit", "end of data": "End of data" };
  const reasonLabel = (r) => (r === "square-off" ? `Square-off at ${meta.square_off || "14:30"}` : REASON[r] || r);

  function groupStats(list, key) {
    const m = new Map();
    for (const t of list) { const k = key(t); if (!m.has(k)) m.set(k, []); m.get(k).push(t); }
    return [...m.entries()].map(([k, v]) => [k, stats(v)]);
  }

  function bkTable(groups, total, head) {
    const row = (name, s, tot) => `<tr${tot ? ' class="tot"' : ""}><td>${esc(name)}</td><td>${s.n.toLocaleString("en-IN")}</td>
      <td>${s.winRate.toFixed(1)}%</td><td class="${cls(s.total)}">${sgn(s.total)}</td><td class="${cls(s.exp)}">${sgn(s.exp)}</td></tr>`;
    return `<table class="tbl"><tr><th>${head}</th><th>Trades</th><th>Win rate</th><th>Gross P&amp;L</th><th>Avg / trade</th></tr>
      ${groups.map(([k, s]) => row(k, s)).join("")}${row("All trades", total, true)}</table>`;
  }

  function breakdown(list) {
    let html = `<div class="ph"><span>How trades ended · ${esc(meta.variants[variant] || variant)} · ${tf}-minute candles</span>
      <span class="hint">Follows the filters above · gross P&amp;L</span></div>`;
    if (meta.rules) html += `<p class="rules">Rules · ${esc(meta.rules)}</p>`;
    if (!list.length) return html + '<div class="empty">No trades match these filters.</div>';
    const total = stats(list);
    const byExit = groupStats(list, (t) => reasonLabel(t.exit_reason)).sort((a, b) => b[1].total - a[1].total);
    const bySide = groupStats(list, (t) => t.side).sort((a, b) => (a[0] < b[0] ? -1 : 1))
      .map(([k, s]) => [k === "CALL" ? `Calls · stop ${inr(meta.call_max_loss)}` : `Puts · stop ${inr(meta.max_loss)}`, s]);
    return html + `<div class="bk"><div><h3>By exit</h3>${bkTable(byExit, total, "How the trade ended")}</div>
      <div><h3>Calls vs puts</h3>${bkTable(bySide, total, "Side")}</div></div>`;
  }

  function spark(curve, good) {
    const n = curve.length, lo = Math.min(0, ...curve), hi = Math.max(0, ...curve), sp = hi - lo || 1;
    const X = (i) => 2 + (i * 296) / Math.max(1, n - 1), Y = (v) => 52 - ((v - lo) / sp) * 48;
    const pts = curve.map((v, i) => X(i).toFixed(1) + "," + Y(v).toFixed(1)).join(" ");
    return `<svg viewBox="0 0 300 56" preserveAspectRatio="none"><line x1="0" x2="300" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)" stroke-dasharray="3"/><polyline fill="none" stroke="var(--${good ? "pos" : "neg"})" stroke-width="1.6" points="${pts}"/></svg>`;
  }

  function render() {
    document.querySelectorAll("#tfSeg button").forEach((b) => b.classList.toggle("on", Number(b.dataset.tf) === tf));
    cur = rows.filter((t) => passes(t, false));
    const s = stats(cur);
    const selRow = cur.find((t) => t.id === sel);
    $("#kpis").innerHTML = [
      ["Total trades", s.n.toLocaleString("en-IN"), `${s.w} wins · ${s.l} losses`],
      ["Win rate", s.winRate.toFixed(1) + "%", `Expectancy ${inr(s.exp)} / trade`],
      ["Total P&L (gross)", `<span class="${cls(s.total)}">${sgn(s.total)}</span>`, "Taxes & charges excluded"],
      ["Max drawdown", `<span class="${s.dd < 0 ? "neg" : ""}">${inr(s.dd)}</span>`, `Best ${inr(s.best)} · Worst ${inr(s.worst)}`],
      ["Profit factor", pfText(s.pf), `Payoff ratio ${s.payoff.toFixed(2)}`],
      ["Selected trade", selRow ? `<span class="${cls(selRow.pnl)}">${sgn(selRow.pnl)}</span>` : "-", selRow ? selRow.entry_time : "Click a trade"],
    ].map(([a, b, c]) => `<div class="kpi"><small>${a.toUpperCase()}</small><b>${b}</b><small>${c}</small></div>`).join("");

    $("#variants").innerHTML = Object.entries(meta.variants).map(([k, name]) => {
      const v = stats(rows.filter((t) => t.variant === k && passes(t, true)));
      return `<div class="vc ${k === variant ? "on" : ""}" data-v="${k}"><div class="t"><span>${esc(name)}</span><span class="${cls(v.total)}">${sgn(v.total)}</span></div>
        <small>${v.n} trades · Win ${v.winRate.toFixed(1)}% · PF ${pfText(v.pf)} · Max DD ${inr(v.dd)}</small>${spark(v.curve, v.total >= 0)}</div>`;
    }).join("");

    $("#breakdown").innerHTML = breakdown(cur);
    $("#listTitle").textContent = `Trades (${cur.length.toLocaleString("en-IN")})`;
    if (!cur.length) { $("#list").innerHTML = '<div class="empty">No trades match these filters.</div>'; sel = null; drawDetail(null); return; }
    let html = "", last = "";
    for (const t of cur) {
      if (t.date !== last) { html += `<div class="dh">${dayName(t.date)}</div>`; last = t.date; }
      const sym = t.option_symbol.replace(/^NIFTY\s+/, "");
      html += `<div class="tr ${t.id === sel ? "on" : ""}" data-id="${t.id}"><span>${hhmm(t.entry_time)}</span>
        <span>${esc(sym)} <span class="tag ${t.side === "CALL" ? "c" : "p"}">${t.side === "CALL" ? "CALL" : "PUT"}</span></span><span class="p ${cls(t.pnl)}">${sgn(t.pnl)}</span>
        <span class="s">→ ${hhmm(t.exit_time)} · ${esc(t.exit_reason)}</span></div>`;
    }
    $("#list").innerHTML = html;
    if (!selRow) select(cur[0].id, false); else drawDetailFor(selRow);
  }

  function select(id, scroll) {
    sel = id;
    document.querySelectorAll(".tr").forEach((e) => e.classList.toggle("on", Number(e.dataset.id) === id));
    const row = cur.find((t) => t.id === id);
    if (scroll) { const e = document.querySelector(`.tr[data-id="${id}"]`); if (e) e.scrollIntoView({ block: "nearest" }); }
    if (row) { const k = document.querySelectorAll(".kpi b")[5]; if (k) k.innerHTML = `<span class="${cls(row.pnl)}">${sgn(row.pnl)}</span>`; drawDetailFor(row); }
  }

  async function drawDetailFor(row) {
    const my = ++tok;
    let d = detailCache.get(row.id);
    if (!d) {
      drawDetail(row, null);
      try { d = await (await fetch("/api/bt/trade/" + row.id)).json(); detailCache.set(row.id, d); } catch (e) { return; }
    }
    if (my === tok) drawDetail(row, d);
  }

  function drawDetail(t, d) {
    if (!t) { $("#detail").innerHTML = '<div class="empty">Select a trade</div>'; $("#chartFut").innerHTML = ""; $("#chartOpt").innerHTML = ""; return; }
    const bull = t.side === "CALL";
    const flags = [];
    if (t.days_to_expiry === 0) flags.push('<span class="pill r">Expiry day</span>');
    if (t.trail_steps > 0) flags.push(`<span class="pill g">Trail moved ×${t.trail_steps}</span>`);
    if (t.mean_holds > 0) flags.push(`<span class="pill g">09:15 average kept it open ×${t.mean_holds}</span>`);
    if (t.exit_reason === "stop loss") flags.push('<span class="pill r">Stop loss hit</span>');
    if (t.exit_reason === "square-off") flags.push('<span class="pill">Held to square-off</span>');
    if (!flags.length) flags.push('<span class="pill">None</span>');
    const tr = d && d.trade;
    $("#detail").innerHTML = `<div class="grid">
      <div><label>Symbol</label><b>${esc(t.option_symbol)} <span class="tag ${bull ? "c" : "p"}">BUY</span></b></div>
      <div><label>Direction</label><b><span class="pill ${bull ? "g" : "r"}">${bull ? "BULLISH" : "BEARISH"}</span> signal ${hhmm(t.signal_time)}</b></div>
      <div><label>NIFTY futures entry → exit</label><b>${num(t.fut_entry)} → ${num(t.fut_exit)}</b></div>
      <div><label>Option entry → exit</label><b>${num(t.entry_price)} → ${num(t.exit_price)} <span class="muted">(${t.points >= 0 ? "+" : ""}${num(t.points)} pts)</span></b></div>
      <div><label>Time</label><b>${hhmm(t.entry_time)} → ${hhmm(t.exit_time)} <span class="muted">(${t.minutes_held} min)</span></b></div>
      <div><label>Expiry / DTE</label><b>${t.expiry} · ${t.days_to_expiry}d</b></div>
      <div><label>Exit reason</label><b>${esc(t.exit_reason)}</b></div>
      <div><label>Gross P&amp;L</label><b class="${cls(t.pnl)}">${sgn(t.pnl)} <span class="muted">(${t.qty} qty)</span></b></div>
      <div><label>Best gain in trade</label><b>${num(t.best_points)} pts</b></div>
      <div><label>Flags</label><b>${flags.join("")}</b></div>
      ${tr ? `<div style="grid-column:1/-1"><label>Signal candle readings</label><b style="font-weight:500">EMA ${num(tr.ema)} · +DI ${num(tr.pdi)} · ADX ${num(tr.adx)} · RSI ${num(tr.rsi)} · MACD ${num(tr.macd)}</b></div>` : ""}
    </div>`;
    $("#futTitle").textContent = `NIFTY futures · ${t.timeframe || tf}-minute bars · ${t.date}`;
    $("#optTitle").textContent = `Option premium · ${t.option_symbol} · 1-minute`;
    if (!d) { $("#chartFut").innerHTML = '<div class="empty">Loading chart…</div>'; $("#chartOpt").innerHTML = ""; return; }
    drawFutures(t, d); drawOption(t, d);
  }

  // ---------------------------------------------------------------- charts
  const W = 860, PAD = { l: 8, r: 58, t: 14, b: 24 };
  function frame(x0, x1, y0, y1, H) {
    const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
    return { iw, ih, X: (m) => PAD.l + ((m - x0) / (x1 - x0)) * iw, Y: (v) => PAD.t + (1 - (v - y0) / (y1 - y0)) * ih };
  }
  function axes(f, x0, x1, y0, y1, H) {
    let g = "";
    for (let i = 0; i <= 4; i++) { const v = y0 + ((y1 - y0) * i) / 4, y = f.Y(v); g += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${W - PAD.r + 5}" y="${y + 4}">${num(v, v > 1000 ? 0 : 1)}</text>`; }
    const span = x1 - x0, step = [5, 10, 15, 30, 60].find((s) => span / s <= 8) || 60;
    for (let m = Math.ceil(x0 / step) * step; m <= x1; m += step) { const x = f.X(m); g += `<line x1="${x}" x2="${x}" y1="${PAD.t}" y2="${H - PAD.b}" stroke="var(--line)"/><text x="${x - 14}" y="${H - 7}">${clock(m)}</text>`; }
    return g;
  }
  function marker(f, m, v, color, label, H) {
    const x = f.X(m), y = f.Y(v);
    return `<line x1="${x}" x2="${x}" y1="${PAD.t}" y2="${H - PAD.b}" stroke="${color}" stroke-dasharray="4 3" opacity=".8"/><circle cx="${x}" cy="${y}" r="5" fill="${color}" stroke="var(--card)" stroke-width="2"/><text x="${Math.min(x + 6, W - PAD.r - 34)}" y="${PAD.t + 11}" style="fill:${color};font-weight:600">${label}</text>`;
  }

  function drawFutures(t, d) {
    const el = $("#chartFut"), c = d.futures, H = 320;
    if (!c.length) { el.innerHTML = '<div class="empty">No futures candles found for this day.</div>'; return; }
    const tfm = Number(t.timeframe || tf);
    const lows = c.map((x) => x.l), highs = c.map((x) => x.h), emas = c.filter((x) => x.ema != null).map((x) => x.ema);
    const means = c.filter((x) => x.mean != null).map((x) => x.mean);
    const all = [...lows, ...highs, ...emas, ...means, t.fut_entry, t.fut_exit];
    let y0 = Math.min(...all), y1 = Math.max(...all); const pad = (y1 - y0) * 0.06 || 1; y0 -= pad; y1 += pad;
    const x0 = 555, x1 = 935, f = frame(x0, x1, y0, y1, H), bw = Math.max(2, (f.iw * tfm * 0.7) / (x1 - x0));
    let s = axes(f, x0, x1, y0, y1, H);
    for (const x of c) {
      const cx = f.X(x.m + tfm / 2), up = x.c >= x.o, col = up ? "var(--pos)" : "var(--neg)";
      s += `<g><title>${clock(x.m)}  O ${num(x.o)}  H ${num(x.h)}  L ${num(x.l)}  C ${num(x.c)}</title><line x1="${cx}" x2="${cx}" y1="${f.Y(x.h)}" y2="${f.Y(x.l)}" stroke="${col}"/>
        <rect x="${cx - bw / 2}" y="${f.Y(Math.max(x.o, x.c))}" width="${bw}" height="${Math.max(1, Math.abs(f.Y(x.o) - f.Y(x.c)))}" fill="${col}"/></g>`;
    }
    const pts = c.filter((x) => x.ema != null).map((x) => f.X(x.m + tfm / 2).toFixed(1) + "," + f.Y(x.ema).toFixed(1)).join(" ");
    s += `<polyline fill="none" stroke="var(--ema)" stroke-width="1.8" points="${pts}"/>`;
    const mpts = c.filter((x) => x.mean != null).map((x) => f.X(x.m + tfm / 2).toFixed(1) + "," + f.Y(x.mean).toFixed(1)).join(" ");
    if (mpts) s += `<polyline fill="none" stroke="var(--mean)" stroke-width="1.6" stroke-dasharray="6 4" points="${mpts}"/>`;
    s += marker(f, mm(t.entry_time), t.fut_entry, "var(--pos)", "Entry", H) + marker(f, mm(t.exit_time), t.fut_exit, "var(--neg)", "Exit", H);
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%">${s}</svg>`;
  }

  function drawOption(t, d) {
    const el = $("#chartOpt"), c = d.option, H = 260;
    if (!c.length) { el.innerHTML = '<div class="empty">No option candles found.</div>'; return; }
    const em = mm(t.entry_time), xm = mm(t.exit_time), stop = t.entry_price - d.stop_points;
    const x0 = Math.max(555, em - 25), x1 = Math.min(935, xm + 25);
    const v = c.filter((x) => x.m >= x0 && x.m <= x1);
    const all = [...v.map((x) => x.l), ...v.map((x) => x.h), t.entry_price, t.exit_price, stop];
    let y0 = Math.min(...all), y1 = Math.max(...all); const pad = (y1 - y0) * 0.08 || 1; y0 -= pad; y1 += pad;
    const f = frame(x0, x1, y0, y1, H);
    let s = axes(f, x0, x1, y0, y1, H);
    const line = v.map((x) => f.X(x.m).toFixed(1) + "," + f.Y(x.c).toFixed(1)).join(" ");
    s += `<polyline fill="none" stroke="var(--accent)" stroke-width="1.8" points="${line}"/>`;
    s += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${f.Y(t.entry_price)}" y2="${f.Y(t.entry_price)}" stroke="var(--pos)" stroke-dasharray="5 4" opacity=".7"/>`;
    s += `<line x1="${PAD.l}" x2="${W - PAD.r}" y1="${f.Y(stop)}" y2="${f.Y(stop)}" stroke="var(--neg)" stroke-dasharray="5 4" opacity=".7"/><text x="${PAD.l + 4}" y="${f.Y(stop) - 4}" style="fill:var(--neg)">Initial stop ${num(stop)}</text>`;
    s += marker(f, em, t.entry_price, "var(--pos)", "Entry", H) + marker(f, xm, t.exit_price, "var(--neg)", "Exit", H);
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%">${s}</svg>`;
  }

  // ---------------------------------------------------------------- events
  document.addEventListener("click", (e) => {
    const tr = e.target.closest(".tr"); if (tr) return select(Number(tr.dataset.id), false);
    const vc = e.target.closest(".vc"); if (vc) { variant = vc.dataset.v; $("#fVariant").value = variant; sel = null; return render(); }
    const tb = e.target.closest("#tfSeg button"); if (tb) { sel = null; return loadTf(Number(tb.dataset.tf)); }
  });
  const bind = (id, key, after) => $(id).addEventListener("change", (e) => { filt[key] = e.target.value; if (after) after(); render(); });
  bind("#fDir", "dir"); bind("#fFrom", "from"); bind("#fTo", "to"); bind("#fOutcome", "outcome"); bind("#fReason", "reason"); bind("#fDte", "dte"); bind("#fD1", "d1"); bind("#fD2", "d2");
  $("#fVariant").addEventListener("change", (e) => { variant = e.target.value; sel = null; render(); });
  $("#reset").addEventListener("click", () => {
    Object.assign(filt, { dir: "", from: "09:25", to: "14:30", outcome: "", reason: "", dte: "", d1: "", d2: "" });
    for (const [id, k] of [["#fDir", "dir"], ["#fFrom", "from"], ["#fTo", "to"], ["#fOutcome", "outcome"], ["#fReason", "reason"], ["#fDte", "dte"], ["#fD1", "d1"], ["#fD2", "d2"]]) $(id).value = filt[k];
    sel = null; render();
  });
  $("#reload").addEventListener("click", () => { detailCache.clear(); boot(); });
  $("#theme").addEventListener("click", () => {
    const r = document.documentElement, dark = r.dataset.theme !== "dark";
    r.dataset.theme = dark ? "dark" : "light"; $("#theme").textContent = dark ? "Light" : "Dark";
    try { localStorage.setItem("bt-theme", r.dataset.theme); } catch (e) {}
  });
  try { const t = localStorage.getItem("bt-theme"); if (t === "dark") { document.documentElement.dataset.theme = "dark"; $("#theme").textContent = "Light"; } } catch (e) {}
  document.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes((document.activeElement || {}).tagName)) return;
    const i = cur.findIndex((t) => t.id === sel), n = Math.max(0, Math.min(cur.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)));
    if (cur[n]) { e.preventDefault(); select(cur[n].id, true); }
  });
  boot();
})();
