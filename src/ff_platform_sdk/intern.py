"""HMAC-Signatur der internen Aufrufe zwischen Plattform und App.

Die Plattform ruft `/intern/*` nur im internen Netz auf. Die Signatur sichert
gegen eine versehentlich doch nach außen geroutete Route ab: Signiert sind
Zeitstempel, Methode, Pfad und Body; Aufrufe außerhalb des Zeitfensters werden
verworfen (Replay-Schutz). Gegenstück: `apps/sync/signatur.py` der Plattform.
"""

import hashlib
import hmac
import time

KOPF_ZEIT = "X-FFP-Zeitstempel"
KOPF_SIGNATUR = "X-FFP-Signatur"
FENSTER = 300  # Sekunden


def signatur(geheimnis: str, zeitstempel: str, methode: str, pfad: str, body: bytes) -> str:
    nachricht = f"{zeitstempel}.{methode.upper()}.{pfad}.".encode() + body
    return hmac.new(geheimnis.encode(), nachricht, hashlib.sha256).hexdigest()


def kopfzeilen(geheimnis: str, methode: str, pfad: str, body: bytes = b"") -> dict[str, str]:
    zeitstempel = str(int(time.time()))
    return {
        KOPF_ZEIT: zeitstempel,
        KOPF_SIGNATUR: signatur(geheimnis, zeitstempel, methode, pfad, body),
    }


def pruefen(
    geheimnis: str,
    methode: str,
    pfad: str,
    body: bytes,
    zeitstempel: str | None,
    gegeben: str | None,
    *,
    jetzt: float | None = None,
) -> bool:
    try:
        if abs((jetzt or time.time()) - int(zeitstempel or "")) > FENSTER:
            return False
    except ValueError:
        return False
    erwartet = signatur(geheimnis, zeitstempel or "", methode, pfad, body)
    return hmac.compare_digest(erwartet, gegeben or "")
