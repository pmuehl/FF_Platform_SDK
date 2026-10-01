"""Prüfung des ID-Tokens der Plattform (RS256, über JWKS).

Die App meldet Benutzer per OIDC an der Plattform an (Authorization Code mit
PKCE) und bekommt ein ID-Token, 15 Minuten gültig. Darin stehen Feuerwehr,
Module und Rollen. Dieses Token prüft die App bei jedem Aufruf selbst — ohne
Rückfrage bei der Plattform.

Maßgeblich ist ausschließlich der geprüfte Claim `tenant`, nie die Domain.
"""

from dataclasses import dataclass, field
from typing import Any

import jwt
from jwt import PyJWKClient


class TokenFehler(Exception):
    """Token fehlt, ist abgelaufen oder ungültig → HTTP 401."""


@dataclass(frozen=True)
class AngemeldeterBenutzer:
    identitaet: str  # sub
    tenant: str
    tenant_slug: str
    mitgliedschaft: str
    mitglied: str | None
    name: str
    benutzername: str
    module: tuple[str, ...]
    rollen: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def hat_modul(self, modul: str) -> bool:
        return modul in self.module

    def hat_rolle(self, modul: str, *rollen: str) -> bool:
        """Hat der Benutzer im Modul eine der genannten Rollen (ohne Angabe: irgendeine)?"""
        vorhanden = self.rollen.get(modul, ())
        return bool(set(vorhanden) & set(rollen)) if rollen else bool(vorhanden)


class TokenPruefer:
    """Prüft ID-Tokens gegen den öffentlichen Schlüssel der Plattform.

    aussteller: Issuer der Plattform, z. B. https://platform.alarmboard.at/o
    client_id:  Client der App (steht als `aud` im Token)

    Die Schlüssel werden zwischengespeichert; wechselt die Plattform den
    Schlüssel, lädt der Prüfer bei unbekannter `kid` neu.
    """

    def __init__(
        self,
        aussteller: str,
        client_id: str,
        *,
        jwks_url: str | None = None,
        jwks_client: Any = None,
        toleranz: int = 30,
    ):
        self.aussteller = aussteller.rstrip("/")
        self.client_id = client_id
        self.toleranz = toleranz
        self._jwks = jwks_client or PyJWKClient(
            jwks_url or f"{self.aussteller}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=3600,
        )

    def pruefe(self, token: str | None) -> AngemeldeterBenutzer:
        if not token:
            raise TokenFehler("Token fehlt")
        try:
            schluessel = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                schluessel,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.aussteller,
                leeway=self.toleranz,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as fehler:
            raise TokenFehler(str(fehler)) from fehler
        try:
            return AngemeldeterBenutzer(
                identitaet=claims["sub"],
                tenant=claims["tenant"],
                tenant_slug=claims["tenant_slug"],
                mitgliedschaft=claims["mitgliedschaft"],
                mitglied=claims.get("mitglied"),
                name=claims.get("name", ""),
                benutzername=claims.get("preferred_username", ""),
                module=tuple(claims.get("module", ())),
                rollen={m: tuple(r) for m, r in claims.get("rollen", {}).items()},
            )
        except KeyError as fehler:
            raise TokenFehler(f"Claim fehlt: {fehler}") from fehler
