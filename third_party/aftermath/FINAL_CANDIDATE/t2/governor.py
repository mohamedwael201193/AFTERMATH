"""Deterministic risk governor. Pure function of (proposal, context). The model can never override it: it can only
shrink size or refuse. Every check is recorded (name, pass, observed value, limit) — refusals carry all failed checks."""
from __future__ import annotations
import math, os
from dataclasses import dataclass, asdict
from pathlib import Path

WHITELIST = {"NVDAUSDT", "TSLAUSDT", "AAPLUSDT", "AMZNUSDT", "MSFTUSDT", "METAUSDT", "GOOGLUSDT", "COINUSDT", "MSTRUSDT"}

@dataclass(frozen=True)
class Limits:
    max_size_frac: float = 0.10          # per position, of paper equity (shrink, not refuse)
    max_gross_leverage: float = 1.0      # gross notional incl. hedge legs / equity
    max_open_positions: int = 3
    min_llm_confidence: float = 0.55
    max_spread_bp: float = 12.0
    depth_band_bp: float = 25.0          # order (main leg) must be fillable within this band of mid
    depth_cover: float = 1.0             # depth within band >= cover * order notional
    max_data_age_min: float = 90.0
    max_event_age_min: float = 360.0
    symbol_daily_loss: float = -0.005    # realized on that symbol today, fraction of equity
    daily_loss_halt: float = -0.02
    drawdown_halt: float = -0.08
    min_precedents: int = 3              # Reanchor primitive
    max_horizon_h: int = 48
    min_hedge_r2: float = 0.15

def emergency_stop_engaged(state_dir) -> bool:
    return os.environ.get("T2_KILL") == "1" or (Path(state_dir) / "KILL_SWITCH").exists()

def check(proposal: dict | None, ctx: dict, lim: Limits = Limits()) -> dict:
    """ctx keys: symbol, source ('llm'|'rule'), emergency_stop, contract{status,is_rwa}, spread_bp, depth_band_usdt,
    data_age_min, event_age_min, equity, gross_open_usdt, n_open, open_symbols, symbol_pnl_today, day_pnl, drawdown,
    n_precedents, hedge_beta, hedge_r2."""
    checks = []
    def c(name, ok, value=None, limit=None): checks.append({"check": name, "pass": bool(ok), "value": value, "limit": limit})
    c("emergency_stop_off", not ctx["emergency_stop"], ctx["emergency_stop"], False)
    if ctx["emergency_stop"]:
        return {"verdict": "REFUSED", "size_frac": 0.0, "checks": checks, "reasons": ["emergency_stop_off"], "limits": asdict(lim)}
    if proposal is None:
        return {"verdict": "NO_ACTION", "size_frac": 0.0, "checks": checks, "reasons": ["NO_VALID_PROPOSAL"], "limits": asdict(lim)}
    if proposal["action"] == "NO_ACTION":
        return {"verdict": "NO_ACTION", "size_frac": 0.0, "checks": checks, "reasons": ["PROPOSER_NO_ACTION"], "limits": asdict(lim)}
    s = ctx["symbol"]; eq = ctx["equity"]
    c("symbol_matches_event", proposal["symbol"] == s, proposal["symbol"], s)
    c("symbol_whitelisted", s in WHITELIST, s, "whitelist")
    c("contract_tradeable", ctx["contract"].get("status") == "normal" and ctx["contract"].get("is_rwa") == "YES", {"status": ctx["contract"].get("status"), "is_rwa": ctx["contract"].get("is_rwa")}, "normal & isRwa")
    if ctx["source"] == "llm": c("llm_confidence", proposal["confidence"] >= lim.min_llm_confidence, proposal["confidence"], lim.min_llm_confidence)
    c("data_fresh", ctx["data_age_min"] <= lim.max_data_age_min, round(ctx["data_age_min"], 1), lim.max_data_age_min)
    c("event_fresh", ctx["event_age_min"] <= lim.max_event_age_min, round(ctx["event_age_min"], 1), lim.max_event_age_min)
    c("daily_loss_ok", ctx["day_pnl"] > lim.daily_loss_halt, round(ctx["day_pnl"], 5), lim.daily_loss_halt)
    c("drawdown_ok", ctx["drawdown"] > lim.drawdown_halt, round(ctx["drawdown"], 5), lim.drawdown_halt)
    c("symbol_loss_ok", ctx["symbol_pnl_today"] > lim.symbol_daily_loss, round(ctx["symbol_pnl_today"], 5), lim.symbol_daily_loss)
    c("not_already_positioned", s not in set(ctx["open_symbols"]), sorted(ctx["open_symbols"]), "none on symbol")
    c("open_positions_ok", ctx["n_open"] < lim.max_open_positions, ctx["n_open"], lim.max_open_positions)
    c("precedents_ok", ctx["n_precedents"] >= lim.min_precedents, ctx["n_precedents"], lim.min_precedents)
    c("hedge_fit_ok", ctx["hedge_r2"] is not None and ctx["hedge_r2"] >= lim.min_hedge_r2, None if ctx["hedge_r2"] is None else round(ctx["hedge_r2"], 3), lim.min_hedge_r2)
    c("spread_ok", ctx["spread_bp"] <= lim.max_spread_bp, round(ctx["spread_bp"], 2), lim.max_spread_bp)
    size = min(proposal["size_frac"], lim.max_size_frac)
    shrunk = size < proposal["size_frac"]
    gross_new = size * eq * (1 + abs(ctx.get("hedge_beta") or 0.0))
    room = lim.max_gross_leverage * eq - ctx["gross_open_usdt"]
    if gross_new > room and room > 0:
        size = size * room / gross_new; gross_new = room; shrunk = True
    # fail closed (security audit, Worker C): a non-finite size/beta/gross or a size that rounds to 0 can never pass, and
    # equity <= 0 no longer divides by zero. For finite, positive inputs the record is byte-identical to before.
    # Non-finite context values (e.g. +inf depth, -inf open positions) also fail here; the failure is reported under
    # gross_leverage_ok so that no new check entry changes the records of the frozen arms.
    _num = [ctx.get(k) for k in ("spread_bp", "depth_band_usdt", "data_age_min", "event_age_min", "equity", "gross_open_usdt", "n_open",
                                 "symbol_pnl_today", "day_pnl", "drawdown", "n_precedents", "hedge_beta", "hedge_r2")]
    sane = (math.isfinite(gross_new) and math.isfinite(size) and math.isfinite(float(proposal["size_frac"])) and round(size, 6) > 0
            and math.isfinite(float(proposal["confidence"])) and math.isfinite(float(proposal["horizon_hours"]))
            and all(math.isfinite(float(v)) for v in _num if isinstance(v, (int, float)) and not isinstance(v, bool)))
    lev = round((ctx["gross_open_usdt"] + gross_new) / eq, 4) if (isinstance(eq, (int, float)) and eq > 0) else None
    c("gross_leverage_ok", room > 0 and size > 0 and sane, lev, lim.max_gross_leverage)
    order = size * eq
    c("depth_ok", ctx["depth_band_usdt"] >= lim.depth_cover * order, round(ctx["depth_band_usdt"], 0), round(lim.depth_cover * order, 0))
    c("horizon_ok", 1 <= proposal["horizon_hours"] <= lim.max_horizon_h, proposal["horizon_hours"], lim.max_horizon_h)
    failed = [x["check"] for x in checks if not x["pass"]]
    if failed: return {"verdict": "REFUSED", "size_frac": 0.0, "checks": checks, "reasons": failed, "limits": asdict(lim)}
    return {"verdict": "APPROVED", "size_frac": round(size, 6), "resized": shrunk, "requested_size_frac": proposal["size_frac"],
            "checks": checks, "reasons": ["RESIZED_BY_GOVERNOR"] if shrunk else [], "limits": asdict(lim)}
