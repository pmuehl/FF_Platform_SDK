"""SDK of the FF Platform for the connected apps (Dashboard, Einsatzleitung, wiki_tickets).

Contains the parts the platform verifies in its acceptance test:

- `auth`         verification of the platform's ID token via JWKS → `AuthenticatedUser`
- `internal`     HMAC signature of the internal calls (/intern/*)
- `master_data`  receiver of the master data sync (upsert, "no longer delivered",
                 reconcile, revocation)
- `changelog`    version and changelog of the app, shown by the platform
- `fastapi`      dependencies and router for FastAPI apps
- `testing`      test counterpart the platform tests its sync against

Tenant context, ORM filter, entitlement checks and the leak test suite come
with the migration of the first app.
"""

__version__ = "0.2.0"
