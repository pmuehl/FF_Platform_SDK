import json

from fastapi.testclient import TestClient

from ff_platform_sdk import intern
from ff_platform_sdk.testing.gegenstelle import Gegenstelle

GEHEIMNIS = "sehr-geheim"


def signiert(client: TestClient, methode: str, pfad: str, daten=None, geheimnis=GEHEIMNIS):
    body = b"" if daten is None else json.dumps(daten).encode()
    kopf = intern.kopfzeilen(geheimnis, methode, pfad, body)
    return client.request(methode, pfad, content=body, headers=kopf)


def ereignis(entitaet, typ="upsert", tenant="tenant-a", **nutzlast):
    return {"id": 1, "tenant": tenant, "entitaet": entitaet, "typ": typ, "nutzlast": nutzlast}


def test_interne_endpunkte_nur_mit_signatur():
    client = TestClient(Gegenstelle(GEHEIMNIS).app)
    assert client.get("/intern/manifest").status_code == 401
    assert signiert(client, "GET", "/intern/manifest", geheimnis="falsch").status_code == 401
    assert signiert(client, "GET", "/intern/manifest").json()["schluessel"] == "gegenstelle"


def test_sync_upsert_entfernt_abgleich_widerruf():
    g = Gegenstelle(GEHEIMNIS)
    client = TestClient(g.app)
    assert signiert(
        client, "POST", "/intern/mandant-init", {"tenant": {"id": "tenant-a"}}
    ).json() == {"ok": True}
    assert g.spiegel.eingerichtet == [{"id": "tenant-a"}]

    antwort = signiert(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "bis": 7,
            "ereignisse": [
                ereignis("mitglied", id="m1", nachname="Auer", version=2),
                ereignis("mitglied", id="m2", nachname="Bauer", version=1),
                ereignis("mitglied", id="m1", nachname="Alt", version=1),  # verspätet, älter
                ereignis("mitglied", tenant="tenant-b", id="x1", nachname="Fremd", version=1),
            ],
        },
    )
    assert antwort.json() == {"bestaetigt": 7}
    assert {m["nachname"] for m in g.spiegel.geliefert("tenant-a", "mitglied")} == {"Auer", "Bauer"}
    assert [m["nachname"] for m in g.spiegel.geliefert("tenant-b", "mitglied")] == ["Fremd"]

    # „entfernt" markiert, löscht aber nicht
    signiert(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "ereignisse": [ereignis("mitglied", typ="entfernt", id="m2")],
        },
    )
    assert [m["id"] for m in g.spiegel.geliefert("tenant-a", "mitglied")] == ["m1"]
    assert "m2" in g.spiegel.tabelle("tenant-a", "mitglied")

    # Voll-Abgleich: m1 fehlt im Soll → nicht mehr geliefert; m3 kommt dazu; B bleibt unberührt
    signiert(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "abgleich": {"tenant": "tenant-a", "vollstaendig": {"mitglied": ["m3"]}},
            "ereignisse": [ereignis("mitglied", id="m3", nachname="Czerny", version=1)],
        },
    )
    assert [m["id"] for m in g.spiegel.geliefert("tenant-a", "mitglied")] == ["m3"]
    assert len(g.spiegel.geliefert("tenant-b", "mitglied")) == 1

    signiert(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "ereignisse": [ereignis("widerruf", art="benutzer_gesperrt", mitgliedschaft="ms-1")],
        },
    )
    assert g.spiegel.widerrufe == [
        {"tenant": "tenant-a", "art": "benutzer_gesperrt", "mitgliedschaft": "ms-1"}
    ]


def test_token_geschuetzter_endpunkt(pruefer, schluessel):
    client = TestClient(Gegenstelle(GEHEIMNIS, pruefer=pruefer).app)
    assert client.get("/ich").status_code == 401
    assert client.get("/ich", headers={"Authorization": "Bearer unsinn"}).status_code == 401
    ich = client.get("/ich", headers={"Authorization": f"Bearer {schluessel.token()}"}).json()
    assert ich["tenant_slug"] == "ff-a" and ich["rollen"] == {"gegenstelle": ["leser"]}
