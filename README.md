# FF_Platform_SDK

Python-Paket `ff-platform-sdk` (Import `ff_platform_sdk`): bindet die FF-Apps
(Dashboard, Einsatzleitung, wiki_tickets) an die **FF Plattform** an.
Konzept: `FF_Platform/docs/mandantenfaehigkeit-plattform.md`, Kapitel 9.

**Stand: v0.1** — was die Plattform in Phase 2 abnimmt.

| Baustein | Inhalt |
| --- | --- |
| `auth` | ID-Token der Plattform prüfen (RS256 über JWKS) → `AngemeldeterBenutzer` mit Feuerwehr, Modulen, Rollen |
| `intern` | HMAC-Signatur der internen Aufrufe (`/intern/*`) mit Zeitfenster gegen Wiederholung |
| `stammdaten` | Empfänger des Stammdaten-Syncs: Upsert, „nicht mehr geliefert", Voll-Abgleich, Widerruf |
| `fastapi` | Abhängigkeiten (`aktueller_benutzer`, `require_rolle`) und Router für `/intern/*` |
| `testing.gegenstelle` | Test-Gegenstelle: verhält sich wie ein angebundenes Modul; die Plattform prüft damit ihren Sync |

Noch nicht enthalten (kommt mit der Umstellung der ersten App, Phase 1 und 3):
Mandanten-Kontext und ORM-Filter (`tenant`, `orm`), Freischaltungs-Prüfung
(`entitlements`), Spiegel-Tabellen für SQLAlchemy, Schreib-Client für die
Stammdaten-API, die generische Leck-Test-Suite.

## Einbinden

```toml
# pyproject.toml der App
dependencies = [
    "ff-platform-sdk[fastapi] @ git+https://github.com/pmuehl/FF_Platform_SDK.git@v0.1.0",
]
```

```python
from ff_platform_sdk.auth import TokenPruefer
from ff_platform_sdk.fastapi import aktueller_benutzer, intern_router, require_rolle

pruefer = TokenPruefer("https://platform.alarmboard.at/o", client_id="dashboard")
benutzer = aktueller_benutzer(pruefer)

@app.get("/api/fahrzeuge")
def fahrzeuge(b = Depends(require_rolle(benutzer, "dashboard"))):
    ...  # b.tenant ist die Feuerwehr — maßgeblich ist nur dieser geprüfte Claim

app.include_router(
    intern_router(geheimnis=INTERN_GEHEIMNIS, manifest=MANIFEST, spiegel=MeinSpiegel())
)
```

- **Geheimnis:** steht in der Plattform unter Admin → Module → Modul →
  „Geheimnis für interne Aufrufe". In der App als Umgebungsvariable.
- **`/intern/*` darf nicht nach außen geroutet werden** (Traefik). Die Signatur
  ist die zweite Sicherung, nicht die erste.
- **Spiegel:** Die App implementiert das Protokoll `stammdaten.Spiegel` mit ihren
  eigenen Tabellen. Die ID jedes Datensatzes ist die der Plattform. „Entfernt"
  heißt markieren, nicht löschen — Fachdaten verweisen darauf.
- **401** nur bei fehlendem, abgelaufenem oder ungültigem Token. Modul nicht
  zugänglich → 404, falsche Rolle → 403.

## Entwickeln

```bash
uv venv -p 3.14 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Die Plattform prüft das SDK in ihrem Abnahmetest mit
(`FF_Platform/backend/tests/test_sdk_gegenstelle.py`, dort `make sdk`).
