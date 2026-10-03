import json

from fastapi.testclient import TestClient

from ff_platform_sdk import internal
from ff_platform_sdk.testing.counterpart import Counterpart

SECRET = "very-secret"


def signed(client: TestClient, method: str, path: str, data=None, secret=SECRET):
    body = b"" if data is None else json.dumps(data).encode()
    headers = internal.headers(secret, method, path, body)
    return client.request(method, path, content=body, headers=headers)


def event(entity, typ="upsert", tenant="tenant-a", **payload):
    return {"id": 1, "tenant": tenant, "entitaet": entity, "typ": typ, "nutzlast": payload}


def test_internal_endpoints_only_with_signature():
    client = TestClient(Counterpart(SECRET).app)
    assert client.get("/intern/manifest").status_code == 401
    assert signed(client, "GET", "/intern/manifest", secret="wrong").status_code == 401
    assert signed(client, "GET", "/intern/manifest").json()["schluessel"] == "counterpart"


def test_sync_upsert_removed_reconcile_revoke():
    c = Counterpart(SECRET)
    client = TestClient(c.app)
    assert signed(
        client, "POST", "/intern/mandant-init", {"tenant": {"id": "tenant-a"}}
    ).json() == {"ok": True}
    assert c.mirror.initialized == [{"id": "tenant-a"}]

    response = signed(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "bis": 7,
            "ereignisse": [
                event("mitglied", id="m1", nachname="Auer", version=2),
                event("mitglied", id="m2", nachname="Bauer", version=1),
                event("mitglied", id="m1", nachname="Alt", version=1),  # late and older
                event("mitglied", tenant="tenant-b", id="x1", nachname="Fremd", version=1),
            ],
        },
    )
    assert response.json() == {"bestaetigt": 7}
    assert {m["nachname"] for m in c.mirror.delivered("tenant-a", "mitglied")} == {"Auer", "Bauer"}
    assert [m["nachname"] for m in c.mirror.delivered("tenant-b", "mitglied")] == ["Fremd"]

    # "entfernt" marks the record but does not delete it
    signed(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "ereignisse": [event("mitglied", typ="entfernt", id="m2")],
        },
    )
    assert [m["id"] for m in c.mirror.delivered("tenant-a", "mitglied")] == ["m1"]
    assert "m2" in c.mirror.table("tenant-a", "mitglied")

    # full reconcile: m1 is not in the target set → no longer delivered; m3 is added;
    # tenant B stays untouched
    signed(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "abgleich": {"tenant": "tenant-a", "vollstaendig": {"mitglied": ["m3"]}},
            "ereignisse": [event("mitglied", id="m3", nachname="Czerny", version=1)],
        },
    )
    assert [m["id"] for m in c.mirror.delivered("tenant-a", "mitglied")] == ["m3"]
    assert len(c.mirror.delivered("tenant-b", "mitglied")) == 1

    signed(
        client,
        "POST",
        "/intern/stammdaten",
        {
            "ereignisse": [event("widerruf", art="benutzer_gesperrt", mitgliedschaft="ms-1")],
        },
    )
    assert c.mirror.revocations == [
        {"tenant": "tenant-a", "art": "benutzer_gesperrt", "mitgliedschaft": "ms-1"}
    ]


def test_token_protected_endpoint(verifier, keys):
    client = TestClient(Counterpart(SECRET, verifier=verifier).app)
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    me = client.get("/me", headers={"Authorization": f"Bearer {keys.token()}"}).json()
    assert me["tenant_slug"] == "ff-a" and me["roles"] == {"counterpart": ["reader"]}
