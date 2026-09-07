#!/usr/bin/env python3
"""Persistent dependency-aware retail T6 asset index v1.

The index deliberately separates *references* (for example an XModel Material
handle) from authoritative serialized *definitions*.  A reference proves which
asset a consumer asks for; it does not imply that the bytes around that handle
contain the full asset body.

This module is intentionally asset-type agnostic.  The first adapter consumes
`t6-material-techset-top-level-walk-v1` reports, but the same on-disk index can
hold XModels, XAnims, GfxImages, shaders, sounds, maps, and future XAsset types.

Resolution is fail-closed:
* missing definitions fail;
* conflicting definitions fail unless a dependency/search order selects one;
* byte-identical duplicates are collapsed;
* cached indexes can be verified against exact expanded-zone fingerprints.

Only Python's standard library is used so this can run in CI and extraction
workflows without installing anything.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

FORMAT = "t6-retail-asset-index-v1"
WALK_FORMAT = "t6-material-techset-top-level-walk-v1"


class AssetIndexError(RuntimeError):
    pass


class MissingAssetError(AssetIndexError):
    pass


class AmbiguousAssetError(AssetIndexError):
    pass


class StaleIndexError(AssetIndexError):
    pass


@dataclasses.dataclass(frozen=True)
class ZoneFingerprint:
    zone: str
    sha256: str
    size: int

    @classmethod
    def from_bytes(cls, zone: str, data: bytes) -> "ZoneFingerprint":
        return cls(zone=zone, sha256=hashlib.sha256(data).hexdigest(), size=len(data))

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class AssetDefinition:
    asset_type: str
    name: str
    zone: str
    start: int
    end: int
    sha256: str
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.asset_type or not self.name or not self.zone:
            raise ValueError("asset_type, name and zone are required")
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"invalid serialized extent {self.start}..{self.end}")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError(f"invalid SHA-256 {self.sha256!r}")

    @property
    def serialized_bytes(self) -> int:
        return self.end - self.start

    @property
    def content_identity(self) -> tuple[str, int]:
        return self.sha256, self.serialized_bytes

    def as_dict(self) -> dict[str, Any]:
        return {
            "assetType": self.asset_type,
            "name": self.name,
            "zone": self.zone,
            "start": self.start,
            "end": self.end,
            "serializedBytes": self.serialized_bytes,
            "sha256": self.sha256,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AssetDefinition":
        return cls(
            asset_type=str(raw["assetType"]),
            name=str(raw["name"]),
            zone=str(raw["zone"]),
            start=int(raw["start"]),
            end=int(raw["end"]),
            sha256=str(raw["sha256"]).lower(),
            metadata=dict(raw.get("metadata") or {}),
        )


@dataclasses.dataclass(frozen=True)
class AssetReference:
    asset_type: str
    name: str
    source_zone: str
    source_asset: str | None = None
    owner_start: int | None = None
    proof: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "assetType": self.asset_type,
            "name": self.name,
            "sourceZone": self.source_zone,
            "sourceAsset": self.source_asset,
            "ownerStart": self.owner_start,
            "proof": dict(self.proof),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AssetReference":
        owner = raw.get("ownerStart")
        return cls(
            asset_type=str(raw["assetType"]),
            name=str(raw["name"]),
            source_zone=str(raw["sourceZone"]),
            source_asset=raw.get("sourceAsset"),
            owner_start=None if owner is None else int(owner),
            proof=dict(raw.get("proof") or {}),
        )


def _extract_walk_name(row: Mapping[str, Any]) -> str:
    raw = row.get("name")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, Mapping):
        value = raw.get("value")
        if isinstance(value, str) and value:
            return value
    raise AssetIndexError(f"walk row has no exact inline name: {raw!r}")


def _row_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    xasset_type = int(row["xassetType"])
    base: dict[str, Any] = {
        "producerFormat": WALK_FORMAT,
        "xassetIndex": int(row["xassetIndex"]),
        "xassetType": xasset_type,
    }
    if xasset_type == 5:
        base.update(
            textureCount=int(row.get("textureCount", 0)),
            constantCount=int(row.get("constantCount", 0)),
            stateBitsCount=int(row.get("stateBitsCount", 0)),
            techniqueSetPointer=row.get("techniqueSetPointer"),
            nestedTechniqueSetName=(
                _extract_walk_name(row["nestedTechniqueSet"])
                if isinstance(row.get("nestedTechniqueSet"), Mapping)
                and row["nestedTechniqueSet"].get("name") is not None
                else None
            ),
        )
    elif xasset_type == 7:
        base.update(
            worldVertFormat=int(row.get("worldVertFormat", 0)),
            techniqueRefCount=len(row.get("techniqueRefs") or []),
        )
    return base


class RetailAssetIndex:
    def __init__(self) -> None:
        self.zones: dict[str, ZoneFingerprint] = {}
        self.definitions: dict[tuple[str, str], list[AssetDefinition]] = {}
        self.references: list[AssetReference] = []

    def add_zone(self, fp: ZoneFingerprint) -> None:
        old = self.zones.get(fp.zone)
        if old is not None and old != fp:
            raise StaleIndexError(
                f"zone {fp.zone!r} fingerprint changed: "
                f"{old.sha256}/{old.size} -> {fp.sha256}/{fp.size}"
            )
        self.zones[fp.zone] = fp

    def add_definition(self, definition: AssetDefinition) -> None:
        fp = self.zones.get(definition.zone)
        if fp is None:
            raise AssetIndexError(
                f"definition {definition.asset_type}:{definition.name} references "
                f"unregistered zone {definition.zone!r}"
            )
        key = (definition.asset_type, definition.name)
        rows = self.definitions.setdefault(key, [])
        if definition not in rows:
            rows.append(definition)
            rows.sort(key=lambda x: (x.zone, x.start, x.end, x.sha256))

    def add_reference(self, reference: AssetReference) -> None:
        if reference.source_zone not in self.zones:
            raise AssetIndexError(
                f"reference {reference.asset_type}:{reference.name} uses "
                f"unregistered zone {reference.source_zone!r}"
            )
        if reference not in self.references:
            self.references.append(reference)

    def ingest_material_techset_walk(
        self,
        zone: str,
        report: Mapping[str, Any],
        expanded: bytes,
    ) -> list[AssetDefinition]:
        if report.get("format") != WALK_FORMAT:
            raise AssetIndexError(
                f"{zone}: expected {WALK_FORMAT!r}, got {report.get('format')!r}"
            )
        actual_fp = ZoneFingerprint.from_bytes(zone, expanded)
        expected_hash = str(report.get("expandedSha256") or "").lower()
        if expected_hash and expected_hash != actual_fp.sha256:
            raise StaleIndexError(
                f"{zone}: walker expandedSha256 {expected_hash} != {actual_fp.sha256}"
            )
        self.add_zone(actual_fp)

        made: list[AssetDefinition] = []
        for row in report.get("rows") or []:
            xasset_type = int(row["xassetType"])
            if xasset_type == 5:
                asset_type = "material"
            elif xasset_type == 7:
                asset_type = "material_technique_set"
            else:
                raise AssetIndexError(
                    f"{zone}: unsupported row xassetType={xasset_type}; "
                    "top-level walker report is corrupt or from a different schema"
                )
            start = int(row["sourceStart"])
            end = int(row["sourceEnd"])
            if start < 0 or end <= start or end > len(expanded):
                raise AssetIndexError(
                    f"{zone}: invalid exact extent {start}..{end} for {asset_type}"
                )
            body = expanded[start:end]
            definition = AssetDefinition(
                asset_type=asset_type,
                name=_extract_walk_name(row),
                zone=zone,
                start=start,
                end=end,
                sha256=hashlib.sha256(body).hexdigest(),
                metadata=_row_metadata(row),
            )
            self.add_definition(definition)
            made.append(definition)
        return made

    def candidates(self, asset_type: str, name: str) -> tuple[AssetDefinition, ...]:
        return tuple(self.definitions.get((asset_type, name), ()))

    def resolve(
        self,
        asset_type: str,
        name: str,
        search_order: Sequence[str] | None = None,
    ) -> AssetDefinition:
        candidates = list(self.candidates(asset_type, name))
        if not candidates:
            raise MissingAssetError(f"no definition for {asset_type}:{name}")

        identities = {x.content_identity for x in candidates}
        if len(identities) == 1:
            if search_order:
                rank = {zone: i for i, zone in enumerate(search_order)}
                candidates.sort(key=lambda x: (rank.get(x.zone, len(rank)), x.zone, x.start))
            else:
                candidates.sort(key=lambda x: (x.zone, x.start))
            return candidates[0]

        if not search_order:
            detail = ", ".join(
                f"{x.zone}@{x.start}:sha256={x.sha256[:12]}" for x in candidates
            )
            raise AmbiguousAssetError(
                f"conflicting definitions for {asset_type}:{name}; "
                f"dependency order required: {detail}"
            )

        rank = {zone: i for i, zone in enumerate(search_order)}
        ranked = [x for x in candidates if x.zone in rank]
        if not ranked:
            raise MissingAssetError(
                f"{asset_type}:{name} exists, but not in dependency closure "
                f"{list(search_order)!r}"
            )
        best_rank = min(rank[x.zone] for x in ranked)
        best = [x for x in ranked if rank[x.zone] == best_rank]
        best_ids = {x.content_identity for x in best}
        if len(best_ids) != 1:
            raise AmbiguousAssetError(
                f"multiple conflicting definitions for {asset_type}:{name} "
                f"at dependency rank {best_rank}"
            )
        best.sort(key=lambda x: (x.zone, x.start))
        return best[0]

    def references_for(
        self, asset_type: str, name: str
    ) -> tuple[AssetReference, ...]:
        return tuple(
            x for x in self.references
            if x.asset_type == asset_type and x.name == name
        )

    def verify_zone_bytes(self, zone: str, data: bytes) -> None:
        expected = self.zones.get(zone)
        if expected is None:
            raise MissingAssetError(f"zone {zone!r} is not indexed")
        actual = ZoneFingerprint.from_bytes(zone, data)
        if actual != expected:
            raise StaleIndexError(
                f"zone {zone!r} bytes do not match index: expected "
                f"{expected.sha256}/{expected.size}, got {actual.sha256}/{actual.size}"
            )

    def as_dict(self) -> dict[str, Any]:
        defs = [
            d.as_dict()
            for key in sorted(self.definitions)
            for d in self.definitions[key]
        ]
        refs = sorted(
            (r.as_dict() for r in self.references),
            key=lambda r: (
                r["assetType"],
                r["name"],
                r["sourceZone"],
                -1 if r["ownerStart"] is None else r["ownerStart"],
            ),
        )
        return {
            "format": FORMAT,
            "zones": {
                zone: self.zones[zone].as_dict()
                for zone in sorted(self.zones)
            },
            "definitions": defs,
            "references": refs,
            "summary": {
                "zoneCount": len(self.zones),
                "definitionCount": len(defs),
                "referenceCount": len(refs),
                "assetKeyCount": len(self.definitions),
            },
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RetailAssetIndex":
        if raw.get("format") != FORMAT:
            raise AssetIndexError(
                f"expected index format {FORMAT!r}, got {raw.get('format')!r}"
            )
        out = cls()
        zones = raw.get("zones") or {}
        for zone, row in zones.items():
            out.add_zone(
                ZoneFingerprint(
                    zone=str(zone),
                    sha256=str(row["sha256"]).lower(),
                    size=int(row["size"]),
                )
            )
        for row in raw.get("definitions") or []:
            out.add_definition(AssetDefinition.from_dict(row))
        for row in raw.get("references") or []:
            out.add_reference(AssetReference.from_dict(row))
        return out

    @classmethod
    def load(cls, path: Path) -> "RetailAssetIndex":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _parse_zone_paths(values: Iterable[str]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for item in values:
        if "=" not in item:
            raise AssetIndexError(f"expected ZONE=PATH, got {item!r}")
        zone, raw_path = item.split("=", 1)
        if not zone or not raw_path:
            raise AssetIndexError(f"expected non-empty ZONE=PATH, got {item!r}")
        if zone in out:
            raise AssetIndexError(f"duplicate zone argument {zone!r}")
        out[zone] = Path(raw_path)
    return out


def _cmd_build(args: argparse.Namespace) -> int:
    walks = _parse_zone_paths(args.walk)
    expanded_paths = _parse_zone_paths(args.expanded)
    if set(walks) != set(expanded_paths):
        raise AssetIndexError(
            "--walk and --expanded must provide the same exact zone names"
        )
    index = RetailAssetIndex()
    for zone in sorted(walks):
        report = json.loads(walks[zone].read_text(encoding="utf-8"))
        expanded = expanded_paths[zone].read_bytes()
        index.ingest_material_techset_walk(zone, report, expanded)
    index.save(args.out)
    print(json.dumps(index.as_dict()["summary"], indent=2, sort_keys=True))
    return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    index = RetailAssetIndex.load(args.index)
    order = None
    if args.search_order:
        order = [x for x in args.search_order.split(",") if x]
    result = index.resolve(args.asset_type, args.name, order)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    index = RetailAssetIndex.load(args.index)
    zones = _parse_zone_paths(args.expanded)
    for zone, path in zones.items():
        index.verify_zone_bytes(zone, path.read_bytes())
    print(json.dumps({"verifiedZones": sorted(zones)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="build exact index from top-level walker reports")
    b.add_argument("--walk", action="append", default=[], metavar="ZONE=PATH", required=True)
    b.add_argument(
        "--expanded", action="append", default=[], metavar="ZONE=PATH", required=True
    )
    b.add_argument("--out", type=Path, required=True)
    b.set_defaults(func=_cmd_build)

    r = sub.add_parser("resolve", help="resolve one authoritative asset definition")
    r.add_argument("index", type=Path)
    r.add_argument("asset_type")
    r.add_argument("name")
    r.add_argument(
        "--search-order",
        help="comma-separated dependency precedence, highest precedence first",
    )
    r.set_defaults(func=_cmd_resolve)

    v = sub.add_parser("verify", help="fail if indexed expanded-zone bytes changed")
    v.add_argument("index", type=Path)
    v.add_argument("--expanded", action="append", default=[], metavar="ZONE=PATH", required=True)
    v.set_defaults(func=_cmd_verify)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
