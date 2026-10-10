# Receipt signing

The production Ed25519 private key is generated on this machine and is not the research key `ed25519:45e4334c577525fa`.

- Commit `keys/production_ed25519.pub` only.
- Keep the private file outside Git. On Render, mount it as a secret file at `T2_SIGNING_KEY=/etc/secrets/production_ed25519.key`.
- Keep one offline encrypted backup. If both copies are lost, do not forge old lines. Start a new chain id and append a signed `key_rotation` line that names the retired public key id.
- Old public keys stay pinned so older lines still verify.
- OpenTimestamps status stays `pending` until a proof file exists. A missing proof is not a confirmed timestamp.
- The private key and the API process share a host. Verification from a fresh checkout uses only the public key and the stored line.

`ledger_lines` stores `pubkey_id`. It does not store key bytes.
