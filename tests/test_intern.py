import time

from ff_platform_sdk import intern


def test_signatur_passt_nur_zu_methode_pfad_und_body():
    kopf = intern.kopfzeilen("geheim", "POST", "/intern/stammdaten", b'{"a":1}')
    args = (kopf[intern.KOPF_ZEIT], kopf[intern.KOPF_SIGNATUR])
    assert intern.pruefen("geheim", "POST", "/intern/stammdaten", b'{"a":1}', *args)
    assert not intern.pruefen("anders", "POST", "/intern/stammdaten", b'{"a":1}', *args)
    assert not intern.pruefen("geheim", "GET", "/intern/stammdaten", b'{"a":1}', *args)
    assert not intern.pruefen("geheim", "POST", "/intern/manifest", b'{"a":1}', *args)
    assert not intern.pruefen("geheim", "POST", "/intern/stammdaten", b'{"a":2}', *args)


def test_alte_aufrufe_werden_verworfen():
    alt = str(int(time.time()) - intern.FENSTER - 5)
    signatur = intern.signatur("geheim", alt, "POST", "/x", b"")
    assert not intern.pruefen("geheim", "POST", "/x", b"", alt, signatur)
    assert not intern.pruefen("geheim", "POST", "/x", b"", None, None)
    assert not intern.pruefen("geheim", "POST", "/x", b"", "keine-zahl", signatur)
