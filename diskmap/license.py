"""Verify a DiskMap Studio Pro license without contacting a server."""
import base64
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PUBLIC_KEY = bytes.fromhex("10ebda690746c957528e69396e4e86246df60f200263d13ed4b271184099535a")
LICENSE_LIMIT = 4096


def verify(blob, *, public_key=PUBLIC_KEY):
    try:
        if len(blob) > LICENSE_LIMIT:
            raise ValueError
        body, signature = blob.strip().split(b".")
        payload = base64.b64decode(body, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            base64.b64decode(signature, validate=True), payload
        )
        claims = json.loads(payload)
        if (not isinstance(claims, dict)
                or claims.get("product") != "DiskMap Studio"
                or claims.get("edition") != "Pro"
                or not isinstance(claims.get("holder"), str)
                or not 1 <= len(claims["holder"]) <= 150
                or not claims["holder"].isprintable()):
            raise ValueError
        return claims["holder"]
    except (InvalidSignature, ValueError) as error:
        raise ValueError("A licença Pro é inválida.") from error


def read_license(path):
    with path.open("rb") as handle:
        return handle.read(LICENSE_LIMIT + 1)
