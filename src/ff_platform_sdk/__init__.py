"""SDK der FF Plattform für die angebundenen Apps (Dashboard, Einsatzleitung, wiki_tickets).

v0.1 enthält, was die Plattform in Phase 2 abnimmt:

- `auth`        Prüfung des ID-Tokens der Plattform über JWKS → `AngemeldeterBenutzer`
- `intern`      HMAC-Signatur der internen Aufrufe (/intern/*)
- `stammdaten`  Empfänger des Stammdaten-Syncs (Upsert, „nicht mehr geliefert", Abgleich, Widerruf)
- `fastapi`     Abhängigkeiten und Router für FastAPI-Apps
- `testing`     Test-Gegenstelle, gegen die die Plattform ihren Sync prüft

Mandanten-Kontext, ORM-Filter, Freischaltungs-Prüfung und die Leck-Test-Suite
kommen mit der Umstellung der ersten App (Phase 1 und 3).
"""

__version__ = "0.1.0"
