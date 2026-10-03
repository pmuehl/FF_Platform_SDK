"""Receiver of the master data sync (platform → app).

The platform delivers changes to `POST /intern/stammdaten`. The field names are
the platform's wire format:

    {"ereignisse": [{"id": 42, "tenant": "…", "entitaet": "mitglied",
                     "typ": "upsert", "nutzlast": {...}}, …], "bis": 57}

- `upsert`    create or replace the record (the ID is the platform's ID).
              Versions older than the stored one are ignored (`version`).
- `entfernt`  the record is no longer delivered (dropped out of the filter or
              deleted) — mark, do not delete: the app's own data refers to it.
- `abgleich`  full reconcile of a fire brigade: everything not listed in
              `vollstaendig` counts as no longer delivered.
- entity `widerruf`: user locked, role withdrawn, module disabled — the app
              ends the affected sessions immediately.

Delivery is "at least once": the receiver must be idempotent.
The app brings its own `Mirror` (tables in its database);
`InMemoryMirror` is the reference for tests.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


class Mirror(Protocol):
    def upsert(self, tenant: str | None, entity: str, record: dict[str, Any]) -> None: ...

    def removed(self, tenant: str | None, entity: str, record_id: str) -> None: ...

    def reconcile(self, tenant: str, entity: str, valid_ids: set[str]) -> None: ...

    def revoke(self, tenant: str | None, data: dict[str, Any]) -> None: ...

    def tenant_init(self, tenant: dict[str, Any]) -> None: ...


def process(mirror: Mirror, delivery: dict[str, Any]) -> dict[str, Any]:
    """Applies a delivery to the mirror and returns the acknowledgement."""
    for event in delivery.get("ereignisse", []):
        tenant, entity, payload = (
            event.get("tenant"),
            event["entitaet"],
            event["nutzlast"],
        )
        if entity == "widerruf":
            mirror.revoke(tenant, payload)
        elif event["typ"] == "entfernt":
            mirror.removed(tenant, entity, payload["id"])
        else:
            mirror.upsert(tenant, entity, payload)
    reconcile = delivery.get("abgleich")
    if reconcile:
        for entity, ids in reconcile["vollstaendig"].items():
            mirror.reconcile(reconcile["tenant"], entity, set(ids))
    return {"bestaetigt": delivery.get("bis")}


@dataclass
class InMemoryMirror:
    """Reference mirror in memory — for tests and the test counterpart."""

    # (tenant, entity) → {id: record}; catalogs are stored under tenant None
    data: dict[tuple[str | None, str], dict[str, dict[str, Any]]] = field(default_factory=dict)
    no_longer_delivered: set[tuple[str | None, str, str]] = field(default_factory=set)
    revocations: list[dict[str, Any]] = field(default_factory=list)
    initialized: list[dict[str, Any]] = field(default_factory=list)

    def table(self, tenant: str | None, entity: str) -> dict[str, dict[str, Any]]:
        return self.data.setdefault((tenant, entity), {})

    def delivered(self, tenant: str | None, entity: str) -> list[dict[str, Any]]:
        """Records that are currently delivered."""
        return [
            r
            for i, r in self.table(tenant, entity).items()
            if (tenant, entity, i) not in self.no_longer_delivered
        ]

    def upsert(self, tenant, entity, record):
        table = self.table(tenant, entity)
        present = table.get(record["id"])
        # `version` guards against late, older deliveries
        if present and present.get("version", 0) > record.get("version", 0):
            return
        table[record["id"]] = record
        self.no_longer_delivered.discard((tenant, entity, record["id"]))

    def removed(self, tenant, entity, record_id):
        if record_id in self.table(tenant, entity):
            self.no_longer_delivered.add((tenant, entity, record_id))

    def reconcile(self, tenant, entity, valid_ids):
        for record_id in self.table(tenant, entity):
            if record_id not in valid_ids:
                self.no_longer_delivered.add((tenant, entity, record_id))

    def revoke(self, tenant, data):
        self.revocations.append({"tenant": tenant, **data})

    def tenant_init(self, tenant):
        self.initialized.append(tenant)
