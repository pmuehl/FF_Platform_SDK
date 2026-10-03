"""HMAC signature of the internal calls between platform and app.

The platform calls `/intern/*` only inside the internal network. The signature
guards against a route that was exposed by mistake: timestamp, method, path and
body are signed; calls outside the time window are rejected (replay
protection). Counterpart: `apps/sync/signatur.py` in the platform.
"""

import hashlib
import hmac
import time

HEADER_TIMESTAMP = "X-FFP-Zeitstempel"
HEADER_SIGNATURE = "X-FFP-Signatur"
WINDOW_SECONDS = 300


def sign(secret: str, timestamp: str, method: str, path: str, body: bytes) -> str:
    message = f"{timestamp}.{method.upper()}.{path}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def headers(secret: str, method: str, path: str, body: bytes = b"") -> dict[str, str]:
    timestamp = str(int(time.time()))
    return {
        HEADER_TIMESTAMP: timestamp,
        HEADER_SIGNATURE: sign(secret, timestamp, method, path, body),
    }


def verify(
    secret: str,
    method: str,
    path: str,
    body: bytes,
    timestamp: str | None,
    given: str | None,
    *,
    now: float | None = None,
) -> bool:
    try:
        if abs((now or time.time()) - int(timestamp or "")) > WINDOW_SECONDS:
            return False
    except ValueError:
        return False
    expected = sign(secret, timestamp or "", method, path, body)
    return hmac.compare_digest(expected, given or "")
