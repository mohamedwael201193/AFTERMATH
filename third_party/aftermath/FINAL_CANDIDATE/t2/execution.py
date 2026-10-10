"""Paper execution with realistic fills. No order endpoint exists anywhere in t2 (test-enforced).

- Fill time: the open of the first 1h bar whose open is STRICTLY AFTER decision time + latency. Never the decision bar.
- Taker fill: walk the order book level by level (VWAP), quote-size per level. In historical replay the book is a depth
  PROFILE recorded live (offsets in bp from mid + USDT size), re-centred on the fill-bar open: labelled
  'depth_source=profile_recorded_<ts>' because historical Bitget order books are not publicly downloadable.
- Fees: contract takerFeeRate (recorded from /api/v2/mix/market/contracts), both legs, entry and exit.
- Funding: every settlement in (entry, exit]; longs pay positive rates. Missing history -> conservative 1 bp/8h charge.
- Market-beta hedge (RESIDUAL-style expression): optional QQQUSDT leg of -beta_mkt x notional, same fill/fee/funding.
- Stop: 3% adverse move on a bar CLOSE -> exit at the next bar open. Otherwise time exit at fill + horizon."""
from __future__ import annotations
import math
import pandas as pd
from .util import T

H = pd.Timedelta(hours=1)
LATENCY = pd.Timedelta(seconds=5)
STOP = 0.03
FALLBACK_FUNDING_8H = 0.0001

def fill_time(decision_at, index) -> pd.Timestamp | None:
    t = T(decision_at) + LATENCY
    later = index[index > t]
    return later[0] if len(later) else None

def walk_book(side: int, notional: float, ref_price: float, profile: dict, fee_rate: float) -> dict:
    """side +1 buys (consumes asks), -1 sells (consumes bids). Returns VWAP, slippage vs ref mid, fee, filled."""
    levels = profile["asks"] if side > 0 else profile["bids"]
    left, cost_q, qty = notional, 0.0, 0.0
    for off_bp, size_q in levels:
        px = ref_price * (1 + side * off_bp / 1e4)
        take = min(left, size_q); qty += take / px; cost_q += take; left -= take
        if left <= 1e-9: break
    filled = notional - max(left, 0.0)
    vwap = cost_q / qty if qty else float("nan")
    return {"side": side, "requested_usdt": round(notional, 4), "filled_usdt": round(filled, 4), "unfilled_usdt": round(max(left, 0.0), 4),
            "qty": qty, "vwap": vwap, "ref_mid": ref_price, "slippage_bp": round(side * (vwap / ref_price - 1) * 1e4, 3) if qty else None,
            "fee_usdt": round(filled * fee_rate, 6), "fee_rate": fee_rate}

def funding_cost(funding: pd.Series | None, side: int, notional: float, t0, t1) -> tuple[float, int, str]:
    if funding is None or len(funding) == 0 or funding.index.min() > T(t0):
        n = int((T(t1) - T(t0)) / pd.Timedelta(hours=8))
        return notional * FALLBACK_FUNDING_8H * n, n, "fallback_1bp_per_8h"
    f = funding[(funding.index > T(t0)) & (funding.index <= T(t1))]
    return float(side * notional * f.sum()), int(len(f)), "recorded_history"

def leg_pnl(tape, sym, side, notional, entry_t, exit_t, profile, fee_rate, funding):
    o = tape["open"]
    if entry_t not in o.index or exit_t not in o.index or not (o.at[entry_t, sym] == o.at[entry_t, sym]): return None
    ent = walk_book(side, notional, float(o.at[entry_t, sym]), profile, fee_rate)
    if ent["qty"] == 0: return None
    ext = walk_book(-side, ent["qty"] * float(o.at[exit_t, sym]), float(o.at[exit_t, sym]), profile, fee_rate)
    gross = side * ent["qty"] * (ext["vwap"] - ent["vwap"]) if ext["qty"] else 0.0
    fund, n_f, fsrc = funding_cost(funding, side, ent["filled_usdt"], entry_t, exit_t)
    net = gross - ent["fee_usdt"] - ext["fee_usdt"] - fund
    return {"symbol": sym, "entry": ent, "exit": ext, "gross_usdt": round(gross, 6), "fees_usdt": round(ent["fee_usdt"] + ext["fee_usdt"], 6),
            "funding_usdt": round(fund, 6), "funding_settlements": n_f, "funding_source": fsrc, "net_usdt": round(net, 6)}

def planned_exit(tape, sym, side, entry_t, horizon_h, asof):
    """Deterministic exit using only bars known at `asof`. Returns (exit_t|None, reason)."""
    c = tape["close"]; o = tape["open"]; target = entry_t + pd.Timedelta(hours=horizon_h)
    entry_px = float(o.at[entry_t, sym])
    for t in c.index[(c.index >= entry_t) & (c.index < target)]:
        if t + H > T(asof): return None, "OPEN"
        if side * (float(c.at[t, sym]) / entry_px - 1) <= -STOP:
            nxt = t + H
            return (nxt, "STOP") if nxt in o.index and nxt <= T(asof) else (None, "OPEN")
    if target in o.index and target <= T(asof): return target, "TIME"
    return None, "OPEN"

def simulate(tape, sym, side, size_frac, equity, decision_at, horizon_h, asof, profiles, fees, fundings, hedge_beta=None, hedge_sym="QQQUSDT"):
    """Full paper trade (entry + exit) evaluated with data known at `asof`. Returns dict with status FILLED_OPEN /
    CLOSED / NO_FILL."""
    et = fill_time(decision_at, tape["open"].index)
    if et is None or et > T(asof): return {"status": "PENDING_FILL", "fill_at": None}
    assert et > T(decision_at), "same-bar fill forbidden"
    xt, why = planned_exit(tape, sym, side, et, horizon_h, asof)
    notional = size_frac * equity
    out = {"status": "OPEN" if xt is None else "CLOSED", "fill_at": et.isoformat(), "exit_at": xt.isoformat() if xt is not None else None,
           "exit_reason": why, "notional_usdt": round(notional, 4), "side": side, "depth_source": profiles[sym].get("label")}
    if xt is None:
        ent = walk_book(side, notional, float(tape["open"].at[et, sym]), profiles[sym], fees[sym])
        out["entry"] = ent; return out
    main = leg_pnl(tape, sym, side, notional, et, xt, profiles[sym], fees[sym], fundings.get(sym))
    if main is None: return {"status": "NO_FILL", "fill_at": et.isoformat()}
    legs = [main]
    if hedge_beta is not None and hedge_beta == hedge_beta and abs(hedge_beta) > 1e-6:
        hs = -side * (1 if hedge_beta > 0 else -1)
        hl = leg_pnl(tape, hedge_sym, hs, abs(hedge_beta) * notional, et, xt, profiles[hedge_sym], fees[hedge_sym], fundings.get(hedge_sym))
        if hl is not None: legs.append(hl)
    out["legs"] = legs; out["entry"] = main["entry"]
    out["net_usdt"] = round(sum(l["net_usdt"] for l in legs), 6)
    out["net_bp_equity"] = round(out["net_usdt"] / equity * 1e4, 3)
    out["costs_usdt"] = round(sum(l["fees_usdt"] + l["funding_usdt"] for l in legs) + sum(
        (l["entry"]["slippage_bp"] or 0) / 1e4 * l["entry"]["filled_usdt"] + (l["exit"]["slippage_bp"] or 0) / 1e4 * l["exit"]["filled_usdt"] for l in legs), 6)
    return out
