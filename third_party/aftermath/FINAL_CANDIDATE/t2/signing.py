"""Signed receipts: an OUTER Ed25519 signature layer over the hash-chained ledgers (deep audit B, Kaaval primitive;
clean-room). The ledger bytes are never touched (frozen A/B/C records unchanged); signatures live in a sidecar
`<ledger stem>.sigs.jsonl` next to each ledger, and heads are optionally anchored to a separate append-only,
hash-chained, signed log outside the repo (a git repo when initialised: every anchor is also a commit).

Why: an unsigned SHA-256 chain detects edits but anyone can rebuild it end to end. A rebuilt chain no longer contains
the signed head at the signed position, and a new signature needs the private key, which never enters git.

Key:    private  T2_SIGNING_KEY  (default ~/.config/side_agent_b/t2_ledger_ed25519.key, 0600, dir 0700; never in git)
        public   t2/keys/ledger_ed25519.pub (committed; JSON {alg, key_id, public_hex})
Anchor: T2_ANCHOR_DIR (default ~/.local/share/side_agent_b/t2_anchor) / anchors.jsonl
Signed message: canonical JSON {"v":1,"ledger":<path relative to t2/>,"n":<records>,"head":<hash of record n-1>,
                "signed_at_utc":..,"key_id":..} (UTF-8)."""
from __future__ import annotations
import hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path
from .ledger import HashLedger, canon, verify as verify_chain

HERE = Path(__file__).resolve().parent
PUB_PATH = HERE / "keys" / "ledger_ed25519.pub"

def key_path(): return Path(os.environ.get("T2_SIGNING_KEY") or Path.home() / ".config" / "side_agent_b" / "t2_ledger_ed25519.key")
def anchor_path(): return Path(os.environ.get("T2_ANCHOR_DIR") or Path.home() / ".local" / "share" / "side_agent_b" / "t2_anchor") / "anchors.jsonl"
def sig_path(ledger): ledger = Path(ledger); return ledger.with_name(ledger.stem + ".sigs.jsonl")
def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _crypto():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.exceptions import InvalidSignature
    return Ed25519PrivateKey, Ed25519PublicKey, ser, InvalidSignature

def key_id(pub_raw: bytes) -> str: return "ed25519:" + hashlib.sha256(pub_raw).hexdigest()[:16]

def keygen(path=None, pub_out=PUB_PATH, overwrite=False):
    """Create the private key (0600) once; write the public key file. Refuses to overwrite an existing key."""
    Priv, _, ser, _ = _crypto()
    path = Path(path or key_path())
    if path.exists() and not overwrite: raise FileExistsError(f"signing key already exists at {path}")
    path.parent.mkdir(parents=True, exist_ok=True); os.chmod(path.parent, 0o700)
    k = Priv.generate()
    raw = k.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f: f.write(raw)
    os.chmod(path, 0o600)
    pub = k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    info = {"alg": "ed25519", "key_id": key_id(pub), "public_hex": pub.hex(), "created_at_utc": _now(),
            "private_key": "kept outside git (T2_SIGNING_KEY or ~/.config/side_agent_b/), mode 0600"}
    if pub_out is not None: Path(pub_out).parent.mkdir(parents=True, exist_ok=True); Path(pub_out).write_text(json.dumps(info, indent=1) + "\n")
    return info

def load_private(path=None):
    Priv, _, _, _ = _crypto()
    path = Path(path or key_path())
    if not path.exists(): return None
    if os.stat(path).st_mode & 0o077: raise PermissionError(f"signing key {path} must be mode 0600")
    return Priv.from_private_bytes(path.read_bytes())

def load_public(pub_path=PUB_PATH):
    _, Pub, _, _ = _crypto()
    info = json.loads(Path(pub_path).read_text())
    raw = bytes.fromhex(info["public_hex"])
    assert key_id(raw) == info["key_id"], "public key file: key_id does not match the key"
    return Pub.from_public_bytes(raw), info["key_id"]

def ledger_name(ledger, root=HERE):
    ledger = Path(ledger).resolve()
    try: return str(ledger.relative_to(Path(root).resolve()))
    except ValueError:
        parts = ledger.parts                                   # another worktree's t2 tree: same name as in this one
        for i in range(len(parts) - 3):
            if parts[i:i + 3] == ("FINAL_CANDIDATE", "t2", "runs"): return "/".join(parts[i + 2:])
        return str(ledger)                                     # anything else (temp dirs): absolute path, never collides

def message(name, n, head, signed_at, kid):
    return canon({"v": 1, "ledger": name, "n": n, "head": head, "signed_at_utc": signed_at, "key_id": kid}).encode()

def _records(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []

def sign_head(ledger, priv=None, *, root=HERE, anchor=True):
    """Sign the current head (idempotent: no new entry when the head is already signed). Returns the entry, or
    {"status": "NO_KEY"} when no private key is available (the ledger is untouched either way)."""
    priv = priv if priv is not None else load_private()
    if priv is None: return {"status": "NO_KEY"}
    _, _, ser, _ = _crypto()
    v = verify_chain(ledger)
    if not v["ok"]: return {"status": "REFUSED_CHAIN_BROKEN", "broken_at": v.get("broken_at")}
    if v["n"] == 0: return {"status": "EMPTY"}
    sp = sig_path(ledger); prev = _records(sp)
    if prev and prev[-1]["n"] == v["n"] and prev[-1]["head"] == v["head"]: return {"status": "ALREADY_SIGNED", **prev[-1]}
    kid = key_id(priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw))
    name, at = ledger_name(ledger, root), _now()
    e = {"v": 1, "ledger": name, "n": v["n"], "head": v["head"], "signed_at_utc": at, "key_id": kid,
         "sig": priv.sign(message(name, v["n"], v["head"], at, kid)).hex()}
    with sp.open("a") as f: f.write(json.dumps(e, sort_keys=True) + "\n")
    if anchor: anchor_heads([e], priv)
    return {"status": "SIGNED", **e}

def anchor_heads(entries, priv, path=None):
    """Append signed heads to the separate append-only anchor log (hash-chained + signed per line). If the anchor
    directory is a git repo, each append is committed (an independent, timestamped history)."""
    path = Path(path or anchor_path()); path.parent.mkdir(parents=True, exist_ok=True)
    led = HashLedger(path)
    for e in entries:
        body = {"type": "ANCHOR", "ledger": e["ledger"], "n": e["n"], "head": e["head"], "ledger_sig": e["sig"], "key_id": e["key_id"], "anchored_at_utc": _now()}
        body["anchor_sig"] = priv.sign(canon(body).encode()).hex()
        led.append(body)
    if (path.parent / ".git").exists():
        try:
            subprocess.run(["git", "-C", str(path.parent), "add", path.name], capture_output=True, timeout=20)
            subprocess.run(["git", "-C", str(path.parent), "-c", "user.name=t2-anchor", "-c", "user.email=t2-anchor@localhost",
                            "commit", "-q", "-m", f"anchor {len(entries)} head(s)"], capture_output=True, timeout=20)
        except Exception: pass
    return len(entries)

def supersede(ledger, reason, priv=None, *, root=HERE):
    """Legitimate regeneration of a signed ledger (e.g. a demo re-run). Visible and key-gated: the old sidecar is kept
    as <stem>.sigs.superseded-<time>.jsonl, a signed SUPERSEDE entry (name, old heads, reason) goes to the anchor log,
    then the new head is signed. Without the key nobody can do this, so a silent rebuild still fails verification."""
    priv = priv if priv is not None else load_private()
    if priv is None: raise FileNotFoundError("no signing key")
    _, _, ser, _ = _crypto()
    sp = sig_path(ledger); old = _records(sp); name = ledger_name(ledger, root); at = _now()
    if sp.exists(): sp.rename(sp.with_name(f"{Path(ledger).stem}.sigs.superseded-{at.replace(':', '')}.jsonl"))
    kid = key_id(priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw))
    body = {"type": "SUPERSEDE", "ledger": name, "old_heads": [[e["n"], e["head"]] for e in old], "reason": reason, "key_id": kid, "anchored_at_utc": at}
    body["anchor_sig"] = priv.sign(canon(body).encode()).hex()
    path = anchor_path(); path.parent.mkdir(parents=True, exist_ok=True); HashLedger(path).append(body)
    return sign_head(ledger, priv, root=root)

def verify_signed(ledger, pub=None, *, root=HERE, anchor=None, require=False):
    """Outer check on top of the hash chain. Status:
      SIGNED / SIGNED_UNSIGNED_TAIL (records appended after the last signature: fine for a running log) /
      UNSIGNED (no sidecar; FAIL when require=True) /
      FAIL: CHAIN_BROKEN, BAD_SIGNATURE, KEY_MISMATCH, WRONG_LEDGER, SIGNED_HEAD_NOT_IN_CHAIN (rebuilt or truncated),
            NON_MONOTONIC, ANCHOR_MISMATCH."""
    _, _, _, Invalid = _crypto()
    pub, kid = pub if pub is not None else load_public()
    v = verify_chain(ledger)
    if not v["ok"]: return {"ok": False, "status": "CHAIN_BROKEN", "broken_at": v.get("broken_at")}
    recs = _records(ledger)
    try: sigs = _records(sig_path(ledger))
    except ValueError: return {"ok": False, "status": "SIDECAR_UNPARSEABLE"}                  # fail, never crash
    name = ledger_name(ledger, root)
    def head_at(n): return recs[n - 1]["hash"] if 1 <= n <= len(recs) else None
    last_n = 0
    for i, s in enumerate(sigs):
        if s.get("key_id") != kid: return {"ok": False, "status": "KEY_MISMATCH", "at_sig": i}
        try: pub.verify(bytes.fromhex(s["sig"]), message(s["ledger"], s["n"], s["head"], s["signed_at_utc"], s["key_id"]))
        except (Invalid, ValueError, KeyError): return {"ok": False, "status": "BAD_SIGNATURE", "at_sig": i}
        if s["ledger"] != name: return {"ok": False, "status": "WRONG_LEDGER", "at_sig": i, "signed_for": s["ledger"]}
        if s["n"] < last_n: return {"ok": False, "status": "NON_MONOTONIC", "at_sig": i}
        if head_at(s["n"]) != s["head"]: return {"ok": False, "status": "SIGNED_HEAD_NOT_IN_CHAIN", "at_sig": i, "n": s["n"]}
        last_n = s["n"]
    anchored = 0
    ap = Path(anchor) if anchor is not None else anchor_path()
    if ap.exists():
        av = verify_chain(ap)
        if not av["ok"]: return {"ok": False, "status": "ANCHOR_CHAIN_BROKEN", "broken_at": av.get("broken_at")}
        mine = [a for a in _records(ap) if a.get("ledger") == name]
        last_sup = max([i for i, a in enumerate(mine) if a.get("type") == "SUPERSEDE"], default=-1)
        for i, a in enumerate(mine):
            if a.get("type") == "SUPERSEDE":                 # signed, reasoned regeneration: earlier anchors no longer apply
                body = {k: a[k] for k in ("type", "ledger", "old_heads", "reason", "key_id", "anchored_at_utc")}
                try: pub.verify(bytes.fromhex(a["anchor_sig"]), canon(body).encode())
                except (Invalid, ValueError, KeyError): return {"ok": False, "status": "ANCHOR_BAD_SIGNATURE", "seq": a.get("seq")}
                continue
            body = {k: a[k] for k in ("type", "ledger", "n", "head", "ledger_sig", "key_id", "anchored_at_utc")}
            try: pub.verify(bytes.fromhex(a["anchor_sig"]), canon(body).encode())
            except (Invalid, ValueError, KeyError): return {"ok": False, "status": "ANCHOR_BAD_SIGNATURE", "seq": a.get("seq")}
            if i < last_sup: continue                        # superseded (signature still checked above)
            if head_at(a["n"]) != a["head"]: return {"ok": False, "status": "ANCHOR_MISMATCH", "seq": a.get("seq"), "n": a["n"]}
            anchored += 1
        if anchored and not sigs: return {"ok": False, "status": "ANCHORED_BUT_SIDECAR_MISSING", "anchored": anchored}
    if not sigs: return {"ok": not require, "status": "UNSIGNED", "n": v["n"]}
    tail = v["n"] - last_n
    return {"ok": True, "status": "SIGNED" if tail == 0 else "SIGNED_UNSIGNED_TAIL", "n": v["n"], "signed_n": last_n, "unsigned_tail": tail,
            "n_signatures": len(sigs), "anchored": anchored, "key_id": kid}

def sign_all(paths, priv=None, root=HERE):
    priv = priv if priv is not None else load_private()
    return {str(p): sign_head(p, priv, root=root) for p in paths}

MANIFEST = HERE / "keys" / "signed_ledgers.json"

def committed_ledgers(runs=HERE / "runs"):
    """t2 ledgers that live in git (live/, market_recorder/ and */state/ are gitignored)."""
    fs = list(runs.glob("*/ledger.jsonl")) + list(runs.glob("demo/ablations/*.jsonl"))
    return sorted(f for f in fs if f.parts[-2] not in ("live",) and ".sigs" not in f.name and "live_smoke" not in str(f) and "live_verify" not in str(f))

def live_ledgers(live_dir):
    live_dir = Path(live_dir)
    return ([live_dir / "ledger.jsonl"] if (live_dir / "ledger.jsonl").exists() else []) + sorted(live_dir.glob("arms/*/ledger.jsonl")) + \
           ([live_dir / "live_flow" / "ledger.jsonl"] if (live_dir / "live_flow" / "ledger.jsonl").exists() else [])   # scheduled t2-live-flow

def sign_committed(priv=None):
    """Sign every committed t2 ledger and record their names in the committed manifest (the judge then requires a
    valid signature for each)."""
    priv = priv if priv is not None else load_private()
    if priv is None: raise FileNotFoundError(f"no signing key at {key_path()} (run: python FINAL_CANDIDATE/run.py t2-keygen)")
    out = sign_all(committed_ledgers(), priv)
    names = sorted(ledger_name(p) for p in committed_ledgers())
    MANIFEST.write_text(json.dumps({"required_signed": names, "note": "every ledger listed here must carry a valid Ed25519 head signature (run.py judge, step 2b)"}, indent=1) + "\n")
    return out

def required_names():
    return set(json.loads(MANIFEST.read_text())["required_signed"]) if MANIFEST.exists() else set()
