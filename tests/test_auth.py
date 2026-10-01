import time

import pytest

from ff_platform_sdk.auth import TokenFehler

from .conftest import Schluessel


def test_gueltiges_token_ergibt_den_benutzer(pruefer, schluessel):
    b = pruefer.pruefe(schluessel.token())
    assert (b.tenant, b.tenant_slug, b.benutzername) == ("tenant-a", "ff-a", "anna")
    assert b.hat_modul("gegenstelle") and not b.hat_modul("wiki")
    assert b.hat_rolle("gegenstelle", "leser", "admin")
    assert not b.hat_rolle("gegenstelle", "admin")
    assert not b.hat_rolle("wiki")


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": int(time.time()) - 600},  # abgelaufen
        {"aud": "andere-app"},  # für eine andere App ausgestellt
        {"iss": "https://boese.test/o"},  # fremder Aussteller
    ],
)
def test_ungueltige_tokens(pruefer, schluessel, claims):
    with pytest.raises(TokenFehler):
        pruefer.pruefe(schluessel.token(**claims))


def test_fremde_signatur_und_fehlendes_token(pruefer):
    with pytest.raises(TokenFehler):
        pruefer.pruefe(Schluessel().token())  # mit einem anderen Schlüssel signiert
    with pytest.raises(TokenFehler):
        pruefer.pruefe(None)
    with pytest.raises(TokenFehler):
        pruefer.pruefe("kein.jwt")
