#!/usr/bin/env python3
"""Universal T6 GfxImage -> IPAK payload resolver.

This module is deliberately independent of GfxWorld/XModel and of any map name.
Both world and model materials must resolve streamed images through this same code.

Inputs are normalized GfxImage identities plus an ordered set of eligible IPAK
sources.  The resolver:

- requires the retained streamed `dataHash29`;
- prefers exact `(nameHash, dataHash29)` matches;
- optionally permits a *unique dataHash* match only when the caller explicitly
  enables that already-proven identity rule;
- applies source precedence deterministically (larger priority wins);
- records lower-priority/shadowed matches and same-name/wrong-data variants;
- extracts through `t6_ipak_core`, so CRC29 is always independently verified;
- optionally validates retained dimensions through a caller-supplied payload probe.

It never guesses from filenames and never substitutes a same-name payload whose data
hash differs from the retained GfxImage streamed-part hash.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from t6_ipak_core import IpakEntry, T6Ipak, T6IpakError


class T6ImageResolverError(RuntimeError):
    pass


@dataclass(frozen=True)
class T6ImageIdentity:
    name: str
    name_hash: int
    data_hash29: int
    width: int | None = None
    height: int | None = None
    depth: int | None = None
    streamed_part_index: int = 0

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "T6ImageIdentity":
        name = str(row.get("image") or row.get("name") or "")
        if not name:
            raise T6ImageResolverError("GfxImage identity is missing name")

        def first(*keys: str) -> Any:
            for key in keys:
                value = row.get(key)
                if value is not None:
                    return value
            return None

        name_hash = first("nameHash", "name_hash", "gfxImageHash", "hash")
        data_hash = first(
            "dataHash29",
            "data_hash29",
            "streamedPart0Hash29",
            "streamedDataHash29",
        )
        if data_hash is None:
            parts = row.get("streamedParts")
            if isinstance(parts, list) and parts:
                part0 = parts[0] or {}
                data_hash = first_from(part0, "dataHash29", "hash29", "hash")
        if name_hash is None:
            raise T6ImageResolverError(f"{name}: missing retained GfxImage name hash")
        if data_hash is None:
            raise T6ImageResolverError(f"{name}: missing retained streamed-part data hash")

        def opt_int(value: Any) -> int | None:
            return None if value is None else int(value)

        return cls(
            name=name,
            name_hash=int(name_hash),
            data_hash29=int(data_hash),
            width=opt_int(row.get("width")),
            height=opt_int(row.get("height")),
            depth=opt_int(row.get("depth")),
            streamed_part_index=int(row.get("streamedPartIndex", 0)),
        )

    def dimensions(self) -> tuple[int, int, int] | None:
        if self.width is None or self.height is None or self.depth is None:
            return None
        return (self.width, self.height, self.depth)


def first_from(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return None


@dataclass(frozen=True)
class T6IpakSource:
    label: str
    priority: int
    ipak: T6Ipak
    source_class: str | None = None


@dataclass(frozen=True)
class _Candidate:
    source: T6IpakSource
    entry: IpakEntry
    resolution: str


PayloadProbe = Callable[[bytes], dict[str, Any]]


class T6StreamedImageResolver:
    def __init__(
        self,
        sources: Iterable[T6IpakSource],
        *,
        allow_unique_data_hash: bool = False,
    ):
        source_list = list(sources)
        labels = [s.label for s in source_list]
        if len(labels) != len(set(labels)):
            raise T6ImageResolverError("duplicate IPAK source labels")
        self.sources = sorted(source_list, key=lambda s: (s.priority, s.label))
        self.allow_unique_data_hash = bool(allow_unique_data_hash)

    def _census(self, image: T6ImageIdentity) -> tuple[list[_Candidate], list[dict[str, Any]]]:
        exact: list[_Candidate] = []
        unique: list[_Candidate] = []
        diagnostics: list[dict[str, Any]] = []
        for source in self.sources:
            exact_entry = source.ipak.exact(image.name_hash, image.data_hash29)
            name_variants = source.ipak.name_candidates(image.name_hash)
            data_variants = source.ipak.data_candidates(image.data_hash29)
            wrong_name_data = sorted(
                {entry.data_hash for entry in name_variants if entry.data_hash != image.data_hash29}
            )
            diagnostics.append(
                {
                    "source": source.label,
                    "priority": source.priority,
                    "sourceClass": source.source_class,
                    "exactPair": exact_entry is not None,
                    "sameNameWrongDataHashes": wrong_name_data,
                    "dataHashEntryCount": len(data_variants),
                    "dataHashAvailableNameHashes": sorted({e.name_hash for e in data_variants}),
                }
            )
            if exact_entry is not None:
                exact.append(_Candidate(source, exact_entry, "exact-pair"))
                continue
            if self.allow_unique_data_hash:
                unique_entry = source.ipak.unique_data(image.data_hash29)
                if unique_entry is not None:
                    unique.append(_Candidate(source, unique_entry, "unique-data-hash"))

        # Exact identity always dominates the weaker explicit unique-data rule,
        # even when the weaker candidate happens to live in a higher-priority IPAK.
        candidates = exact if exact else unique
        return candidates, diagnostics

    def resolve(
        self,
        image: T6ImageIdentity,
        *,
        payload_probe: PayloadProbe | None = None,
    ) -> dict[str, Any]:
        candidates, diagnostics = self._census(image)
        if not candidates:
            return {
                "state": "unresolved",
                "image": image.name,
                "nameHash": image.name_hash,
                "dataHash29": image.data_hash29,
                "streamedPartIndex": image.streamed_part_index,
                "dimensions": image.dimensions(),
                "sourceDiagnostics": diagnostics,
                "reason": (
                    "no exact (nameHash,dataHash29) match in eligible IPAKs"
                    if not self.allow_unique_data_hash
                    else "no exact pair or explicit unique-dataHash match in eligible IPAKs"
                ),
            }

        # Larger priority wins. Tie is invalid because a precedence graph must not
        # have two indistinguishable winning containers for one identity.
        max_priority = max(c.source.priority for c in candidates)
        winners = [c for c in candidates if c.source.priority == max_priority]
        if len(winners) != 1:
            raise T6ImageResolverError(
                f"{image.name}: ambiguous winning IPAK sources at priority {max_priority}: "
                f"{[c.source.label for c in winners]}"
            )
        winner = winners[0]
        try:
            payload = winner.source.ipak.extract(winner.entry)
        except T6IpakError as exc:
            raise T6ImageResolverError(
                f"{image.name}: winning IPAK payload failed validation: {exc}"
            ) from exc

        probe = None
        expected_dimensions = image.dimensions()
        if payload_probe is not None:
            probe = payload_probe(payload)
            if not isinstance(probe, dict):
                raise T6ImageResolverError(f"{image.name}: payload probe did not return dict")
            if expected_dimensions is not None:
                actual = (
                    int(probe.get("width", -1)),
                    int(probe.get("height", -1)),
                    int(probe.get("depth", -1)),
                )
                if actual != expected_dimensions:
                    raise T6ImageResolverError(
                        f"{image.name}: payload dimensions {actual} != retained {expected_dimensions}"
                    )

        shadowed = [
            {
                "source": c.source.label,
                "priority": c.source.priority,
                "sourceClass": c.source.source_class,
                "resolution": c.resolution,
                "entry": list(c.entry.as_tuple()),
            }
            for c in sorted(candidates, key=lambda c: (c.source.priority, c.source.label))
            if c is not winner
        ]
        return {
            "state": "resolved",
            "image": image.name,
            "nameHash": image.name_hash,
            "dataHash29": image.data_hash29,
            "streamedPartIndex": image.streamed_part_index,
            "dimensions": expected_dimensions,
            "resolution": winner.resolution,
            "winner": {
                "source": winner.source.label,
                "priority": winner.source.priority,
                "sourceClass": winner.source.source_class,
                "entry": list(winner.entry.as_tuple()),
            },
            "shadowedAdmissibleMatches": shadowed,
            "sourceDiagnostics": diagnostics,
            "payloadBytes": len(payload),
            "payloadProbe": probe,
            "payload": payload,
            "policy": (
                "exact pair dominates unique-dataHash; within the selected resolution class, "
                "highest source priority wins; same-name wrong-data variants are diagnostic only"
            ),
        }

    def resolve_manifest_row(
        self,
        row: dict[str, Any],
        *,
        payload_probe: PayloadProbe | None = None,
    ) -> dict[str, Any]:
        return self.resolve(T6ImageIdentity.from_dict(row), payload_probe=payload_probe)


def serializable_resolution(result: dict[str, Any]) -> dict[str, Any]:
    """Return a proof/manfiest-safe copy without the raw payload bytes."""
    return {key: value for key, value in result.items() if key != "payload"}
