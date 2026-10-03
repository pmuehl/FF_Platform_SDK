"""Building blocks for FastAPI apps: user from the token, role check, internal endpoints."""

import json
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from . import internal
from .auth import AuthenticatedUser, TokenError, TokenVerifier
from .changelog import Changelog
from .master_data import Mirror, process


def current_user(verifier: TokenVerifier) -> Callable[..., AuthenticatedUser]:
    """Dependency: reads `Authorization: Bearer <ID token>` and verifies it.

    401 only for a missing, expired or invalid token — clients then redirect
    to the platform's login.
    """

    def dependency(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
        try:
            return verifier.verify(token)
        except TokenError as error:
            raise HTTPException(401, "Not authenticated") from error

    return dependency


def require_role(
    user: Callable[..., AuthenticatedUser], module: str, *roles: str
) -> Callable[..., AuthenticatedUser]:
    """Dependency: access only with one of the roles in the module.

    Without access to the module: 404 (does not reveal what is enabled);
    with access but the wrong role: 403.
    """

    def dependency(u: AuthenticatedUser = Depends(user)) -> AuthenticatedUser:  # noqa: B008
        if not u.has_module(module):
            raise HTTPException(404, "Not found")
        if not u.has_role(module, *roles):
            raise HTTPException(403, "Forbidden")
        return u

    return dependency


def internal_router(
    *,
    secret: str,
    manifest: dict[str, Any] | Callable[[], dict[str, Any]],
    mirror: Mirror,
    changelog: Changelog | None = None,
) -> APIRouter:
    """The internal endpoints called by the platform — all signed.

    `GET /intern/manifest`, `POST /intern/mandant-init`, `POST /intern/stammdaten`
    and, if a changelog is given, `GET /intern/changelog`.
    In the deployment `/intern/*` must not be routed to the outside.
    """
    router = APIRouter(prefix="/intern", tags=["internal"])

    async def signed(request: Request) -> bytes:
        body = await request.body()
        if not internal.verify(
            secret,
            request.method,
            request.url.path,
            body,
            request.headers.get(internal.HEADER_TIMESTAMP),
            request.headers.get(internal.HEADER_SIGNATURE),
        ):
            raise HTTPException(401, "Invalid signature")
        return body

    @router.get("/manifest")
    async def get_manifest(_: bytes = Depends(signed)) -> dict[str, Any]:
        return manifest() if callable(manifest) else manifest

    @router.post("/mandant-init")
    async def tenant_init(body: bytes = Depends(signed)) -> dict[str, bool]:
        mirror.tenant_init(json.loads(body)["tenant"])
        return {"ok": True}

    @router.post("/stammdaten")
    async def master_data(body: bytes = Depends(signed)) -> dict[str, Any]:
        return process(mirror, json.loads(body))

    if changelog is not None:

        @router.get("/changelog")
        async def get_changelog(_: bytes = Depends(signed)) -> dict[str, Any]:
            return changelog.as_response()

    return router
