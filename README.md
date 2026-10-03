# FF_Platform_SDK

Python package `ff-platform-sdk` (import `ff_platform_sdk`): connects the FF apps
(Dashboard, Einsatzleitung, wiki_tickets) to the **FF Platform**, the
multi-tenant platform for volunteer fire brigades.

**Status: v0.2** — the parts the platform verifies in its acceptance test.

| Module | Contents |
| --- | --- |
| `auth` | Verify the platform's ID token (RS256 via JWKS) → `AuthenticatedUser` with fire brigade, modules and roles |
| `internal` | HMAC signature of the internal calls (`/intern/*`) with a time window against replay |
| `master_data` | Receiver of the master data sync: upsert, "no longer delivered", full reconcile, revocation |
| `changelog` | Version and changelog of the app (`VERSION`, `CHANGELOG.md`), fetched and shown by the platform |
| `fastapi` | Dependencies (`current_user`, `require_role`) and the router for `/intern/*` |
| `testing.counterpart` | Test counterpart: behaves like a connected module; the platform tests its sync against it |

Not included yet (comes with the migration of the first app):
tenant context and ORM filter (`tenant`, `orm`), entitlement checks
(`entitlements`), mirror tables for SQLAlchemy, a write client for the
master data API, the generic tenant leak test suite.

## Usage

```toml
# pyproject.toml of the app
dependencies = [
    "ff-platform-sdk[fastapi] @ git+https://github.com/pmuehl/FF_Platform_SDK.git@v0.2.0",
]
```

```python
from ff_platform_sdk.auth import TokenVerifier
from ff_platform_sdk.changelog import Changelog
from ff_platform_sdk.fastapi import current_user, internal_router, require_role

verifier = TokenVerifier("https://platform.alarmboard.at/o", client_id="dashboard")
user = current_user(verifier)

@app.get("/api/vehicles")
def vehicles(u = Depends(require_role(user, "dashboard"))):
    ...  # u.tenant is the fire brigade — only this verified claim counts

app.include_router(
    internal_router(
        secret=INTERNAL_SECRET,
        manifest=MANIFEST,
        mirror=MyMirror(),
        changelog=Changelog.from_files("."),  # VERSION, CHANGELOG.md, BUILD
    )
)
```

- **Secret:** shown in the platform under Admin → Module → the module →
  "Geheimnis für interne Aufrufe". Pass it to the app as an environment variable.
- **`/intern/*` must not be routed to the outside** (Traefik). The signature is
  the second line of defence, not the first.
- **Mirror:** the app implements the `master_data.Mirror` protocol with its own
  tables. The ID of every record is the platform's ID. "Removed" means mark,
  not delete — the app's own data refers to these records.
- **401** only for a missing, expired or invalid token. Module not accessible
  → 404, wrong role → 403.

## Version and changelog

Every app has a version `ww.xx.yy.zzz`: major changes, moderate changes, small
changes or bug fixes, and a build counter.

- `VERSION` in the app's repository holds `ww.xx.yy`, e.g. `1.4.0`.
- `zzz` is counted by the platform: it goes up by one whenever the app reports
  a new version or a new build ID. The build ID comes from the environment
  variable `BUILD_ID` or a file `BUILD`; write it in the Dockerfile after
  copying the sources: `RUN date -u +%Y%m%d%H%M%S > BUILD`.
- `CHANGELOG.md` describes each version for the fire brigades, in German:

  ```markdown
  ## 1.4.0 — 2026-10-03: Alarmliste
  ### Neu
  - Die Alarmliste zeigt jetzt auch die Reserve.
  ### Behoben
  - Fahrzeuge ohne Funkrufnamen fehlten.
  ```

  Sections: `Neu`, `Geändert`, `Behoben`. One entry per version.

The platform fetches `GET /intern/changelog` regularly and shows the entries to
every fire brigade that has the module enabled. New versions are visible at
once; the platform admin can edit or hide them there.

## Wire format

The Python API is English. The wire format is defined by the platform and uses
German names; the SDK passes them through unchanged:

- ID token claims: `tenant`, `tenant_slug`, `mitgliedschaft` (membership),
  `mitglied` (member), `module` (modules), `rollen` (roles)
- Headers: `X-FFP-Zeitstempel` (timestamp), `X-FFP-Signatur` (signature)
- Sync payload: `ereignisse` (events), `entitaet` (entity), `typ` (type:
  `upsert` or `entfernt`), `nutzlast` (payload), `bis` (up to),
  `abgleich` (reconcile), `vollstaendig` (complete), `bestaetigt` (acknowledged)
- Entities: `mitglied`, `fahrzeug` (vehicle), `zug` (platoon), `benutzer` (user),
  `katalog_version`, `widerruf` (revocation)
- Changelog: `version`, `build`, `eintraege` (entries) with `version`, `datum`
  (date), `titel` (title), `punkte` (items: `art` = `neu`/`geaendert`/`behoben`, `text`)
- Manifest keys: `schluessel` (key), `rollen`, `standard_konten`,
  `schreibrechte`, `stammdaten_abos`, `modul_attribute`

## Development

```bash
uv venv -p 3.14 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The platform runs the SDK in its acceptance test
(`FF_Platform/backend/tests/test_sdk_gegenstelle.py`, `make sdk` there).
