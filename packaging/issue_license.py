"""Issue a Pro license using Franklin's external Ed25519 private key."""
import argparse
import base64
import json
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def signed_license(key, holder):
    if not 1 <= len(holder) <= 150 or not holder.isprintable():
        raise ValueError("O nome do titular deve ter de 1 a 150 caracteres imprimíveis.")
    payload = json.dumps({
        "product": "DiskMap Studio", "edition": "Pro",
        "holder": holder, "serial": str(uuid4()),
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(payload) + b"." + base64.b64encode(key.sign(payload)) + b"\n"


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--key", type=Path, required=True)
    args.add_argument("--holder", required=True)
    args.add_argument("--out", type=Path, required=True)
    options = args.parse_args()
    key = Ed25519PrivateKey.from_private_bytes(options.key.read_bytes())
    with options.out.open("xb") as handle:
        handle.write(signed_license(key, options.holder))


if __name__ == "__main__":
    main()
