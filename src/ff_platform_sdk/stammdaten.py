"""Empfänger des Stammdaten-Syncs (Plattform → App).

Die Plattform liefert Änderungen an `POST /intern/stammdaten`:

    {"ereignisse": [{"id": 42, "tenant": "…", "entitaet": "mitglied",
                     "typ": "upsert", "nutzlast": {...}}, …], "bis": 57}

- `upsert`    Datensatz anlegen oder ersetzen (die ID ist die der Plattform).
              Ältere Stände als der vorhandene werden ignoriert (`version`).
- `entfernt`  Datensatz wird nicht mehr geliefert (aus dem Filter gefallen oder
              gelöscht) — markieren, nicht löschen: Fachdaten verweisen darauf.
- `abgleich`  Voll-Abgleich einer Feuerwehr: Alles, was nicht in `vollstaendig`
              steht, gilt als nicht mehr geliefert.
- Entität `widerruf`: Benutzer gesperrt, Rolle entzogen, Modul abgeschaltet —
              die App beendet betroffene Sitzungen sofort.

Zustellung ist „mindestens einmal": Der Empfänger muss idempotent sein.
Die App bringt ihren eigenen `Spiegel` mit (Tabellen in ihrer Datenbank);
`SpiegelImSpeicher` ist die Referenz für Tests.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


class Spiegel(Protocol):
    def upsert(self, tenant: str | None, entitaet: str, daten: dict[str, Any]) -> None: ...

    def entfernt(self, tenant: str | None, entitaet: str, datensatz_id: str) -> None: ...

    def abgleich(self, tenant: str, entitaet: str, gueltige_ids: set[str]) -> None: ...

    def widerruf(self, tenant: str | None, daten: dict[str, Any]) -> None: ...

    def mandant_init(self, tenant: dict[str, Any]) -> None: ...


def verarbeite(spiegel: Spiegel, daten: dict[str, Any]) -> dict[str, Any]:
    """Wendet eine Lieferung auf den Spiegel an und gibt die Bestätigung zurück."""
    for ereignis in daten.get("ereignisse", []):
        tenant, entitaet, nutzlast = (
            ereignis.get("tenant"),
            ereignis["entitaet"],
            ereignis["nutzlast"],
        )
        if entitaet == "widerruf":
            spiegel.widerruf(tenant, nutzlast)
        elif ereignis["typ"] == "entfernt":
            spiegel.entfernt(tenant, entitaet, nutzlast["id"])
        else:
            spiegel.upsert(tenant, entitaet, nutzlast)
    abgleich = daten.get("abgleich")
    if abgleich:
        for entitaet, ids in abgleich["vollstaendig"].items():
            spiegel.abgleich(abgleich["tenant"], entitaet, set(ids))
    return {"bestaetigt": daten.get("bis")}


@dataclass
class SpiegelImSpeicher:
    """Referenz-Spiegel im Arbeitsspeicher — für Tests und die Test-Gegenstelle."""

    # (tenant, entitaet) → {id: Datensatz}; Kataloge liegen unter tenant None
    daten: dict[tuple[str | None, str], dict[str, dict[str, Any]]] = field(default_factory=dict)
    nicht_mehr_geliefert: set[tuple[str | None, str, str]] = field(default_factory=set)
    widerrufe: list[dict[str, Any]] = field(default_factory=list)
    eingerichtet: list[dict[str, Any]] = field(default_factory=list)

    def tabelle(self, tenant: str | None, entitaet: str) -> dict[str, dict[str, Any]]:
        return self.daten.setdefault((tenant, entitaet), {})

    def geliefert(self, tenant: str | None, entitaet: str) -> list[dict[str, Any]]:
        """Datensätze, die aktuell geliefert werden."""
        return [
            d
            for i, d in self.tabelle(tenant, entitaet).items()
            if (tenant, entitaet, i) not in self.nicht_mehr_geliefert
        ]

    def upsert(self, tenant, entitaet, daten):
        tabelle = self.tabelle(tenant, entitaet)
        vorhanden = tabelle.get(daten["id"])
        # `version` als Schutz gegen verspätete, ältere Zustellungen
        if vorhanden and vorhanden.get("version", 0) > daten.get("version", 0):
            return
        tabelle[daten["id"]] = daten
        self.nicht_mehr_geliefert.discard((tenant, entitaet, daten["id"]))

    def entfernt(self, tenant, entitaet, datensatz_id):
        if datensatz_id in self.tabelle(tenant, entitaet):
            self.nicht_mehr_geliefert.add((tenant, entitaet, datensatz_id))

    def abgleich(self, tenant, entitaet, gueltige_ids):
        for datensatz_id in self.tabelle(tenant, entitaet):
            if datensatz_id not in gueltige_ids:
                self.nicht_mehr_geliefert.add((tenant, entitaet, datensatz_id))

    def widerruf(self, tenant, daten):
        self.widerrufe.append({"tenant": tenant, **daten})

    def mandant_init(self, tenant):
        self.eingerichtet.append(tenant)
