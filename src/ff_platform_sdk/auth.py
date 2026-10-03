"""Verification of the platform's ID token (RS256, via JWKS).

The app signs users in at the platform via OIDC (authorization code with PKCE)
and receives an ID token, valid for 15 minutes. It carries the fire brigade,
the modules and the roles. The app verifies this token itself on every call —
without asking the platform.

Only the verified claim `tenant` counts, never the domain.
"""

from dataclasses import dataclass, field
from typing import Any

import jwt
from jwt import PyJWKClient


class TokenError(Exception):
    """Token is missing, expired or invalid → HTTP 401."""


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str  # sub
    tenant: str
    tenant_slug: str
    membership: str
    member: str | None
    name: str
    username: str
    modules: tuple[str, ...]
    roles: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def has_module(self, module: str) -> bool:
        return module in self.modules

    def has_role(self, module: str, *roles: str) -> bool:
        """Does the user have one of the given roles in the module (none given: any role)?"""
        present = self.roles.get(module, ())
        return bool(set(present) & set(roles)) if roles else bool(present)


class TokenVerifier:
    """Verifies ID tokens against the platform's public key.

    issuer:     issuer of the platform, e.g. https://platform.alarmboard.at/o
    client_id:  client of the app (the `aud` of the token)

    Keys are cached; when the platform rotates its key, the verifier reloads
    on an unknown `kid`.
    """

    def __init__(
        self,
        issuer: str,
        client_id: str,
        *,
        jwks_url: str | None = None,
        jwks_client: Any = None,
        leeway: int = 30,
    ):
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.leeway = leeway
        self._jwks = jwks_client or PyJWKClient(
            jwks_url or f"{self.issuer}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=3600,
        )

    def verify(self, token: str | None) -> AuthenticatedUser:
        if not token:
            raise TokenError("token missing")
        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as error:
            raise TokenError(str(error)) from error
        try:
            # claim names are the platform's wire format
            return AuthenticatedUser(
                subject=claims["sub"],
                tenant=claims["tenant"],
                tenant_slug=claims["tenant_slug"],
                membership=claims["mitgliedschaft"],
                member=claims.get("mitglied"),
                name=claims.get("name", ""),
                username=claims.get("preferred_username", ""),
                modules=tuple(claims.get("module", ())),
                roles={m: tuple(r) for m, r in claims.get("rollen", {}).items()},
            )
        except KeyError as error:
            raise TokenError(f"claim missing: {error}") from error
