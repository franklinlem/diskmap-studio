import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from diskmap.license import verify


def test_license_accepts_verified_pro_claims_and_rejects_tampering():
    signer = Ed25519PrivateKey.generate()
    public_key = signer.public_key().public_bytes_raw()
    payload = b'{"product":"DiskMap Studio","edition":"Pro","holder":"Tester"}'
    signature = base64.b64encode(signer.sign(payload))
    assert verify(base64.b64encode(payload) + b"." + signature, public_key=public_key) == "Tester"
    with pytest.raises(ValueError):
        verify(base64.b64encode(payload.replace(b"Tester", b"Intruder")) + b"." + signature, public_key=public_key)
    with pytest.raises(ValueError):
        verify(b"corrupted", public_key=public_key)
