import time

import pytest

from ff_platform_sdk.auth import TokenError

from .conftest import Keys


def test_valid_token_yields_the_user(verifier, keys):
    u = verifier.verify(keys.token())
    assert (u.tenant, u.tenant_slug, u.username) == ("tenant-a", "ff-a", "anna")
    assert u.has_module("counterpart") and not u.has_module("wiki")
    assert u.has_role("counterpart", "reader", "admin")
    assert not u.has_role("counterpart", "admin")
    assert not u.has_role("wiki")


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": int(time.time()) - 600},  # expired
        {"aud": "other-app"},  # issued for another app
        {"iss": "https://evil.test/o"},  # foreign issuer
    ],
)
def test_invalid_tokens(verifier, keys, claims):
    with pytest.raises(TokenError):
        verifier.verify(keys.token(**claims))


def test_foreign_signature_and_missing_token(verifier):
    with pytest.raises(TokenError):
        verifier.verify(Keys().token())  # signed with a different key
    with pytest.raises(TokenError):
        verifier.verify(None)
    with pytest.raises(TokenError):
        verifier.verify("not.a.jwt")
