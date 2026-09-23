"""MARKET CONTEXT — the daily bias board (console + visual dashboard).

Run: py -3.13 market_context.py            (prints board, writes + opens
                                            market_brief.html)
     py -3.13 market_context.py --no-open  (skip opening the browser)

Per market: BIAS (which side has permission today — the 5-day trend filter our
campaign validated), day LIVE/quiet (vol gate logic), stretch (RSI extremes =
crowding), today's news mapped to that market with UK times — and the written
REASON for every claim. Receipt stays on the page: unconditional direction
measured 50.1% on 913 unseen days; bias = permission + energy, not prophecy.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf

UK = ZoneInfo("Europe/London")
MARKETS = [("GC=F", "GOLD", ("USD",)), ("DX-Y.NYB", "DOLLAR", ("USD",)),
           ("ES=F", "S&P 500", ("USD",)), ("NQ=F", "NASDAQ 100", ("USD",)),
           ("^FTSE", "FTSE 100", ("GBP", "USD")), ("BTC-USD", "BITCOIN", ("USD",))]


def fetch_events():
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                         timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        rows = r.json()
    except Exception as e:
        print(f"(calendar feed unavailable: {str(e)[:60]})")
        return []
    out = []
    for ev in rows:
        try:
            t = datetime.fromisoformat(ev["date"]).astimezone(UK)
        except Exception:
            continue
        if ev.get("impact") in ("High", "Medium") \
                and ev.get("country") in ("USD", "GBP", "EUR"):
            out.append((t, ev.get("impact"), ev.get("country"), ev.get("title")))
    return sorted(out)


def read_gauges():
    """Fear gauges: each market's insurance price (conventional bands)."""
    GAUGES = [("^VIX", "VIX", "S&P 500", (15, 20, 30)),
              ("^VXN", "VXN", "NASDAQ 100", (20, 25, 35)),
              ("^GVZ", "GVZ", "GOLD", (14, 18, 28))]
    out = {}
    for sym, code, mkt, bands in GAUGES:
        try:
            v = read_market(sym)
        except Exception:
            continue
        a, b, c = bands
        lvl = v["last"]
        v["mood"] = ("CALM" if lvl < a else "NORMAL" if lvl < b else
                     "NERVOUS" if lvl < c else "EXTREME")
        v["mkt"] = mkt
        out[code] = v
    return out


def vix_card():
    """Fear gauges card, rendered from read_gauges()."""
    rows = ""
    for code, v in read_gauges().items():
        cls = {"CALM": "live", "NORMAL": "newslo", "NERVOUS": "warn",
               "EXTREME": "news"}[v["mood"]]
        rows += (f"<div class='ev'><span class='t'>{code}</span>"
                 f"<span class='cur'>{v['mkt']}</span><span><b>{v['last']:.1f}</b></span>"
                 f"<span class='chip {cls}'>{v['mood']}</span>"
                 f"<span class='cur'>20d pos {v['pos']:.0f}%</span></div>")
    if not rows:
        return ""
    return f"""
    <section class='card'>
      <header><h2>Fear gauges</h2><span class='bias flat'>OPTIONS MARKET NERVES</span></header>
      <div class='newsblock' style='border-top:none;margin-top:6px;padding-top:0'>{rows}</div>
      <ul class='why'>
        <li>Each is the price of insurance on its own market, read from options —
        the crowd's nerves, quantified. Bands are conventional: calm / normal /
        nervous / extreme (crisis).</li>
        <li>Context, not a signal: calm gauges under stretched indices mean any
        surprise lands on an unhedged crowd — violence risk, direction unknown.</li>
      </ul>
    </section>"""


def records_panel():
    """Live ledger: the two confirmed systems' paper records + the watch list."""
    here = os.path.dirname(os.path.abspath(__file__))
    rows = ""
    try:
        f = pd.read_csv(os.path.join(here, "gold_paper_log.csv"))
        pts = f["u1"].astype(float).sum() + pd.to_numeric(f["u2"], errors="coerce").fillna(0).sum()
        rows += (f"<div class='ev'><span class='t'>{len(f)}/40</span>"
                 f"<span>Gold 15:05 morning momentum — confirmed, paper stage</span>"
                 f"<span class='cur'>{pts:+.1f} pts</span></div>")
    except Exception:
        rows += ("<div class='ev'><span class='t'>0/40</span>"
                 "<span>Gold 15:05 morning momentum — confirmed, paper stage</span>"
                 "<span class='cur'>awaiting first trade</span></div>")
    try:
        d = pd.read_csv(os.path.join(here, "donchian_paper_log.csv"))
        rows += (f"<div class='ev'><span class='t'>{len(d)}/100</span>"
                 f"<span>Gold Donchian breakout drift — confirmed, machine-papered</span>"
                 f"<span class='cur'>{d['pts'].astype(float).sum():+.1f} pts</span></div>")
    except Exception:
        rows += ("<div class='ev'><span class='t'>0/100</span>"
                 "<span>Gold Donchian breakout drift — confirmed, machine-papered</span>"
                 "<span class='cur'>awaiting first signal</span></div>")
    watch = [
        ("Turn-of-month long, vol-gated", "gold", "+0.49/+0.78 both halves"),
        ("Volume-spike continuation +vol", "NAS100", "+5.41 @close n=350"),
        ("Asian-range sweep-reverse +trend", "S&amp;P", "+0.95 @close n=558"),
        ("NR7 breakout raw", "NAS100", "+7.06 @close n=194, thin"),
        ("Supertrend flip raw", "gold", "+0.01 — likely nothing"),
        ("Round-50 break +trend", "gold", "+0.05 — likely nothing"),
    ]
    wrows = "".join(f"<div class='ev'><span class='cur'>{mk}</span><span>{nm}</span>"
                    f"<span class='cur'>{st}</span></div>" for nm, mk, st in watch)
    return (f"<h3 class='section-h'>The record — earning trust daily</h3>"
            f"<div class='timeline'>{rows}"
            f"<h4 class='wk'>Watch list — unproven; judged only by data accruing since 22 Sep 2026</h4>"
            f"{wrows}</div>")


def read_market(symbol):
    df = yf.download(symbol, period="120d", interval="1d", progress=False,
                     auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["close"])
    c = df["close"]
    delta = c.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    dn = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - 100 / (1 + up / dn)).iloc[-1])
    rng = df["high"] - df["low"]
    med = float(rng.iloc[-21:-1].median())
    volx = float(rng.iloc[-1]) / max(med, 1e-9)
    hi20, lo20 = float(df["high"].iloc[-20:].max()), float(df["low"].iloc[-20:].min())
    pos = (float(c.iloc[-1]) - lo20) / max(hi20 - lo20, 1e-9) * 100
    c1, c6 = float(c.iloc[-2]), float(c.iloc[-7])
    trend = 1 if c1 > c6 else -1 if c1 < c6 else 0
    last, cL5 = float(c.iloc[-1]), float(c.iloc[-6])
    nxt = 1 if last > cL5 else -1 if last < cL5 else 0
    return dict(rsi=rsi, volx=volx, live=volx > 1.0, trend=trend, pos=pos,
                c1=c1, c6=c6, last=last, nxt=nxt)


def reasons(m):
    r = []
    if m["trend"] > 0:
        r.append(f"LONG side only — yesterday's close {m['c1']:,.1f} sits above the "
                 f"close five sessions back ({m['c6']:,.1f}); counter-trend trades "
                 f"tested as the losing side on every market.")
    elif m["trend"] < 0:
        r.append(f"SHORT side only — yesterday's close {m['c1']:,.1f} sits below the "
                 f"close five sessions back ({m['c6']:,.1f}).")
    else:
        r.append("No side — the 5-day trend is flat; no permission either way.")
    r.append((f"LIVE day — yesterday ranged {m['volx']:.2f}× its 20-day median; "
              "movement begets movement (the tested vol gate is open).")
             if m["live"] else
             (f"Quiet day — yesterday ranged only {m['volx']:.2f}× its 20-day "
              "median; edges tested near zero on quiet days."))
    if m["rsi"] >= 70:
        r.append(f"STRETCHED HIGH — RSI14 at {m['rsi']:.0f} and price at "
                 f"{m['pos']:.0f}% of its 20-day range: the crowd is leaning hard "
                 "one way, so surprises land violently. A caution flag, not a "
                 "short signal — stretch tested as no entry edge.")
    elif m["rsi"] <= 30:
        r.append(f"STRETCHED LOW — RSI14 at {m['rsi']:.0f}: crowded downside, "
                 "violent-bounce risk. Caution flag only.")
    return r


def fear_greed():
    """Fear & Greed dial: five crowd-mood components, each scored 0-100
    against its own trailing year, averaged. Description of mood, not a signal."""
    import math
    SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB"]
    tickers = ["^GSPC", "^VIX", "SPY", "TLT", "HYG", "LQD"] + SECTORS
    try:
        raw = yf.download(tickers, period="400d", interval="1d",
                          progress=False, auto_adjust=False)["Close"]
    except Exception:
        return None
    def prank(series):
        s = series.dropna()
        if len(s) < 60:
            return None
        tail = s.iloc[-252:]
        return float((tail < s.iloc[-1]).mean() * 100)
    comps = []
    spx = raw["^GSPC"].dropna()
    comps.append(("Momentum (S&P vs 125d avg)",
                  prank(spx / spx.rolling(125).mean() - 1)))
    vix = raw["^VIX"].dropna()
    comps.append(("Volatility (VIX vs its norm, inverted)",
                  prank(-(vix - vix.rolling(50).mean()))))
    sh = (raw["SPY"].pct_change(20) - raw["TLT"].pct_change(20))
    comps.append(("Safe-haven demand (stocks vs bonds)", prank(sh)))
    jk = (raw["HYG"].pct_change(20) - raw["LQD"].pct_change(20))
    comps.append(("Junk-bond appetite (risky vs safe credit)", prank(jk)))
    above = 0
    n_sec = 0
    for s in SECTORS:
        ser = raw[s].dropna()
        if len(ser) >= 60:
            n_sec += 1
            if ser.iloc[-1] > float(ser.rolling(50).mean().iloc[-1]):
                above += 1
    if n_sec:
        comps.append((f"Breadth ({above}/{n_sec} sectors above 50d avg)",
                      above / n_sec * 100))
    comps = [(n, v) for n, v in comps if v is not None]
    if len(comps) < 3:
        return None
    idx = float(np.mean([v for _, v in comps]))
    label = ("EXTREME FEAR" if idx < 25 else "FEAR" if idx < 45 else
             "NEUTRAL" if idx < 55 else "GREED" if idx < 75 else "EXTREME GREED")

    # gauge svg: five 36-degree bands, needle at idx
    def pol(r, deg):
        rad = math.radians(deg)
        return 110 + r * math.cos(rad), 105 - r * math.sin(rad)
    COLS = ["#f2594f", "#e8873c", "#e2b451", "#9fc35a", "#2fd6a4"]
    arcs = ""
    for i, col in enumerate(COLS):
        x0, y0 = pol(80, 180 - 36 * i - 2)
        x1, y1 = pol(80, 180 - 36 * (i + 1) + 2)
        arcs += (f"<path d='M {x0:.1f} {y0:.1f} A 80 80 0 0 1 {x1:.1f} {y1:.1f}' "
                 f"stroke='{col}' stroke-width='16' fill='none' stroke-linecap='round'/>")
    nx, ny = pol(62, 180 - idx * 1.8)
    svg = (f"<svg viewBox='0 0 220 130' style='width:100%;max-width:260px;display:block;margin:0 auto'>"
           f"{arcs}<line x1='110' y1='105' x2='{nx:.1f}' y2='{ny:.1f}' "
           f"stroke='#e6ecf7' stroke-width='3.5' stroke-linecap='round'/>"
           f"<circle cx='110' cy='105' r='6' fill='#e2b451'/></svg>")
    return dict(idx=idx, label=label, comps=comps, svg=svg)


def fg_card(fg):
    if not fg:
        return ""
    rows = "".join(f"<div class='ev'><span class='t'>{v:5.0f}</span><span>{n}</span></div>"
                   for n, v in fg["comps"])
    lcls = ("news" if fg["idx"] < 25 else "warn" if fg["idx"] < 45 else
            "newslo" if fg["idx"] < 55 else "live")
    return f"""
    <section class='card'>
      <header><h2>Fear &amp; Greed</h2><span class='chip {lcls}' style='font-size:12px'>{fg['label']}</span></header>
      {fg['svg']}
      <div style='text-align:center;font:700 30px var(--mono);margin:2px 0 10px'>{fg['idx']:.0f}</div>
      <div class='newsblock' style='border-top:none;padding-top:0'><label>Components (each 0-100 vs its own past year)</label>{rows}</div>
      <ul class='why'>
        <li>Crowd mood measured five ways and averaged — our own build of the
        classic dial, with the working parts shown. Description of sentiment,
        not a signal: the tested edges live in the gates, not here.</li>
      </ul>
    </section>"""


def next_session(cards, nxt_ev):
    """The standing setup for the next session: permission side + energy lean
    from the latest completed daily bar, plus what's scheduled. Direction
    stays unknowable — this is the setup, not the outcome."""
    rows = ""
    for name, m, _ in cards:
        side = ("LONG side" if m["nxt"] > 0 else
                "SHORT side" if m["nxt"] < 0 else "no side")
        scls = "live" if m["nxt"] > 0 else "news" if m["nxt"] < 0 else "quiet"
        lean = "likely LIVE" if m["volx"] > 1.0 else "leaning quiet"
        rows += (f"<div class='ev'><span class='cur'>{name}</span>"
                 f"<span class='chip {scls}'>{side}</span>"
                 f"<span>{lean} (latest session {m['volx']:.2f}× median)</span></div>")
    erows = "".join(f"<div class='ev'><span class='t'>{t:%H:%M}</span>"
                    f"<span class='imp {imp.lower()}'>{imp}</span>"
                    f"<span class='cur'>{cur}</span><span>{ti}</span></div>"
                    for t, imp, cur, ti in nxt_ev) or \
        "<div class='ev none'>Nothing medium/high-impact scheduled.</div>"
    return (f"<h3 class='section-h'>Next session — the standing setup</h3>"
            f"<div class='timeline'>{rows}"
            f"<h4 class='wk'>Scheduled for tomorrow</h4>{erows}"
            f"<div class='ev none'>Computed from the latest completed session — "
            f"permission and energy, never direction.</div></div>")


def html_report(cards, events, ahead, nxt_ev, now, path):
    days = {}
    for t, imp, cur, title in ahead:
        days.setdefault(t.date(), []).append((t, cur, title))
    ahead_html = "".join(
        f"<h4 class='wk'>{d:%A %d %B}</h4>" +
        "".join(f"<div class='ev'><span class='t'>{t:%H:%M}</span>"
                f"<span class='cur'>{cur}</span><span>{ti}</span></div>"
                for t, cur, ti in days[d])
        for d in sorted(days)) or \
        "<div class='ev none'>No further high-impact USD/GBP/EUR events this week.</div>"

    ev_rows = "".join(
        f"<div class='ev'><span class='t'>{t:%H:%M}</span>"
        f"<span class='imp {imp.lower()}'>{imp}</span>"
        f"<span class='cur'>{cur}</span><span>{title}</span></div>"
        for t, imp, cur, title in events) or "<div class='ev none'>No medium/high-impact USD, GBP or EUR events scheduled today.</div>"

    card_html = ""
    for name, m, evs in cards:
        state_html = ""
        if name == "GOLD":
            armed = m["live"] and m["trend"] != 0
            state_html = ("<div class='state on'>STATE: ARMED — the 15:05 ping decides</div>"
                          if armed else
                          "<div class='state off'>STATE: DEAD — gates shut, no trade possible today</div>")
        bias = ("LONG SIDE" if m["trend"] > 0 else
                "SHORT SIDE" if m["trend"] < 0 else "NO SIDE")
        bcls = "long" if m["trend"] > 0 else "short" if m["trend"] < 0 else "flat"
        chips = f"<span class='chip {'live' if m['live'] else 'quiet'}'>{'LIVE DAY' if m['live'] else 'QUIET DAY'}</span>"
        if m["rsi"] >= 70:
            chips += "<span class='chip warn'>STRETCHED HIGH</span>"
        elif m["rsi"] <= 30:
            chips += "<span class='chip warn'>STRETCHED LOW</span>"
        his = [t for t, imp, _ in evs if imp == "High"]
        if his:
            chips += f"<span class='chip news'>HIGH-IMPACT NEWS {min(his):%H:%M}</span>"
        elif evs:
            chips += f"<span class='chip newslo'>{len(evs)} medium event(s)</span>"
        nrows = "".join(f"<div class='ev'><span class='t'>{t:%H:%M}</span>"
                        f"<span class='imp {imp.lower()}'>{imp}</span><span>{ti}</span></div>"
                        for t, imp, ti in evs)
        why = "".join(f"<li>{x}</li>" for x in reasons(m))
        card_html += f"""
    <section class='card'>
      <header><h2>{name}</h2><span class='bias {bcls}'>{bias}</span></header>
      {state_html}
      <div class='chips'>{chips}</div>
      <div class='gauge'><label>RSI14 · {m['rsi']:.0f}</label>
        <div class='track rsi'><i style='left:{min(max(m['rsi'],0),100):.0f}%'></i></div></div>
      <div class='gauge'><label>20-day range position · {m['pos']:.0f}%</label>
        <div class='track'><i style='left:{min(max(m['pos'],0),100):.0f}%'></i></div></div>
      <div class='volx'>Yesterday's range: <b>{m['volx']:.2f}×</b> its 20-day median</div>
      {f"<div class='newsblock'><label>Today's events for this market</label>{nrows}</div>" if nrows else ""}
      <ul class='why'>{why}</ul>
    </section>"""

    page = f"""<title>Daily Bias Board</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap">
<style>
  :root {{ --bg:#0b1120; --panel:#121a2e; --line:#233150; --text:#e6ecf7;
          --mut:#8b96ad; --gold:#e2b451; --up:#2fd6a4; --dn:#f2594f;
          --mono:"IBM Plex Mono",Consolas,monospace; }}
  body {{ background:var(--bg); color:var(--text); margin:0;
         padding:28px 16px 48px; font:15px/1.5 "IBM Plex Sans",system-ui,sans-serif; }}
  .wrap {{ max-width:1080px; margin:0 auto; }}
  h1 {{ font-size:clamp(22px,4vw,30px); margin:0; }}
  .sub {{ color:var(--mut); font:500 13px var(--mono); margin:4px 0 24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }}
  .card header {{ display:flex; justify-content:space-between; align-items:center; }}
  .card h2 {{ margin:0; font-size:17px; }}
  .bias {{ font:700 12px var(--mono); letter-spacing:.08em; padding:4px 10px; border-radius:5px; }}
  .bias.long {{ background:rgba(47,214,164,.16); color:var(--up); }}
  .bias.short {{ background:rgba(242,89,79,.16); color:var(--dn); }}
  .bias.flat {{ background:rgba(139,150,173,.16); color:var(--mut); }}
  .chips {{ display:flex; flex-wrap:wrap; gap:6px; margin:10px 0 14px; }}
  .chip {{ font:600 10.5px var(--mono); letter-spacing:.05em; border-radius:999px; padding:3px 10px; }}
  .chip.live {{ background:rgba(47,214,164,.14); color:var(--up); }}
  .chip.quiet {{ background:rgba(139,150,173,.14); color:var(--mut); }}
  .chip.warn {{ background:rgba(226,180,81,.16); color:var(--gold); }}
  .chip.news {{ background:rgba(242,89,79,.16); color:var(--dn); }}
  .chip.newslo {{ background:rgba(91,139,217,.16); color:#8fb2e8; }}
  .gauge {{ margin:8px 0; }}
  .gauge label {{ font:500 11px var(--mono); color:var(--mut); }}
  .track {{ position:relative; height:8px; border-radius:4px; margin-top:4px;
           background:linear-gradient(90deg,#22304f,#2c3d63); }}
  .track.rsi {{ background:linear-gradient(90deg,#1f4f43 0 30%,#22304f 30% 70%,#5a2c33 70% 100%); }}
  .track i {{ position:absolute; top:-3px; width:3px; height:14px; background:var(--gold);
             border-radius:2px; transform:translateX(-50%); }}
  .volx {{ font-size:13px; color:var(--mut); margin:10px 0 4px; }}
  .volx b {{ color:var(--text); }}
  .newsblock {{ border-top:1px solid var(--line); margin-top:10px; padding-top:8px; }}
  .newsblock label {{ font:500 11px var(--mono); color:var(--mut); }}
  .ev {{ display:flex; gap:10px; align-items:baseline; padding:4px 0; font-size:13.5px; }}
  .ev .t {{ font:600 12.5px var(--mono); color:var(--gold); }}
  .imp {{ font:600 10px var(--mono); border-radius:4px; padding:1px 6px; }}
  .imp.high {{ background:rgba(242,89,79,.18); color:var(--dn); }}
  .imp.medium {{ background:rgba(226,180,81,.15); color:var(--gold); }}
  .cur {{ font:600 11px var(--mono); color:var(--mut); }}
  .ev.none {{ color:var(--mut); }}
  .why {{ margin:12px 0 0; padding-left:18px; color:var(--mut); font-size:13px; }}
  .why li {{ margin:5px 0; }}
  .section-h {{ font-size:16px; margin:30px 0 8px; }}
  .state {{ font:600 11.5px var(--mono); border-radius:6px; padding:6px 10px; margin-top:10px; }}
  .state.on {{ background:rgba(47,214,164,.12); color:var(--up); }}
  .state.off {{ background:rgba(139,150,173,.12); color:var(--mut); }}
  .wk {{ margin:12px 0 2px; color:var(--gold); font:600 12px var(--mono); }}
  .timeline {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 18px; }}
  footer {{ margin-top:30px; border-top:1px solid var(--line); padding-top:12px;
           color:var(--mut); font-size:12px; }}
  footer a {{ color:#8fb2e8; }}
</style>
<div class="wrap">
  <h1>Daily Bias Board</h1>
  <div class="sub">{now:%A %d %B %Y · generated %H:%M UK}</div>
  <div class="grid">{card_html}
{fg_card(fear_greed())}
{vix_card()}
  </div>
  <h3 class="section-h">Today's schedule — when volatility may arrive</h3>
  <div class="timeline">{ev_rows}</div>
{next_session(cards, nxt_ev)}
  <h3 class="section-h">Week ahead — high-impact only</h3>
  <div class="timeline">{ahead_html}</div>
  <footer>Sources: <a href="https://www.forexfactory.com/calendar">ForexFactory calendar</a> (live feed) ·
  price data Yahoo Finance daily · gates &amp; filters as validated in the banker-move campaign.<br>
  Receipt: unconditional day-direction measured <b>50.1%</b> over 913 unseen days —
  BIAS on this board means which side has permission and how alive the day is, never a promised destination.</footer>
</div>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


PAGE_URL = "https://elhashino.github.io/market-brief/"
TOPIC = "sunblessed-gold-mm-7x3q"


def ping_summary(cards, fg, events):
    """Telegraphic facts to the phone; tap-through opens the full board."""
    longs = sum(1 for _, m, _ in cards if m["trend"] > 0)
    shorts = sum(1 for _, m, _ in cards if m["trend"] < 0)
    live = [n for n, m, _ in cards if m["live"]]
    stretched = [n for n, m, _ in cards if m["rsi"] >= 70 or m["rsi"] <= 30]
    gold = next((m for n, m, _ in cards if n == "GOLD"), None)
    bits = [f"{longs} long-side / {shorts} short-side",
            "LIVE: " + (", ".join(live) if live else "none"),
            "stretched: " + (", ".join(stretched) if stretched else "none")]
    if fg:
        bits.append(f"F&G {fg['idx']:.0f} {fg['label']}")
    if gold:
        armed = gold["live"] and gold["trend"] != 0
        bits.append("gold: " + ("ARMED" if armed else "DEAD"))
    his = [(t, ti) for t, imp, cur, ti in events if imp == "High"]
    bits.append("high-impact: " + (", ".join(f"{t:%H:%M} {ti}" for t, ti in his[:2])
                                   if his else "none"))
    msg = " | ".join(bits)
    title = ("Morning market brief (backup)" if os.environ.get("BACKUP")
             else "Morning market brief")
    try:
        requests.post(f"https://ntfy.sh/{TOPIC}", data=msg.encode(),
                      headers={"Title": title, "Click": PAGE_URL}, timeout=15)
        print("ping sent:", msg)
    except Exception as e:
        print("ping failed:", e)


def main():
    now = datetime.now(UK)
    print(f"MARKET CONTEXT — {now:%A %d %b %Y, %H:%M} UK\n")
    allev = fetch_events()
    events = [e for e in allev if e[0].date() == now.date()]
    ahead = [e for e in allev if e[0].date() > now.date() and e[1] == "High"]
    nxt_ev = [e for e in allev if e[0].date() == now.date() + timedelta(days=1)]
    cards = []
    for sym, name, curs in MARKETS:
        try:
            m = read_market(sym)
        except Exception as e:
            print(f"  {name:10} data unavailable ({str(e)[:40]})")
            continue
        evs = [(t, imp, ti) for t, imp, cur, ti in events if cur in curs]
        cards.append((name, m, evs))
        bias = ("LONG side only " if m["trend"] > 0 else
                "SHORT side only" if m["trend"] < 0 else "NO side (flat) ")
        print(f"  {name:10} {bias} | {'LIVE ' if m['live'] else 'quiet'} | "
              f"RSI {m['rsi']:.0f} | news {len(evs)}")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    html_report(cards, events, ahead, nxt_ev, now, path)
    print(f"\ndashboard written: {path}")
    ping_summary(cards, fear_greed(), events)


if __name__ == "__main__":
    main()
