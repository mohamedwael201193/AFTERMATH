"""Public Bitget v2 market-data tools (no keys) with a content-addressed, timestamped response cache.

Every response is stored as {endpoint, params, fetched_at_utc, sha256(body), body}. Replay mode reads only from the
cache, so each decision is reproducible from recorded inputs. Endpoints verified live 2026-10-09 (see README)."""
from __future__ import annotations
import hashlib, json, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.bitget.com"
EP = {
    "candles": "/api/v2/mix/market/candles",              # symbol, productType, granularity, limit, endTime
    "ticker": "/api/v2/mix/market/ticker",                # symbol, productType
    "depth": "/api/v2/mix/market/merge-depth",            # symbol, productType, limit
    "funding_current": "/api/v2/mix/market/current-fund-rate",
    "funding_history": "/api/v2/mix/market/history-fund-rate",
    "contracts": "/api/v2/mix/market/contracts",          # includes isRwa, takerFeeRate, symbolStatus, maxLever
    "rtoken_ticker": "/api/v2/spot/market/tickers",       # rToken spot, e.g. RNVDAUSDT
    "rtoken_symbols": "/api/v2/spot/public/symbols",
}
PT = "USDT-FUTURES"

def _key(name, params): return hashlib.sha256((name + "?" + urllib.parse.urlencode(sorted(params.items()))).encode()).hexdigest()[:24]

class BitgetPublic:
    def __init__(self, cache_dir, mode="live", timeout_s=15, fetch=None, registry=None):
        assert mode in ("live", "replay")
        self.cache = Path(cache_dir); self.cache.mkdir(parents=True, exist_ok=True); self.mode = mode
        self.timeout_s = timeout_s; self._fetch = fetch or self._http
        self.registry = registry          # provenance.SourceRegistry (optional): every get() is logged with label + latency

    def _log(self, rec, label):
        if self.registry is not None:
            self.registry.log(input=rec["name"], symbol=rec["params"].get("symbol"), label=label, fetched_at_utc=rec["fetched_at_utc"],
                              latency_ms=rec.get("latency_ms"), sha256=rec["sha256"], endpoint=rec["endpoint"])

    def _http(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "SIDE_AGENT_B-t2/1.0 (public market data)"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as r: return r.read()

    def get(self, name, **params):
        """Returns a record dict: {endpoint, params, fetched_at_utc, sha256, data}. data = parsed 'data' field."""
        params = {k: str(v) for k, v in params.items() if v is not None}
        f = self.cache / f"{name}_{_key(name, params)}.json"
        if self.mode == "replay":
            if not f.exists(): raise FileNotFoundError(f"replay cache miss: {name} {params}")
            rec = json.loads(f.read_text())
            body = rec["body"].encode()
            if hashlib.sha256(body).hexdigest() != rec["sha256"]: raise ValueError(f"cache tampered: {f.name}")
            self._log(rec, "recorded-fixture")
            return self._wrap(rec)
        url = BASE + EP[name] + "?" + urllib.parse.urlencode(params)
        last = None; t0 = time.monotonic()
        for attempt in range(3):
            try:
                body = self._fetch(url); break
            except urllib.error.HTTPError as e:
                # 4xx is a request error (e.g. Bitget 40034 "Parameter ... does not exist"): surface the Bitget code and do
                # not retry. 5xx/429 are transient and retried. (Before 2026-10-09 every error became ConnectionError.)
                msg = ""
                try: j = json.loads(e.read().decode()); msg = f"{j.get('code')}: {j.get('msg')}"
                except Exception: pass
                if 400 <= e.code < 500 and e.code != 429:
                    raise ValueError(f"bitget HTTP {e.code} {name} {params.get('symbol', '')}: {msg}") from None
                last = e; time.sleep(0.5 * 2 ** attempt)
            except Exception as e:
                last = e; time.sleep(0.5 * 2 ** attempt)
        else:
            raise ConnectionError(f"bitget public fetch failed: {name}: {type(last).__name__}")
        txt = body.decode() if isinstance(body, bytes) else body
        d = json.loads(txt)
        if d.get("code") != "00000": raise ValueError(f"bitget error {d.get('code')}: {d.get('msg')}")
        rec = {"endpoint": EP[name], "name": name, "params": params,
               "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
               "sha256": hashlib.sha256(txt.encode()).hexdigest(), "latency_ms": round((time.monotonic() - t0) * 1000, 1), "body": txt}
        f.write_text(json.dumps(rec))
        self._log(rec, "bitget-rest-live")
        return self._wrap(rec)

    @staticmethod
    def _wrap(rec):
        return {"endpoint": rec["endpoint"], "name": rec["name"], "params": rec["params"], "fetched_at_utc": rec["fetched_at_utc"],
                "sha256": rec["sha256"], "data": json.loads(rec["body"])["data"]}

    # convenience wrappers --------------------------------------------------------------
    def candles(self, symbol, granularity="1H", limit=200, end_ms=None):
        return self.get("candles", symbol=symbol, productType=PT, granularity=granularity, limit=limit, endTime=end_ms)
    def ticker(self, symbol): return self.get("ticker", symbol=symbol, productType=PT)
    def depth(self, symbol, limit="max"): return self.get("depth", symbol=symbol, productType=PT, limit=limit)
    def funding_current(self, symbol): return self.get("funding_current", symbol=symbol, productType=PT)
    def funding_history(self, symbol, page_size=100): return self.get("funding_history", symbol=symbol, productType=PT, pageSize=page_size)
    def contract(self, symbol): return self.get("contracts", productType=PT, symbol=symbol)
    def rtoken_ticker(self, symbol):
        """rToken SPOT ticker. Spot names differ from the perp: NVDAUSDT perp <-> RNVDAUSDT rToken (verified via
        /api/v2/spot/public/symbols 2026-10-09). A perp symbol is mapped by prefixing 'R'. QQQUSDT -> RQQQUSDT."""
        return self.get("rtoken_ticker", symbol=rtoken_symbol(symbol))

def rtoken_symbol(perp_symbol: str) -> str:
    return perp_symbol if perp_symbol.startswith("R") and perp_symbol[1:] in RTOKEN_BASES else "R" + perp_symbol

RTOKEN_BASES = {"NVDAUSDT", "TSLAUSDT", "AAPLUSDT", "AMZNUSDT", "MSFTUSDT", "METAUSDT", "GOOGLUSDT", "COINUSDT", "MSTRUSDT", "QQQUSDT"}

def book_from_depth(rec):
    d = rec["data"]
    return {"bids": [[float(p), float(q)] for p, q in d["bids"]], "asks": [[float(p), float(q)] for p, q in d["asks"]],
            "ts_ms": int(d.get("ts", 0)), "sha256": rec["sha256"]}

def depth_profile(book):
    """Convert a book into a price-free profile: levels as (offset_bp from mid, size in quote USDT). Lets a recorded
    live book be re-centred on a historical price (labelled as such wherever used)."""
    bb, ba = book["bids"][0][0], book["asks"][0][0]; mid = (bb + ba) / 2
    prof = {"bids": [[(mid - p) / mid * 1e4, p * q] for p, q in book["bids"]],
            "asks": [[(p - mid) / mid * 1e4, p * q] for p, q in book["asks"]]}
    prof["half_spread_bp"] = (ba - bb) / mid * 1e4 / 2
    return prof

def candles_to_rows(rec):
    """Bitget candle rows: [ts_ms, open, high, low, close, base_vol, quote_vol]."""
    return [[int(r[0])] + [float(x) for x in r[1:7]] for r in rec["data"]]
