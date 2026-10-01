"""Bausteine für FastAPI-Apps: Benutzer aus dem Token, Rollenprüfung, interne Endpunkte."""

import json
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from . import intern
from .auth import AngemeldeterBenutzer, TokenFehler, TokenPruefer
from .stammdaten import Spiegel, verarbeite


def aktueller_benutzer(pruefer: TokenPruefer) -> Callable[..., AngemeldeterBenutzer]:
    """Abhängigkeit: liest `Authorization: Bearer <ID-Token>` und prüft es.

    401 nur bei fehlendem, abgelaufenem oder ungültigem Token — die Clients
    leiten dann zum Login der Plattform.
    """

    def abhaengigkeit(authorization: str | None = Header(default=None)) -> AngemeldeterBenutzer:
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
        try:
            return pruefer.pruefe(token)
        except TokenFehler as fehler:
            raise HTTPException(401, "Nicht angemeldet") from fehler

    return abhaengigkeit


def require_rolle(
    benutzer: Callable[..., AngemeldeterBenutzer], modul: str, *rollen: str
) -> Callable[..., AngemeldeterBenutzer]:
    """Abhängigkeit: Zugriff nur mit einer der Rollen im Modul.

    Ohne Zugriff auf das Modul: 404 (verrät nicht, was gebucht ist);
    mit Zugriff, aber falscher Rolle: 403.
    """

    def abhaengigkeit(b: AngemeldeterBenutzer = Depends(benutzer)) -> AngemeldeterBenutzer:  # noqa: B008
        if not b.hat_modul(modul):
            raise HTTPException(404, "Nicht gefunden")
        if not b.hat_rolle(modul, *rollen):
            raise HTTPException(403, "Keine Berechtigung")
        return b

    return abhaengigkeit


def intern_router(
    *, geheimnis: str, manifest: dict[str, Any] | Callable[[], dict[str, Any]], spiegel: Spiegel
) -> APIRouter:
    """Die internen Endpunkte, die die Plattform aufruft — alle signiert.

    `GET /intern/manifest`, `POST /intern/mandant-init`, `POST /intern/stammdaten`.
    Im Deployment darf `/intern/*` nicht nach außen geroutet werden.
    """
    router = APIRouter(prefix="/intern", tags=["intern"])

    async def signiert(request: Request) -> bytes:
        body = await request.body()
        if not intern.pruefen(
            geheimnis,
            request.method,
            request.url.path,
            body,
            request.headers.get(intern.KOPF_ZEIT),
            request.headers.get(intern.KOPF_SIGNATUR),
        ):
            raise HTTPException(401, "Signatur ungültig")
        return body

    @router.get("/manifest")
    async def manifest_liefern(_: bytes = Depends(signiert)) -> dict[str, Any]:
        return manifest() if callable(manifest) else manifest

    @router.post("/mandant-init")
    async def mandant_init(body: bytes = Depends(signiert)) -> dict[str, bool]:
        spiegel.mandant_init(json.loads(body)["tenant"])
        return {"ok": True}

    @router.post("/stammdaten")
    async def stammdaten(body: bytes = Depends(signiert)) -> dict[str, Any]:
        return verarbeite(spiegel, json.loads(body))

    return router
