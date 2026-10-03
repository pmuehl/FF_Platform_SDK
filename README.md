# FF_Platform_SDK

Python package `ff-platform-sdk` (import `ff_platform_sdk`): connects the FF apps
(Dashboard, Einsatzleitung, wiki_tickets) to the **FF Platform**, the
multi-tenant platform for volunteer fire brigades.

**Status: v0.1** — the parts the platform verifies in its acceptance test.

| Module | Contents |
| --- | --- |
| `auth` | Verify the platform's ID token (RS256 via JWKS) → `AuthenticatedUser` with fire brigade, modules and roles |
| `internal` | HMAC signature of the internal calls (`/intern/*`) with a time window against replay |
| `master_data` | Receiver of the master data sync: upsert, "no longer delivered", full reconcile, revocation |
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
    "ff-platform-sdk[fastapi] @ git+https://github.com/pmuehl/FF_Platform_SDK.git@v0.1.0",
]
```

```python
from ff_platform_sdk.auth import TokenVerifier
from ff_platform_sdk.fastapi import current_user, internal_router, require_role

verifier = TokenVerifier("https://platform.alarmboard.at/o", client_id="dashboard")
user = current_user(verifier)

@app.get("/api/vehicles")
def vehicles(u = Depends(require_role(user, "dashboard"))):
    ...  # u.tenant is the fire brigade — only this verified claim counts

app.include_router(
    internal_router(secret=INTERNAL_SECRET, manifest=MANIFEST, mirror=MyMirror())
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
