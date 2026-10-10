"""Production receipts. The research private key is never loaded."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

RESEARCH_KEY_ID = "ed25519:45e4334c577525fa"


def key_id(pub_raw: bytes) -> str:
    return "ed25519:" + hashlib.sha256(pub_raw).hexdigest()[:16]


def generate_production_key(private_path: Path, public_path: Path) -> str:
    private_path.parent.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    private_path.write_bytes(key.private_bytes_raw())
    try:
        private_path.chmod(0o600)
    except OSError:
        pass
    pub = key.public_key().public_bytes_raw()
    kid = key_id(pub)
    if kid == RESEARCH_KEY_ID:
        raise RuntimeError("production key collided with the research key")
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_text(json.dumps({"alg": "ed25519", "key_id": kid, "public_hex": pub.hex()}) + "\n", encoding="utf-8")
    return kid


def load_public(public_path: Path) -> tuple[Ed25519PublicKey, str]:
    info = json.loads(public_path.read_text(encoding="utf-8"))
    raw = bytes.fromhex(info["public_hex"])
    if key_id(raw) != info["key_id"]:
        raise ValueError("public key id mismatch")
    return Ed25519PublicKey.from_public_bytes(raw), info["key_id"]


def read_private_bytes(private_path: Path) -> bytes:
    raw = private_path.read_bytes()
    if len(raw) == 32:
        return raw
    text = raw.decode("ascii").strip()
    if len(text) == 64:
        return bytes.fromhex(text)
    raise ValueError("private key must be 32 raw bytes or 64 hex characters")


def sign_line(private_path: Path, body: dict, prev_hash: str) -> dict:
    if not private_path.is_file():
        raise FileNotFoundError(str(private_path))
    priv = Ed25519PrivateKey.from_private_bytes(read_private_bytes(private_path))
    pub = priv.public_key().public_bytes_raw()
    kid = key_id(pub)
    payload = json.dumps({"body": body, "prev_hash": prev_hash}, sort_keys=True, separators=(",", ":")).encode()
    line_hash = hashlib.sha256(payload).hexdigest()
    signature = priv.sign(line_hash.encode()).hex()
    return {"line_hash": line_hash, "prev_hash": prev_hash, "body": body, "signature": signature, "pubkey_id": kid}


def issue_receipt(store, private_path: Path, body: dict) -> dict:
    line = sign_line(private_path, body, store.last_prev())
    stored = store.append_ledger(line)
    row = {"id": "rcpt_" + stored["line_hash"][:16], "ledger_seq": stored["seq"], "ots_status": "pending"}
    store.insert_receipt(row)
    return {**row, "line": stored}


def chain_intact(public_path: Path, lines: list[dict]) -> bool:
    prev = "GENESIS"
    for index, line in enumerate(lines, start=1):
        if line.get("seq") != index or line.get("prev_hash") != prev:
            return False
        if not verify_line(public_path, line):
            return False
        prev = line["line_hash"]
    return True


def verify_line(public_path: Path, line: dict) -> bool:
    try:
        pub, kid = load_public(public_path)
    except (ValueError, KeyError, json.JSONDecodeError):
        return False
    if line["pubkey_id"] != kid:
        return False
    payload = json.dumps({"body": line["body"], "prev_hash": line["prev_hash"]}, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(payload).hexdigest() != line["line_hash"]:
        return False
    try:
        pub.verify(bytes.fromhex(line["signature"]), line["line_hash"].encode())
    except InvalidSignature:
        return False
    return True
