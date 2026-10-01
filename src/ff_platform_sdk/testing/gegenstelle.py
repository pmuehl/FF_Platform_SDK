"""Test-Gegenstelle: eine kleine App, die sich wie ein angebundenes Modul verhält.

Die Plattform prüft damit in ihren Tests den ganzen Weg: Manifest abholen,
Modul freischalten (mandant-init), Stammdaten zustellen, Token prüfen.

    gegenstelle = Gegenstelle(geheimnis="…", manifest={...})
    client = TestClient(gegenstelle.app)
"""

from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, FastAPI

from ..auth import AngemeldeterBenutzer, TokenPruefer
from ..fastapi import aktueller_benutzer, intern_router
from ..stammdaten import SpiegelImSpeicher

MANIFEST: dict[str, Any] = {
    "schluessel": "gegenstelle",
    "name": "Test-Gegenstelle",
    "eltern_modul": None,
    "manifest_version": 1,
    "rollen": {
        "auswahl": "eine",
        "werte": [
            {"schluessel": "leser", "name": "Leser"},
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


@dataclass
class Gegenstelle:
    geheimnis: str
    manifest: dict[str, Any] = field(default_factory=lambda: dict(MANIFEST))
    pruefer: TokenPruefer | None = None
    spiegel: SpiegelImSpeicher = field(default_factory=SpiegelImSpeicher)

    def __post_init__(self) -> None:
        self.app = FastAPI(title="FF Plattform — Test-Gegenstelle")
        self.app.include_router(
            intern_router(
                geheimnis=self.geheimnis, manifest=lambda: self.manifest, spiegel=self.spiegel
            )
        )
        if self.pruefer is not None:
            benutzer = aktueller_benutzer(self.pruefer)

            @self.app.get("/ich")
            def ich(b: AngemeldeterBenutzer = Depends(benutzer)) -> dict[str, Any]:  # noqa: B008
                """Was die App über den angemeldeten Benutzer weiß — nur aus dem Token."""
                return {
                    "name": b.name,
                    "tenant": b.tenant,
                    "tenant_slug": b.tenant_slug,
                    "module": list(b.module),
                    "rollen": {m: list(r) for m, r in b.rollen.items()},
                }
