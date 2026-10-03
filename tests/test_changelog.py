import json

import pytest
from fastapi.testclient import TestClient

from ff_platform_sdk import internal
from ff_platform_sdk.changelog import Changelog, parse
from ff_platform_sdk.testing.counterpart import Counterpart

FILE = """# Changelog

Intro that does not count.
- neither does this item

## 1.4.0 — 2026-10-03: Alarmliste
### Neu
- Die Alarmliste zeigt jetzt
  auch die Reserve.
### Fixed
* Fahrzeuge ohne Funkrufnamen fehlten.

## v1.3.2 (2026-09-01)
- Kleinere Verbesserungen.

## not a version
- ignored? No: belongs to 1.3.2.
"""


def test_parse():
    new, old = parse(FILE)
    assert new == {
        "version": "1.4.0",
        "datum": "2026-10-03",
        "titel": "Alarmliste",
        "punkte": [
            {"art": "neu", "text": "Die Alarmliste zeigt jetzt auch die Reserve."},
            {"art": "behoben", "text": "Fahrzeuge ohne Funkrufnamen fehlten."},
        ],
    }
    assert (old["version"], old["datum"], old["titel"]) == ("1.3.2", "2026-09-01", "")
    assert [p["art"] for p in old["punkte"]] == ["geaendert", "geaendert"]


def test_from_files(tmp_path, monkeypatch):
    monkeypatch.delenv("BUILD_ID", raising=False)
    (tmp_path / "VERSION").write_text("1.4.0\n")
    (tmp_path / "CHANGELOG.md").write_text(FILE)
    (tmp_path / "BUILD").write_text("20261003120000\n")
    changelog = Changelog.from_files(tmp_path)
    assert changelog.as_response() == {
        "version": "1.4.0",
        "build": "20261003120000",
        "eintraege": parse(FILE),
    }
    monkeypatch.setenv("BUILD_ID", "from-env")
    assert Changelog.from_files(tmp_path).build == "from-env"
    assert Changelog.from_files(tmp_path, build="explicit").build == "explicit"

    (tmp_path / "VERSION").write_text("1.4\n")
    with pytest.raises(ValueError, match="ww.xx.yy"):
        Changelog.from_files(tmp_path)


def test_endpoint_is_signed_and_optional():
    def get(counterpart, sign=True):
        headers = internal.headers("s", "GET", "/intern/changelog") if sign else {}
        return TestClient(counterpart.app).get("/intern/changelog", headers=headers)

    assert get(Counterpart("s"), sign=False).status_code == 401
    body = get(Counterpart("s")).json()
    assert body["version"] == "1.1.0" and body["build"] == "build-1"
    assert [e["version"] for e in body["eintraege"]] == ["1.1.0", "1.0.0"]
    assert json.dumps(body)  # plain JSON
    assert get(Counterpart("s", changelog=None)).status_code == 404
