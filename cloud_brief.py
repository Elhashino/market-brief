"""MARKET CONTEXT — cloud edition (GitHub Actions).

Generated from the PC master (market_context.py) by build_cloud.py — edit the
master, rebuild this. Writes docs/index.html for GitHub Pages and pings the
headline via ntfy with a tap-through link. Page rebuilds on every weekday run;
only the ping is gated (send window + channel dedupe).
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf

UK = ZoneInfo("Europe/London")
NY = ZoneInfo("America/New_York")
MARKETS =[("GC=F", "GOLD", ("USD",)), ("DX-Y.NYB", "DOLLAR", ("USD",)),
           ("ES=F", "S&P 500", ("USD",)), ("NQ=F", "NASDAQ 100", ("USD",)),
           ("^FTSE", "FTSE 100", ("GBP", "USD")), ("BTC-USD", "BITCOIN", ("USD",))]
SOURCES = {"GC=F": "gold futures, GC=F", "DX-Y.NYB": "dollar index, DX-Y.NYB",
           "ES=F": "S&P futures, ES=F", "NQ=F": "Nasdaq futures, NQ=F",
           "^FTSE": "FTSE cash index", "BTC-USD": "Yahoo BTC-USD"}


def fetch_events():
    """This week's medium/high USD, GBP and EUR events, or None if the feed can't
    be trusted — a dead feed must never read as a quiet calendar."""
    rows = None
    for attempt in range(3):
        try:
            r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                             timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            rows = r.json()
            break
        except Exception as e:
            print(f"(calendar feed unavailable: {str(e)[:60]})")
            if attempt < 2:
                time.sleep(20)
    if not rows:
        return None
    out, stamps = [], []
    for ev in rows:
        try:
            t = datetime.fromisoformat(ev["date"]).astimezone(UK)
        except Exception:
            continue
        stamps.append(t.date())
        if ev.get("impact") in ("High", "Medium") \
                and ev.get("country") in ("USD", "GBP", "EUR"):
            out.append((t, ev.get("impact"), ev.get("country"), ev.get("title")))
    now = datetime.now(UK)
    if now.weekday() < 5 and not (stamps and min(stamps) <= now.date() <= max(stamps)):
        print("(calendar feed doesn't cover today)")
        return None
    return sorted(out)


def clock(t):
    """An event's UK time. The feed gives events with no set time, like elections,
    an odd placeholder minute, so those don't get a false exact time."""
    return f"{t:%H:%M}" if t.minute % 5 == 0 else "no set time"


def ping_uk(now):
    """The gold ping's time on the UK clock: 10:05 New York, which moves when the
    two countries change their clocks on different dates."""
    return now.astimezone(NY).replace(hour=10, minute=5).astimezone(UK)


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


def vix_card(gauges):
    """Fear gauges card, rendered from read_gauges()."""
    rows = ""
    for code, v in gauges.items():
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


def session_over(symbol, now):
    """Has today's daily bar finished? FTSE at its 16:35 close, Bitcoin only at
    UTC midnight, everything else at the 17:00 New York futures break."""
    if symbol == "BTC-USD":
        return False
    if symbol == "^FTSE":
        return (now.hour, now.minute) >= (16, 35)
    return now.astimezone(NY).hour >= 17


def finished_through(symbol, now):
    """The latest date whose daily bar has finished for this market."""
    return now.date() if session_over(symbol, now) else now.date() - timedelta(days=1)


def wilder_rsi(close, n=14):
    """RSI the way TradingView's ta.rsi computes it, so the board matches the chart."""
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def read_market(symbol):
    df = yf.download(symbol, period="200d", interval="1d", progress=False,
                     auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    return read_bars(df.dropna(subset=["close"]), symbol, datetime.now(UK))


def read_bars(df, symbol, now):
    c = df["close"]
    # Live readings include today's forming bar, as a chart does.
    rsi = float(wilder_rsi(c).iloc[-1])
    hi20, lo20 = float(df["high"].iloc[-20:].max()), float(df["low"].iloc[-20:].min())
    pos = (float(c.iloc[-1]) - lo20) / max(hi20 - lo20, 1e-9) * 100
    last = float(c.iloc[-1])
    # Today's bar is still forming (futures start it the evening before), so
    # every reading about the last session comes from the bars before today.
    dates = df.index.date
    done = df[dates < now.date()]
    volx = _range_ratio(done)
    c1, c6 = float(done["close"].iloc[-1]), float(done["close"].iloc[-6])
    trend = 1 if c1 > c6 else -1 if c1 < c6 else 0
    # The next session's setup takes in today's bar once its session is over.
    fin = df[dates <= finished_through(symbol, now)]
    fin_last, fin_c5 = float(fin["close"].iloc[-1]), float(fin["close"].iloc[-6])
    nxt = 1 if fin_last > fin_c5 else -1 if fin_last < fin_c5 else 0
    return dict(sym=symbol, src=SOURCES.get(symbol, symbol), rsi=rsi, volx=volx,
                nxtx=_range_ratio(fin), live=volx > 1.0, trend=trend, pos=pos,
                c1=c1, c6=c6, last=last, nxt=nxt, base=fin_last,
                asof=done.index[-1].date(), fin_asof=fin.index[-1].date(),
                pdh=float(done["high"].iloc[-1]), pdl=float(done["low"].iloc[-1]))


def _range_ratio(bars):
    """The last bar's high-low range against the median of the 20 bars before it."""
    rng = bars["high"] - bars["low"]
    return float(rng.iloc[-1]) / max(float(rng.iloc[-21:-1].median()), 1e-9)


def gold_gate(now):
    """The gold ping's own gate, replayed on its own feed so the board can't
    contradict it. None if the feed can't be read."""
    try:
        import dukascopy_python as dk
        import dukascopy_python.instruments as ins
        end = datetime.now(UK).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        df = dk.fetch(ins.INSTRUMENT_FX_METALS_XAU_USD, dk.INTERVAL_MIN_5,
                      dk.OFFER_SIDE_BID, start=end - timedelta(days=45), end=end)
        df.index = (df.index.tz_localize("UTC") if df.index.tz is None else df.index
                    ).tz_convert("America/New_York")
        df = df.rename(columns=str.lower).dropna(subset=["open", "high", "low", "close"])
        return read_gate(df, now)
    except Exception as e:
        print(f"(gold gate data unavailable: {str(e)[:60]})")
        return None


def read_gate(df, now):
    """Frozen rules, as in cloud_alert.py and gold_paper.py: the last NY session's
    range against the median of the last 20, and the 5-session side. The side's
    series counts Sunday's evening open as a session, as the system was tested."""
    day = now.date()
    while day.weekday() >= 5:
        day += timedelta(days=1)
    mins = df.index.hour * 60 + df.index.minute
    rth = df[(mins >= 570) & (mins <= 955)]
    rngs = [(d, float(g["high"].max() - g["low"].min()))
            for d, g in rth.groupby(rth.index.date) if d < day and len(g) >= 60]
    if len(rngs) < 12:
        return None
    rngs = rngs[-20:]
    session, prior = rngs[-1]
    med = float(np.median([r for _, r in rngs]))
    closes = df["close"].resample("1D").last().dropna()
    closes = closes[closes.index.date < day]
    # the spot bar a CFD chart shows: 17:00 to 17:00 New York
    keys = (df.index + pd.Timedelta(hours=7)).date
    spot_day = max(k for k in set(keys) if k < day)
    spot = df[keys == spot_day]
    return dict(open=prior > med, prior=prior, med=med, session=session,
                side=1 if closes.iloc[-1] > closes.iloc[-6] else -1,
                spot_day=spot_day, spot_hi=float(spot["high"].max()),
                spot_lo=float(spot["low"].min()), spot_c=float(spot["close"].iloc[-1]))


def data_check(cards, fans, gauges, fg, cal_ok, gate, now):
    """Everything that could make the page wrong without it looking wrong."""
    out = []
    if not cal_ok:
        out.append("Calendar feed unavailable: today's events are UNKNOWN, not clear. "
                   "Check forexfactory.com.")
    seen = {n for n, _, _ in cards}
    for _, name, _ in MARKETS:
        if name not in seen:
            out.append(f"{name}: no price data, so its card is missing.")
    for name, m, _ in cards:
        expect = now.date() - timedelta(days=1)
        while m["sym"] != "BTC-USD" and expect.weekday() >= 5:
            expect -= timedelta(days=1)
        if m["asof"] != expect:
            out.append(f"{name}: latest finished session is {m['asof']:%a %d %b}, "
                       f"expected {expect:%a %d %b}. Market holiday or a data gap.")
        if not m["pdl"] <= m["c1"] <= m["pdh"]:
            out.append(f"{name}: close {m['c1']:,.1f} is outside its own high and low.")
        if not 0 <= m["rsi"] <= 100:
            out.append(f"{name}: RSI reads {m['rsi']:.0f}, which is impossible.")
        if not m["volx"] > 0.15:
            out.append(f"{name}: last session's range is only {m['volx']:.2f}× normal. "
                       "It may be an unfinished bar.")
        if abs(m["last"] / m["c1"] - 1) > 0.15:
            out.append(f"{name}: price now is over 15% from the last close. "
                       "Check the feed before trusting this card.")
        fan = fans.get(name)
        if not fan:
            out.append(f"{name}: no analogue reading, so no probable territory.")
        elif fan["asof"] != m["fin_asof"]:
            out.append(f"{name}: territory built from {fan['asof']:%a %d %b}, card "
                       f"from {m['fin_asof']:%a %d %b}.")
        if name == "GOLD" and gate and gate["spot_day"] == m["asof"]:
            fut, spot = m["pdh"] - m["pdl"], gate["spot_hi"] - gate["spot_lo"]
            if not 1 / 1.6 < fut / max(spot, 1e-9) < 1.6:
                out.append(f"GOLD: futures range {fut:,.1f} and spot range {spot:,.1f} "
                           "disagree for the same session.")
    for code in ("VIX", "VXN", "GVZ"):
        if code not in gauges:
            out.append(f"{code}: no data, so its fear gauge is missing.")
    if not fg:
        out.append("Fear & Greed: no data, so its dial is missing.")
    if not gate:
        out.append("Gold gate: no data, so gold's state is UNKNOWN. The ping still decides.")
    return out


def self_test():
    """Offline proof, on made-up bars, that the rules behind the readings still
    hold. Runs on every build; a failure goes on the page and in the ping."""
    fails = []

    def check(name, ok):
        if not ok:
            fails.append(f"Self-test failed: {name}.")

    idx = pd.bdate_range(end="2026-10-30", periods=40)
    bars = pd.DataFrame({"high": 110.0, "low": 100.0,
                         "close": np.linspace(101.0, 109.0, 40)}, index=idx)
    bars.loc[idx[-1], ["high", "low", "close"]] = [130.0, 100.0, 120.0]
    forming = pd.DataFrame({"high": [121.0], "low": [119.0], "close": [120.5]},
                           index=[pd.Timestamp("2026-11-02")])
    next_day = pd.DataFrame({"high": [123.0], "low": [122.0], "close": [122.5]},
                            index=[pd.Timestamp("2026-11-03")])
    morning = datetime(2026, 11, 2, 7, 0, tzinfo=UK)
    evening = datetime(2026, 11, 2, 23, 30, tzinfo=UK)
    for label, df, sym in (("unfinished bar present", pd.concat([bars, forming]), "GC=F"),
                           ("no bar yet today", bars, "^FTSE")):
        m = read_bars(df, sym, morning)
        check(f"{label}: range must come from the last finished session",
              abs(m["volx"] - 3.0) < 1e-6)
        check(f"{label}: levels must be the last finished session's",
              (m["pdh"], m["pdl"], m["c1"]) == (130.0, 100.0, 120.0))
        check(f"{label}: side must compare finished closes", m["trend"] == 1)
        check(f"{label}: session date must be Friday's", str(m["asof"]) == "2026-10-30")
        check(f"{label}: territory must start from the finished close", m["base"] == 120.0)
    m = read_bars(pd.concat([bars, forming]), "GC=F", morning)
    check("price now must come from the forming bar", m["last"] == 120.5)
    m = read_bars(pd.concat([bars, forming, next_day]), "GC=F", evening)
    check("after the close, the board must still read yesterday", abs(m["volx"] - 3.0) < 1e-6)
    check("after the close, the next session must read today", str(m["fin_asof"]) == "2026-11-02")
    check("a bar dated tomorrow must never count as finished", abs(m["nxtx"] - 0.2) < 1e-6)
    check("Bitcoin's day must not end at the futures break",
          not session_over("BTC-USD", evening))
    climb = list(np.arange(100.0, 130.0)) + list(np.arange(110.0, 130.0))
    check("RSI must be Wilder's, which still remembers a drop 20 bars back",
          float(wilder_rsi(pd.Series(climb)).iloc[-1]) < 99)
    check("a placeholder minute must not show as an exact time",
          clock(datetime(2026, 11, 3, 15, 16, tzinfo=UK)) == "no set time"
          and clock(datetime(2026, 11, 3, 15, 0, tzinfo=UK)) == "15:00")
    check("the ping must follow New York's clock",
          f"{ping_uk(datetime(2026, 11, 2, 7, 0, tzinfo=UK)):%H:%M}" == "15:05"
          and f"{ping_uk(datetime(2026, 3, 16, 7, 0, tzinfo=UK)):%H:%M}" == "14:05")
    try:
        from analogue_engine import fan_from
        n = 1700
        steps = np.random.default_rng(7).normal(0, 1, n)
        close = 1000 + np.cumsum(steps)
        long_idx = pd.bdate_range(end="2026-11-02", periods=n)
        long_bars = pd.DataFrame({"close": close, "high": close + 2, "low": close - 2},
                                 index=long_idx)
        check("analogue fan with an unfinished bar must read the last finished session",
              str(fan_from(long_bars, "T", morning.date() - timedelta(days=1))["asof"]) == "2026-10-30")
        check("analogue fan with no bar yet today must read the last finished session",
              str(fan_from(long_bars.iloc[:-1], "T", morning.date() - timedelta(days=1))["asof"]) == "2026-10-30")
    except Exception as e:
        fails.append(f"Self-test failed: analogue fan couldn't run ({str(e)[:60]}).")
    try:
        ny = pd.date_range("2026-09-14 00:00", "2026-11-02 11:00", freq="5min", tz="America/New_York")
        ny = ny[ny.weekday < 5]
        px = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=ny)
        friday = ny.date == pd.Timestamp("2026-10-30").date()
        px.loc[friday, ["high", "low"]] = [111.0, 99.0]
        monday = ny.date == pd.Timestamp("2026-11-02").date()
        px.loc[monday, ["high", "low"]] = [500.0, 1.0]
        g = read_gate(px, morning)
        check("gold gate must read the last finished NY session",
              str(g["session"]) == "2026-10-30" and abs(g["prior"] - 12.0) < 1e-6)
        check("gold gate must compare it with the median of the last 20", abs(g["med"] - 2.0) < 1e-6)
        check("gold gate must be open on a range above its median", g["open"])
    except Exception as e:
        fails.append(f"Self-test failed: gold gate couldn't run ({str(e)[:60]}).")
    bad = dict(sym="GC=F", asof=morning.date(), pdl=1.0, pdh=2.0, c1=5.0, rsi=140.0,
               volx=0.05, last=9.0, fin_asof=morning.date())
    caught = data_check([("GOLD", bad, [])], {}, {}, None, False, None, morning)
    check("the data check must catch bad readings", len(caught) >= 10)
    return fails


def check_html(problems):
    """The data check's verdict, first thing on the page."""
    if not problems:
        return ("<div class='check ok'>Data check passed: every session reading below "
                "comes from a finished session, and each card shows its date.</div>")
    rows = "".join(f"<li>{p}</li>" for p in problems)
    return (f"<div class='check bad'><b>DATA CHECK: {len(problems)} problem(s). "
            f"Don't rely on the readings named here.</b><ul>{rows}</ul></div>")


def reasons(m):
    r = []
    if m["trend"] > 0:
        r.append(f"LONG side only — {m['asof']:%a}'s close {m['c1']:,.1f} sits above the "
                 f"close five sessions back ({m['c6']:,.1f}); counter-trend trades "
                 f"tested as the losing side on every market.")
    elif m["trend"] < 0:
        r.append(f"SHORT side only — {m['asof']:%a}'s close {m['c1']:,.1f} sits below the "
                 f"close five sessions back ({m['c6']:,.1f}).")
    else:
        r.append("No side — the 5-day trend is flat; no permission either way.")
    r.append((f"LIVE day — {m['asof']:%a %d %b} ranged {m['volx']:.2f}× its 20-day median; "
              "movement begets movement.")
             if m["live"] else
             (f"Quiet day — {m['asof']:%a %d %b} ranged only {m['volx']:.2f}× its 20-day "
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
    rows = "".join(
        f"<div class='ev'><span class='t'>{v:5.0f}</span><span>{n}</span>"
        f"<span class='cur'>{'greed side' if v >= 55 else 'fear side' if v <= 45 else 'neutral'}</span></div>"
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


def next_session(cards, nxt_ev, now, cal_ok):
    """The standing setup for the next session: permission side + energy lean
    from the latest completed daily bar, plus what's scheduled. Direction
    stays unknowable — this is the setup, not the outcome."""
    rows = ""
    for name, m, _ in cards:
        side = ("LONG side" if m["nxt"] > 0 else
                "SHORT side" if m["nxt"] < 0 else "no side")
        scls = "live" if m["nxt"] > 0 else "news" if m["nxt"] < 0 else "quiet"
        lean = "likely LIVE" if m["nxtx"] > 1.0 else "leaning quiet"
        rows += (f"<div class='ev'><span class='cur'>{name}</span>"
                 f"<span class='chip {scls}'>{side}</span>"
                 f"<span>{lean} ({m['fin_asof']:%a %d %b}: {m['nxtx']:.2f}× median)</span></div>")
    empty = ("Calendar unavailable, so tomorrow's events are UNKNOWN." if not cal_ok else
             "Tomorrow is the weekend. Monday's events aren't in this week's calendar yet."
             if now.weekday() >= 4 else "Nothing medium/high-impact scheduled.")
    erows = "".join(f"<div class='ev'><span class='t'>{clock(t)}</span>"
                    f"<span class='imp {imp.lower()}'>{imp}</span>"
                    f"<span class='cur'>{cur}</span><span>{ti}</span></div>"
                    for t, imp, cur, ti in nxt_ev) or \
        f"<div class='ev none'>{empty}</div>"
    return (f"<h3 class='section-h'>Next session — the standing setup</h3>"
            f"<div class='timeline'>{rows}"
            f"<h4 class='wk'>Scheduled for tomorrow</h4>{erows}"
            f"<div class='ev none'>Computed from the latest completed session — "
            f"permission and energy, never direction.</div></div>")


def attention(m, evs):
    """0-100 attention score from the validated ingredients + reason parts."""
    parts = []
    s = min(m["volx"], 2.0) / 2.0 * 40 if not pd.isna(m["volx"]) else 20
    if not pd.isna(m["volx"]):
        parts.append(f"{m['asof']:%a} {m['volx']:.2f}x range")
    if m["trend"] != 0:
        s += 20
        parts.append(("long" if m["trend"] > 0 else "short") + " side permitted")
    else:
        parts.append("no side permitted")
    his = [t for t, imp, _ in evs if imp == "High"]
    if his:
        s += 25
        parts.append(f"high-impact news {clock(min(his))} UK")
    if m["rsi"] >= 70 or m["rsi"] <= 30:
        s += 15
        parts.append("stretched — violence risk")
    s = min(round(s), 100)
    label = "PRIME" if s >= 65 else "WORTH WATCHING" if s >= 45 else "LOW INTEREST"
    return s, label, " · ".join(parts)


def ranking_html(cards):
    scored = sorted(((attention(m, evs), n) for n, m, evs in cards),
                    key=lambda x: -x[0][0])
    rows = ""
    for i, ((s, lab, why), n) in enumerate(scored, 1):
        cls = "live" if lab == "PRIME" else "newslo" if lab == "WORTH WATCHING" else "quiet"
        rows += (f"<div class='ev'><span class='t'>{i}.</span>"
                 f"<span class='cur'>{n}</span><span class='chip {cls}'>{lab} {s}</span>"
                 f"<span>{why}</span></div>")
    rows += ("<div class='ev none'>Attention ranking — where movement conditions "
             "concentrate today. Not a promise of profit or direction.</div>")
    return (f"<h3 class='section-h' style='margin-top:0'>Where attention pays today</h3>"
            f"<div class='timeline'>{rows}</div>")


FAN_PAIRS = [("GC=F", "GOLD"), ("^GSPC", "S&P 500"), ("^NDX", "NASDAQ 100"),
             ("^FTSE", "FTSE 100"), ("BTC-USD", "BITCOIN"), ("DX-Y.NYB", "DOLLAR")]


def compute_fans(now):
    """One pass of the analogue engine for all markets — shared by cards + section."""
    try:
        from analogue_engine import today_fan
    except Exception:
        return {}
    fans = {}
    for sym, nm in FAN_PAIRS:
        try:
            f = today_fan(sym, nm, finished_through(sym, now))
            if f:
                fans[nm] = f
        except Exception as e:
            print(f"  {nm:10} analogue reading failed ({str(e)[:40]})")
    return fans


def _px(v):
    return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}"


def analogue_html(fans):
    """DAYS LIKE TODAY — the analogue engine's live fans with calibration stamps."""
    rows = ""
    for _, nm in FAN_PAIRS:
        fan = fans.get(nm)
        if not fan:
            continue
        warn = "UNRELIABLE" in fan["note"] or "WORSE" in fan["note"]
        rows += (f"<div class='ev'><span class='cur'>{nm}</span>"
                 f"<span>From {fan['asof']:%a %d %b}: {fan['up']:.0f}% of its 150 lookalike days closed up next day · "
                 f"median <b>{fan['med']:+.2f}%</b> · typical band <b>{fan['lo']:+.2f}%</b> to "
                 f"<b>{fan['hi']:+.2f}%</b></span>"
                 f"<span class='chip {'warn' if warn else 'live'}'>{fan['note']}</span></div>")
    if not rows:
        return ""
    rows += ("<div class='ev none'>Each market's 150 most similar historical days (same trend, "
             "energy, stretch, momentum fingerprint) and what the NEXT day did after them — a "
             "probability fan that rebuilds daily, walk-forward calibrated 4 Oct 2026. It describes "
             "the shape of tomorrow, never the side: direction skill measured ~52% even on "
             "confident reads.</div>")
    return (f"<h3 class='section-h'>Days like today — the analogue engine</h3>"
            f"<div class='timeline'>{rows}</div>")


def funnel_html(events, cards, now, cal_ok):
    """The pre-session process of elimination: what's done, what's yours."""
    n_high = sum(1 for _, imp, _, _ in events if imp == "High")
    live = sum(1 for _, m, _ in cards if m["live"])
    sided = sum(1 for _, m, _ in cards if m["trend"] != 0)
    news = (f"News boxed off — {n_high} high-impact event(s) timed above; no fresh entries into them"
            if cal_ok else "News UNKNOWN — the calendar feed is down; check forexfactory.com")
    rows = [
        ("1", "auto", news),
        ("2", "auto", f"Energy read — {live} of {len(cards)} markets live; dead days pre-eliminated"),
        ("3", "auto", f"Markets ranked — attention list above; {sided} of {len(cards)} carry a permitted side"),
        ("4", "auto", "Levels marked — the last session's high / close / low on every card; reference, not signals"),
        ("5", "auto", f"Playbook fixed — only the {ping_uk(now):%H:%M} label is a trade; the ping declares the day"),
        ("6", "YOU", "Risk pre-commitment — paper stage: no money moves; when it does, the limits are written BEFORE the open"),
        ("7", "YOU", "The mirror — slept, calm, undistracted? If not, today's edge is negative regardless of the chart"),
    ]
    body = "".join(
        f"<div class='ev'><span class='t'>{n}.</span>"
        f"<span class='chip {'live' if tag == 'auto' else 'warn'}'>{tag.upper()}</span>"
        f"<span>{txt}</span></div>" for n, tag, txt in rows)
    return (f"<h3 class='section-h'>The morning funnel — process of elimination</h3>"
            f"<div class='timeline'>{body}</div>")


def gold_state_html(gate, now):
    """Gold's state from the ping's own gate, so the board can't contradict it."""
    at = f"{ping_uk(now):%H:%M}"
    if not gate:
        return (f"<div class='state off'>STATE: UNKNOWN — couldn't read the gate's data; "
                f"the {at} ping decides</div>")
    side = "LONG" if gate["side"] > 0 else "SHORT"
    nums = (f"{gate['session']:%a}'s New York session {gate['prior']:.1f} "
            f"vs 20-session median {gate['med']:.1f}")
    if gate["open"]:
        return (f"<div class='state on'>STATE: ARMED, {side} side — {nums}; "
                f"the {at} ping decides</div>")
    return f"<div class='state off'>STATE: DEAD — {nums}; gate shut, no {at} trade today</div>"


def html_report(cards, events, ahead, nxt_ev, now, path, fans=None, fg=None,
                gauges=None, cal_ok=True, problems=()):
    days = {}
    for t, imp, cur, title in ahead:
        days.setdefault(t.date(), []).append((t, cur, title))
    ahead_html = "".join(
        f"<h4 class='wk'>{d:%A %d %B}</h4>" +
        "".join(f"<div class='ev'><span class='t'>{clock(t)}</span>"
                f"<span class='cur'>{cur}</span><span>{ti}</span></div>"
                for t, cur, ti in days[d])
        for d in sorted(days)) or (
        "<div class='ev none'>No further high-impact USD/GBP/EUR events this week.</div>"
        if cal_ok else "<div class='ev none'>Calendar unavailable, so this week's events are UNKNOWN.</div>")

    ev_rows = "".join(
        f"<div class='ev'><span class='t'>{clock(t)}</span>"
        f"<span class='imp {imp.lower()}'>{imp}</span>"
        f"<span class='cur'>{cur}</span><span>{title}</span></div>"
        for t, imp, cur, title in events) or (
        "<div class='ev none'>No medium/high-impact USD, GBP or EUR events scheduled today.</div>"
        if cal_ok else "<div class='ev none'>Calendar unavailable, so today's events are UNKNOWN. Check forexfactory.com.</div>")

    card_html = ""
    for name, m, evs in cards:
        state_html = gold_state_html(m.get("gate"), now) if name == "GOLD" else ""
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
            chips += f"<span class='chip news'>HIGH-IMPACT NEWS {clock(min(his))}</span>"
        elif evs:
            chips += f"<span class='chip newslo'>{len(evs)} medium event(s)</span>"
        nrows = "".join(f"<div class='ev'><span class='t'>{clock(t)}</span>"
                        f"<span class='imp {imp.lower()}'>{imp}</span><span>{ti}</span></div>"
                        for t, imp, ti in evs)
        why = "".join(f"<li>{x}</li>" for x in reasons(m))
        rsi_word = ("OVERBOUGHT — crowded high" if m["rsi"] >= 70
                    else "OVERSOLD — crowded low" if m["rsi"] <= 30 else "neutral")
        rz = ("os" if m["rsi"] <= 30 else "ob" if m["rsi"] >= 70 else "mid")
        pos_word = ("AT THE CEILING — breakout territory" if m["pos"] >= 90
                    else "AT THE FLOOR — breakdown territory" if m["pos"] <= 10
                    else "upper half" if m["pos"] >= 50 else "lower half")
        pz = ("lo" if m["pos"] <= 10 else "hi" if m["pos"] >= 90 else "mid")
        vol_word = ("LIVELY — movement tends to continue" if m["volx"] > 1.0
                    else "quiet — edges fade on days like this")
        fan = (fans or {}).get(name)
        terr = ""
        if fan:
            # the fan is close-to-close, so it starts from the finished close
            lo_p = m["base"] * (1 + fan["lo"] / 100)
            md_p = m["base"] * (1 + fan["med"] / 100)
            hi_p = m["base"] * (1 + fan["hi"] / 100)
            span = max(hi_p - lo_p, 1e-9)
            p_now = min(max((m["last"] - lo_p) / span * 100, 2), 98)
            p_mid = min(max((md_p - lo_p) / span * 100, 2), 98)
            wide = "UNRELIABLE" in fan["note"]
            wnote = " · GOLD WARNING: runs hotter than its lookalikes — treat this band as wider (dashed)" if wide else ""
            terr = (f"<div class='terr'><label>Next session's probable territory, from "
                    f"{m['fin_asof']:%a}'s close {_px(m['base'])} · "
                    f"<b>{fan['up']:.0f}%</b> of its 150 lookalike days closed higher{wnote}</label>"
                    f"<div class='ttrack{' wide' if wide else ''}'>"
                    f"<i class='now' style='left:{p_now:.0f}%'></i>"
                    f"<i class='mid' style='left:{p_mid:.0f}%'></i></div>"
                    f"<div class='tlabels'><span>{_px(lo_p)}</span>"
                    f"<span class='c'>centre {_px(md_p)}</span><span>{_px(hi_p)}</span></div>"
                    f"<div class='tnote'>white tick = price now · gold tick = centre of the "
                    f"lookalikes · a territory, never a target — the side stays ~a coin flip</div></div>")
        gate = m.get("gate") if name == "GOLD" else None
        spot_html = (f"<div class='volx'>Spot XAU/USD, {gate['spot_day']:%a %d %b} (closer to a CFD chart): "
                     f"high <b>{gate['spot_hi']:,.1f}</b> · close <b>{gate['spot_c']:,.1f}</b> · "
                     f"low <b>{gate['spot_lo']:,.1f}</b></div>") if gate else ""
        card_html += f"""
    <section class='card'>
      <header><h2>{name}</h2><span class='bias {bcls}'>{bias}</span></header>
      {state_html}
      <div class='chips'>{chips}</div>
      <div class='gauge'><label>RSI14 now · <b>{m['rsi']:.0f}</b> — {rsi_word}</label>
        <div class='track rsi'><i style='left:{min(max(m['rsi'],0),100):.0f}%'></i></div>
        <div class='zones'><span class='{'on' if rz == 'os' else ''}'>oversold</span>
        <span class='{'on' if rz == 'mid' else ''}'>neutral</span>
        <span class='{'on' if rz == 'ob' else ''}'>overbought</span></div></div>
      <div class='gauge'><label>20-day range position now · <b>{m['pos']:.0f}%</b> — {pos_word}</label>
        <div class='track'><i style='left:{min(max(m['pos'],0),100):.0f}%'></i></div>
        <div class='zones'><span class='{'on' if pz == 'lo' else ''}'>floor</span>
        <span class='{'on' if pz == 'mid' else ''}'>middle of its range</span>
        <span class='{'on' if pz == 'hi' else ''}'>ceiling</span></div></div>
      <div class='volx'>{m['asof']:%a %d %b} range: <b>{m['volx']:.2f}×</b> its 20-day median — {vol_word}</div>
      {terr}
      <div class='volx'>Levels, {m['asof']:%a %d %b} ({m['src']}): high <b>{m['pdh']:,.1f}</b> · close <b>{m['c1']:,.1f}</b> · low <b>{m['pdl']:,.1f}</b> — reference, not signals</div>
      {spot_html}
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
  .gauge label b {{ color:var(--text); }}
  .zones {{ display:flex; justify-content:space-between; font:500 9px var(--mono);
           color:#5a6886; margin-top:3px; letter-spacing:.02em; }}
  .zones .on {{ color:var(--gold); font-weight:700; }}
  .terr {{ margin:12px 0 4px; }}
  .terr label {{ font:500 11px var(--mono); color:var(--mut); }}
  .ttrack {{ position:relative; height:10px; border-radius:5px; margin-top:5px;
            background:linear-gradient(90deg, rgba(242,89,79,.45), rgba(139,150,173,.22) 50%, rgba(47,214,164,.45)); }}
  .ttrack.wide {{ outline:1px dashed rgba(226,180,81,.65); outline-offset:2px; }}
  .ttrack i {{ position:absolute; top:-3px; width:3px; height:16px; border-radius:2px;
              transform:translateX(-50%); }}
  .ttrack i.now {{ background:#fff; }}
  .ttrack i.mid {{ background:var(--gold); }}
  .tlabels {{ display:flex; justify-content:space-between; font:500 10px var(--mono);
             color:var(--mut); margin-top:4px; }}
  .tlabels .c {{ color:var(--gold); }}
  .tnote {{ font-size:11px; color:#5a6886; margin-top:3px; }}
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
  .check {{ border-radius:8px; padding:9px 14px; margin:0 0 18px; font-size:13px; }}
  .check.ok {{ background:rgba(47,214,164,.09); color:var(--up); }}
  .check.bad {{ background:rgba(242,89,79,.16); color:#ffb4ae; border:1px solid var(--dn); }}
  .check ul {{ margin:6px 0 0; padding-left:18px; }}
  .wk {{ margin:12px 0 2px; color:var(--gold); font:600 12px var(--mono); }}
  .timeline {{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:12px 18px; }}
  footer {{ margin-top:30px; border-top:1px solid var(--line); padding-top:12px;
           color:var(--mut); font-size:12px; }}
  footer a {{ color:#8fb2e8; }}
</style>
<div class="wrap">
  <h1>Daily Bias Board</h1>
  <div class="sub">{now:%A %d %B %Y · generated %H:%M UK}</div>
{check_html(problems)}
{ranking_html(cards)}
  <h3 class="section-h">The markets in detail</h3>
  <div class="grid">{card_html}
{fg_card(fg)}
{vix_card(gauges or {})}
  </div>
  <h3 class="section-h">Today's schedule — when volatility may arrive</h3>
  <div class="timeline">{ev_rows}</div>
{analogue_html(fans or {})}
{funnel_html(events, cards, now, cal_ok)}
{next_session(cards, nxt_ev, now, cal_ok)}
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


def brief_already_sent() -> bool:
    """True if a morning brief already reached the channel in the last 10h."""
    try:
        r = requests.get(f"https://ntfy.sh/{TOPIC}/json?poll=1&since=10h", timeout=20)
        return "Morning market brief" in r.text
    except Exception:
        return False


def ping_summary(cards, fg, events, cal_ok, problems):
    """Telegraphic facts to the phone; tap-through opens the full board."""
    longs = sum(1 for _, m, _ in cards if m["trend"] > 0)
    shorts = sum(1 for _, m, _ in cards if m["trend"] < 0)
    live = [n for n, m, _ in cards if m["live"]]
    stretched = [n for n, m, _ in cards if m["rsi"] >= 70 or m["rsi"] <= 30]
    gold = next((m for n, m, _ in cards if n == "GOLD"), None)
    top = sorted(((attention(m, e)[0], n) for n, m, e in cards), key=lambda x: -x[0])[:2]
    bits = ["watch: " + ", ".join(f"{n} ({s})" for s, n in top),
            f"{longs} long-side / {shorts} short-side",
            "LIVE: " + (", ".join(live) if live else "none"),
            "stretched: " + (", ".join(stretched) if stretched else "none")]
    if fg:
        bits.append(f"F&G {fg['idx']:.0f} {fg['label']}")
    if gold:
        gate = gold.get("gate")
        bits.append("gold: " + ("UNKNOWN" if not gate else "DEAD" if not gate["open"]
                                else "ARMED " + ("long" if gate["side"] > 0 else "short")))
    his = [(t, ti) for t, imp, cur, ti in events if imp == "High"]
    bits.append("high-impact: " + ("UNKNOWN, calendar down" if not cal_ok else
                                   ", ".join(f"{clock(t)} {ti}" for t, ti in his[:2])
                                   if his else "none"))
    msg = " | ".join(bits)
    if problems:
        msg = f"DATA CHECK: {len(problems)} problem(s), see page | " + msg
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
    forced = os.environ.get("FORCE") == "1"
    if not forced and now.weekday() >= 5:
        print("weekend - nothing to do")
        return
    print(f"MARKET CONTEXT — {now:%A %d %b %Y, %H:%M} UK\n")
    allev = fetch_events()
    cal_ok = allev is not None
    allev = allev or []
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
    fans = compute_fans(now)
    gate = gold_gate(now)
    for name, m, _ in cards:
        if name == "GOLD":
            m["gate"] = gate
    fg, gauges = fear_greed(), read_gauges()
    problems = data_check(cards, fans, gauges, fg, cal_ok, gate, now) + self_test()
    for p in problems:
        print(f"  DATA CHECK: {p}")
    html_report(cards, events, ahead, nxt_ev, now, path, fans=fans, fg=fg,
                gauges=gauges, cal_ok=cal_ok, problems=problems)
    print(f"\ndashboard written: {path}")
    if not forced and now.hour < 6:
        print(f"{now:%H:%M} UK - page refreshed; too early to ping")
    elif brief_already_sent():
        # unconditional: even a forced/dispatched run never double-pings
        print("page refreshed; brief already on the channel today - no ping")
    else:
        ping_summary(cards, fg, events, cal_ok, problems)



if __name__ == "__main__":
    main()
