"""Test counterpart: a small app that behaves like a connected module.

The platform uses it in its tests to cover the whole path: fetch the manifest,
enable the module (mandant-init), deliver master data, verify the token.

    counterpart = Counterpart(secret="…", manifest={...})
    client = TestClient(counterpart.app)
"""

from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, FastAPI

from ..auth import AuthenticatedUser, TokenVerifier
from ..changelog import Changelog, parse
from ..fastapi import current_user, internal_router
from ..master_data import InMemoryMirror

# manifest keys and filter values are the platform's wire format
MANIFEST: dict[str, Any] = {
    "schluessel": "counterpart",
    "name": "Test counterpart",
    "eltern_modul": None,
    "manifest_version": 1,
    "rollen": {
        "auswahl": "eine",
        "werte": [
            {"schluessel": "reader", "name": "Reader"},
            {"schluessel": "admin", "name": "Admin"},
        ],
    },
    "standard_konten": [],
    "schreibrechte": {"mitglied": ["admin"], "fahrzeug": ["admin"]},
    "stammdaten_abos": {
        "mitglied": {"zugehoerigkeit": ["aktiv", "reserve", "zivildienst"]},
        "fahrzeug": {},
        "zug": {},
        "benutzer": {},
        "kataloge": ["dienstgrade"],
    },
    "modul_attribute": {},
}

CHANGELOG = """\
## 1.1.0 — 2026-10-03: Zweite Version
### Neu
- Die Gegenstelle liefert ihren Changelog.
### Behoben
- Ein Fehler,
  der über zwei Zeilen beschrieben ist.

## 1.0.0 — 2026-09-01
- Erste Version.
"""


@dataclass
class Counterpart:
    secret: str
    manifest: dict[str, Any] = field(default_factory=lambda: dict(MANIFEST))
    verifier: TokenVerifier | None = None
    mirror: InMemoryMirror = field(default_factory=InMemoryMirror)
    changelog: Changelog | None = field(
        default_factory=lambda: Changelog("1.1.0", parse(CHANGELOG), build="build-1")
    )

    def __post_init__(self) -> None:
        self.app = FastAPI(title="FF Platform — test counterpart")
        self.app.include_router(
            internal_router(
                secret=self.secret,
                manifest=lambda: self.manifest,
                mirror=self.mirror,
                changelog=self.changelog,
            )
        )
        if self.verifier is not None:
            user = current_user(self.verifier)

            @self.app.get("/me")
            def me(u: AuthenticatedUser = Depends(user)) -> dict[str, Any]:  # noqa: B008
                """What the app knows about the signed-in user — from the token only."""
                return {
                    "name": u.name,
                    "tenant": u.tenant,
                    "tenant_slug": u.tenant_slug,
                    "modules": list(u.modules),
                    "roles": {m: list(r) for m, r in u.roles.items()},
                }
