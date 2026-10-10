"""Tamper-evident append-only ledger (JSONL, SHA-256 hash chain). Any edit, deletion or reorder breaks verify()."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

def canon(obj) -> str: return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
def sha(obj) -> str: return hashlib.sha256(canon(obj).encode()).hexdigest()

class HashLedger:
    def __init__(self, path, fresh=False):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        if fresh and self.path.exists(): self.path.unlink()
        self._last = self._read_last(); self.n = self._count()
    def _read_last(self):
        if not self.path.exists() or self.path.stat().st_size == 0: return "GENESIS"
        return json.loads(self.path.read_text().strip().splitlines()[-1])["hash"]
    def _count(self):
        return 0 if not self.path.exists() else len([l for l in self.path.read_text().splitlines() if l.strip()])
    def append(self, rec: dict) -> dict:
        rec = dict(rec); rec["seq"] = self.n; rec["prev"] = self._last
        rec["hash"] = sha({k: v for k, v in rec.items() if k != "hash"})
        with self.path.open("a") as f: f.write(json.dumps(rec, default=str, sort_keys=True) + "\n")
        self._last = rec["hash"]; self.n += 1; return rec
    def records(self):
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()] if self.path.exists() else []

def verify(path) -> dict:
    prev, n = "GENESIS", 0
    p = Path(path)
    if not p.exists(): return {"ok": True, "n": 0, "head": prev}
    for i, l in enumerate(x for x in p.read_text().splitlines() if x.strip()):
        try: r = json.loads(l)
        except ValueError: return {"ok": False, "broken_at": i, "n": i, "head": prev, "error": "UNPARSEABLE_LINE"}   # fail, never crash
        if not isinstance(r, dict): return {"ok": False, "broken_at": i, "n": i, "head": prev, "error": "NOT_AN_OBJECT"}
        if r.get("prev") != prev or r.get("seq") != i or sha({k: v for k, v in r.items() if k != "hash"}) != r.get("hash"):
            return {"ok": False, "broken_at": i, "n": i, "head": prev}
        prev = r["hash"]; n = i + 1
    return {"ok": True, "n": n, "head": prev}

class ClaimLock:
    """Reverb primitive: hash a claim (decision + grading rule + evidence hashes) BEFORE the outcome exists. Grading
    re-hashes the stored claim and refuses to grade when the hash differs or the lock time is not before the outcome
    window."""
    @staticmethod
    def lock(claim: dict, locked_at: str) -> dict:
        body = {"claim": claim, "locked_at_utc": locked_at}
        return {**body, "lock_sha256": sha(body)}
    @staticmethod
    def check(lock: dict, outcome_window_start: str) -> tuple[bool, str]:
        from .util import T
        body = {"claim": lock["claim"], "locked_at_utc": lock["locked_at_utc"]}
        if sha(body) != lock["lock_sha256"]: return False, "LOCK_HASH_MISMATCH"
        if T(lock["locked_at_utc"]) >= T(outcome_window_start): return False, "LOCKED_TOO_LATE"
        return True, "LOCK_OK"
