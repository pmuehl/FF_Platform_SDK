import time

from ff_platform_sdk import internal


def test_signature_only_matches_method_path_and_body():
    headers = internal.headers("secret", "POST", "/intern/stammdaten", b'{"a":1}')
    args = (headers[internal.HEADER_TIMESTAMP], headers[internal.HEADER_SIGNATURE])
    assert internal.verify("secret", "POST", "/intern/stammdaten", b'{"a":1}', *args)
    assert not internal.verify("other", "POST", "/intern/stammdaten", b'{"a":1}', *args)
    assert not internal.verify("secret", "GET", "/intern/stammdaten", b'{"a":1}', *args)
    assert not internal.verify("secret", "POST", "/intern/manifest", b'{"a":1}', *args)
    assert not internal.verify("secret", "POST", "/intern/stammdaten", b'{"a":2}', *args)


def test_old_calls_are_rejected():
    old = str(int(time.time()) - internal.WINDOW_SECONDS - 5)
    signature = internal.sign("secret", old, "POST", "/x", b"")
    assert not internal.verify("secret", "POST", "/x", b"", old, signature)
    assert not internal.verify("secret", "POST", "/x", b"", None, None)
    assert not internal.verify("secret", "POST", "/x", b"", "not-a-number", signature)
