"""Version and changelog of the app, as shown to the fire brigades by the platform.

The app keeps two files in its repository:

- `VERSION`       the first three parts of the version, `ww.xx.yy` (e.g. `1.4.0`).
                  The platform appends the fourth part itself: it counts up
                  whenever the app reports a new build.
- `CHANGELOG.md`  what changed, written for the fire brigades (in German):

      ## 1.4.0 — 2026-10-03: Optional title
      ### Neu
      - One item per line.
      ### Behoben
      - Another item,
        continued on a second line.

  Section headings: `Neu` (new), `Geändert` (changed), `Behoben` (fixed).
  Items without a section count as "changed".

The platform fetches both via the signed endpoint `GET /intern/changelog`
(see `fastapi.internal_router`). The field names of the response are the
platform's wire format.

A build ID that changes with every build lets the platform count builds. It is
taken from the environment variable `BUILD_ID` or from a file `BUILD`, e.g.
written in the Dockerfile after copying the sources:

    RUN date -u +%Y%m%d%H%M%S > BUILD
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VERSION_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$")

_HEADING = re.compile(
    r"^##\s+v?(\d{1,3}\.\d{1,3}\.\d{1,3})\s*(?:[—–-]\s*|\()(\d{4}-\d{2}-\d{2})\)?\s*(?::\s*(.*))?$"
)
_SECTIONS = {
    "neu": "neu",
    "new": "neu",
    "added": "neu",
    "geändert": "geaendert",
    "geaendert": "geaendert",
    "changed": "geaendert",
    "behoben": "behoben",
    "fixed": "behoben",
}


def parse(text: str) -> list[dict[str, Any]]:
    """Parses the changelog format described above into the wire format entries."""
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    kind = "geaendert"
    for line in text.splitlines():
        heading = _HEADING.match(line.strip())
        if heading:
            current = {
                "version": heading[1],
                "datum": heading[2],
                "titel": (heading[3] or "").strip(),
                "punkte": [],
            }
            entries.append(current)
            kind = "geaendert"
        elif current is None:
            continue
        elif line.startswith("###"):
            kind = _SECTIONS.get(line.lstrip("#").strip().lower(), "geaendert")
        elif line.lstrip().startswith(("- ", "* ")):
            current["punkte"].append({"art": kind, "text": line.lstrip()[2:].strip()})
        elif line.startswith((" ", "\t")) and line.strip() and current["punkte"]:
            current["punkte"][-1]["text"] += " " + line.strip()
    return entries


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


@dataclass(frozen=True)
class Changelog:
    version: str  # ww.xx.yy
    entries: list[dict[str, Any]] = field(default_factory=list)
    build: str = ""

    def __post_init__(self) -> None:
        if not VERSION_PATTERN.match(self.version):
            raise ValueError(f"version {self.version!r} does not have the form ww.xx.yy")

    @classmethod
    def from_files(cls, directory: str | Path = ".", *, build: str | None = None) -> "Changelog":
        """Reads `VERSION`, `CHANGELOG.md` and the build ID from the given directory."""
        root = Path(directory)
        return cls(
            version=_read(root / "VERSION"),
            entries=parse(_read(root / "CHANGELOG.md")),
            build=build or os.environ.get("BUILD_ID") or _read(root / "BUILD"),
        )

    def as_response(self) -> dict[str, Any]:
        return {"version": self.version, "build": self.build, "eintraege": self.entries}
