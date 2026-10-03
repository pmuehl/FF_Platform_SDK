import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from ff_platform_sdk.auth import TokenVerifier

ISSUER = "https://platform.test/o"
CLIENT = "counterpart"


class Keys:
    """Replaces the JWKS request: returns the public key of the test platform."""

    def __init__(self):
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def get_signing_key_from_jwt(self, token):
        class Result:
            key = self.private.public_key()

        return Result()

    def token(self, **claims) -> str:
        now = int(time.time())
        return jwt.encode(
            {
                "iss": ISSUER,
                "aud": CLIENT,
                "sub": "account-1",
                "iat": now,
                "exp": now + 900,
                "tenant": "tenant-a",
                "tenant_slug": "ff-a",
                "mitgliedschaft": "m-1",
                "mitglied": None,
                "name": "Anna Example",
                "preferred_username": "anna",
                "module": ["counterpart"],
                "rollen": {"counterpart": ["reader"]},
                **claims,
            },
            self.private,
            algorithm="RS256",
        )


@pytest.fixture
def keys() -> Keys:
    return Keys()


@pytest.fixture
def verifier(keys) -> TokenVerifier:
    return TokenVerifier(ISSUER, CLIENT, jwks_client=keys)
