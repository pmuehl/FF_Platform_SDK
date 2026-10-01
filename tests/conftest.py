import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from ff_platform_sdk.auth import TokenPruefer

AUSSTELLER = "https://platform.test/o"
CLIENT = "gegenstelle"


class Schluessel:
    """Ersetzt den JWKS-Abruf: liefert den öffentlichen Schlüssel der Test-Plattform."""

    def __init__(self):
        self.privat = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def get_signing_key_from_jwt(self, token):
        class Ergebnis:
            key = self.privat.public_key()

        return Ergebnis()

    def token(self, **claims) -> str:
        jetzt = int(time.time())
        return jwt.encode(
            {
                "iss": AUSSTELLER,
                "aud": CLIENT,
                "sub": "konto-1",
                "iat": jetzt,
                "exp": jetzt + 900,
                "tenant": "tenant-a",
                "tenant_slug": "ff-a",
                "mitgliedschaft": "m-1",
                "mitglied": None,
                "name": "Anna Beispiel",
                "preferred_username": "anna",
                "module": ["gegenstelle"],
                "rollen": {"gegenstelle": ["leser"]},
                **claims,
            },
            self.privat,
            algorithm="RS256",
        )


@pytest.fixture
def schluessel() -> Schluessel:
    return Schluessel()


@pytest.fixture
def pruefer(schluessel) -> TokenPruefer:
    return TokenPruefer(AUSSTELLER, CLIENT, jwks_client=schluessel)
