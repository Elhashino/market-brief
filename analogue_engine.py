"""THE ANALOGUE ENGINE — "days like today", calibrated or killed (pre-registered).

The honest form of "what will the world do": for each index, each day, find the
K most similar historical days (same regime fingerprint) and report the
DISTRIBUTION of what happened next. Never a direction call — a probability fan
that rebuilds daily as the world changes (yesterday joins the library tonight).

Fingerprint per day t (all computed from completed data only):
  trend sign (close[t-1] vs close[t-6]) · vol ratio (range_t vs 20d median) ·
  20d range position · RSI14 · yesterday's return · 5-day return
Analogues: K=150 nearest (z-scored euclidean) among days at least 1 year old
at the time (walk-forward by construction — a test day only sees its past).

CALIBRATION BENCH (the pass line, declared now), on the last ~500 days/index:
  COVERAGE  — realized next-day return falls inside the analogues' 10th-90th
              percentile band. Ideal 80%; PASS band 72-88%.
  MAGNITUDE — corr(analogue band width, realized |return|) > 0 (energy skill).
  DIRECTION — reported honestly, expected ~none (measured 50.1% before).
A market whose coverage misses the band is reported as uncalibrated there.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

K = 150
TEST_DAYS = 500
MARKETS = [("GC=F", "GOLD"), ("^GSPC", "S&P 500"), ("^NDX", "NASDAQ 100"),
           ("^FTSE", "FTSE 100"), ("BTC-USD", "BITCOIN"), ("DX-Y.NYB", "DOLLAR")]


def features(df):
    c = df["close"]
    rng = df["high"] - df["low"]
    f = pd.DataFrame(index=df.index)
    f["trend"] = (c.shift(1) > c.shift(6)).astype(float)
    f["volx"] = (rng / rng.rolling(20).median().shift(1)).clip(0, 4)
    hi20 = df["high"].rolling(20).max()
    lo20 = df["low"].rolling(20).min()
    f["rpos"] = ((c - lo20) / (hi20 - lo20)).clip(0, 1)
    delta = c.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    dn = (-delta.clip(upper=0)).rolling(14).mean()
    f["rsi"] = (100 - 100 / (1 + up / dn)) / 100
    f["ret1"] = c.pct_change().clip(-0.1, 0.1)
    f["ret5"] = c.pct_change(5).clip(-0.2, 0.2)
    f["next"] = c.pct_change().shift(-1)          # tomorrow's return (the outcome)
    return f.dropna()


def run(symbol, name):
    df = yf.download(symbol, period="max", interval="1d", progress=False,
                     auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["close"])
    f = features(df)
    if len(f) < 1500:
        print(f"{name:10} not enough history ({len(f)} days)")
        return
    X = f[["trend", "volx", "rpos", "rsi", "ret1", "ret5"]].to_numpy()
    y = f["next"].to_numpy()
    mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
    Z = (X - mu) / sd

    n = len(f)
    test_idx = range(max(300, n - TEST_DAYS), n)
    cover = dirs = dir_n = 0
    widths, mags = [], []
    for t in test_idx:
        pool = Z[: t - 252]                        # only days >= 1 year older
        if len(pool) < K + 50:
            continue
        d = np.linalg.norm(pool - Z[t], axis=1)
        nb = np.argpartition(d, K)[:K]
        out = y[nb]
        lo, hi = np.percentile(out, [10, 90])
        cover += 1 if lo <= y[t] <= hi else 0
        widths.append(hi - lo)
        mags.append(abs(y[t]))
        upfrac = (out > 0).mean()
        if upfrac >= 0.60 or upfrac <= 0.40:
            dir_n += 1
            dirs += 1 if ((y[t] > 0) == (upfrac >= 0.60)) else 0
    nt = len(widths)
    cov = cover / nt * 100
    mag_corr = float(np.corrcoef(widths, mags)[0, 1])
    dir_line = (f"{dirs / dir_n * 100:4.1f}% on {dir_n} confident days"
                if dir_n >= 30 else f"too few confident days ({dir_n})")
    ok = 72 <= cov <= 88
    print(f"{name:10} | coverage {cov:5.1f}% (ideal 80) {'PASS' if ok else 'MISS'} "
          f"| magnitude corr {mag_corr:+.2f} | direction: {dir_line}")

    # today's live fan (the product, if calibrated)
    pool = Z[: n - 252]
    d = np.linalg.norm(pool - Z[n - 1], axis=1)
    nb = np.argpartition(d, K)[:K]
    out = y[nb] * 100
    out = out[~np.isnan(out)]
    print(f"           DAYS LIKE TODAY ({K} analogues): {np.mean(out > 0) * 100:.0f}% closed up next day | "
          f"median {np.median(out):+.2f}% | typical band {np.percentile(out, 10):+.2f}% to "
          f"{np.percentile(out, 90):+.2f}%")


# Calibration stamps from the 4 Oct 2026 walk-forward bench (RESULTS_ANALOGUE.txt).
# Re-run main() to re-verify before ever changing these.
CALIBRATION = {
    "GOLD": "band UNRELIABLE here — gold currently runs hotter than its own history; treat the range as wider",
    "S&P 500": "calibrated (76.8% coverage)",
    "NASDAQ 100": "calibrated (78.6%)",
    "FTSE 100": "calibrated (85.8%)",
    "BITCOIN": "calibrated (87.6%) — but its 'confident' direction reads tested WORSE than chance; ignore the up-percentage",
    "DOLLAR": "calibrated (83.2%)",
}


def today_fan(symbol, name):
    """Today's live analogue fan for one market — the product. Returns a dict or None."""
    df = yf.download(symbol, period="max", interval="1d", progress=False,
                     auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["close"])
    f = features(df)
    if len(f) < 1500:
        return None
    X = f[["trend", "volx", "rpos", "rsi", "ret1", "ret5"]].to_numpy()
    y = f["next"].to_numpy()
    mu, sd = X.mean(axis=0), X.std(axis=0) + 1e-9
    Z = (X - mu) / sd
    n = len(f)
    pool = Z[: n - 252]
    d = np.linalg.norm(pool - Z[n - 1], axis=1)
    nb = np.argpartition(d, K)[:K]
    out = y[nb] * 100
    out = out[~np.isnan(out)]
    if len(out) < 50:
        return None
    return dict(name=name, up=float(np.mean(out > 0) * 100),
                med=float(np.median(out)), lo=float(np.percentile(out, 10)),
                hi=float(np.percentile(out, 90)),
                note=CALIBRATION.get(name, "uncalibrated"))


def main():
    print("ANALOGUE ENGINE — walk-forward calibration (last ~500 days each)\n")
    for sym, name in MARKETS:
        try:
            run(sym, name)
        except Exception as e:
            print(f"{name:10} failed: {str(e)[:80]}")


if __name__ == "__main__":
    main()
