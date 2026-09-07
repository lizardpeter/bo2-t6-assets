#!/usr/bin/env python3
"""Persistent dependency-aware retail T6 asset index v1.

References and authoritative serialized definitions are deliberately separate.
A packed handle can prove what an owner references without proving that bytes at
the handle field are the referenced asset definition.

The index is asset-type agnostic and fail-closed.  Numeric retail XAsset ids are
read only from t6_asset_types_v1.py.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from t6_asset_types_v1 import MATERIAL, TECHNIQUE_SET

FORMAT = "t6-retail-asset-index-v1"
WALK_FORMAT = "t6-material-techset-top-level-walk-v1"


class AssetIndexError(RuntimeError): pass
class MissingAssetError(AssetIndexError): pass
class AmbiguousAssetError(AssetIndexError): pass
class StaleIndexError(AssetIndexError): pass


@dataclasses.dataclass(frozen=True)
class ZoneFingerprint:
    zone: str
    sha256: str
    size: int

    @classmethod
    def from_bytes(cls, zone: str, data: bytes) -> "ZoneFingerprint":
        return cls(zone, hashlib.sha256(data).hexdigest(), len(data))

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
            "assetType": self.asset_type, "name": self.name, "zone": self.zone,
            "start": self.start, "end": self.end,
            "serializedBytes": self.serialized_bytes, "sha256": self.sha256,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AssetDefinition":
        return cls(
            str(raw["assetType"]), str(raw["name"]), str(raw["zone"]),
            int(raw["start"]), int(raw["end"]), str(raw["sha256"]).lower(),
            dict(raw.get("metadata") or {}),
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
            "assetType": self.asset_type, "name": self.name,
            "sourceZone": self.source_zone, "sourceAsset": self.source_asset,
            "ownerStart": self.owner_start, "proof": dict(self.proof),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "AssetReference":
        owner = raw.get("ownerStart")
        return cls(
            str(raw["assetType"]), str(raw["name"]), str(raw["sourceZone"]),
            raw.get("sourceAsset"), None if owner is None else int(owner),
            dict(raw.get("proof") or {}),
        )


def _extract_walk_name(row: Mapping[str, Any]) -> str:
    raw = row.get("name")
    if isinstance(raw, str) and raw: return raw
    if isinstance(raw, Mapping):
        value = raw.get("value")
        if isinstance(value, str) and value: return value
    raise AssetIndexError(f"walk row has no exact inline name: {raw!r}")


def _row_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    xtype = int(row["xassetType"])
    base: dict[str, Any] = {
        "producerFormat": WALK_FORMAT,
        "xassetIndex": int(row["xassetIndex"]),
        "xassetType": xtype,
    }
    if xtype == MATERIAL:
        base.update(
            textureCount=int(row.get("textureCount", 0)),
            constantCount=int(row.get("constantCount", 0)),
            stateBitsCount=int(row.get("stateBitsCount", 0)),
            techniqueSetPointer=row.get("techniqueSetPointer"),
            nestedTechniqueSetName=(
                _extract_walk_name(row["nestedTechniqueSet"])
                if isinstance(row.get("nestedTechniqueSet"), Mapping)
                and row["nestedTechniqueSet"].get("name") is not None else None
            ),
        )
    elif xtype == TECHNIQUE_SET:
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
                f"zone {fp.zone!r} fingerprint changed: {old.sha256}/{old.size} -> {fp.sha256}/{fp.size}"
            )
        self.zones[fp.zone] = fp

    def add_definition(self, definition: AssetDefinition) -> None:
        if definition.zone not in self.zones:
            raise AssetIndexError(
                f"definition {definition.asset_type}:{definition.name} references unregistered zone {definition.zone!r}"
            )
        key = (definition.asset_type, definition.name)
        rows = self.definitions.setdefault(key, [])
        if definition not in rows:
            rows.append(definition)
            rows.sort(key=lambda x: (x.zone, x.start, x.end, x.sha256))

    def add_reference(self, reference: AssetReference) -> None:
        if reference.source_zone not in self.zones:
            raise AssetIndexError(
                f"reference {reference.asset_type}:{reference.name} uses unregistered zone {reference.source_zone!r}"
            )
        if reference not in self.references:
            self.references.append(reference)

    def ingest_material_techset_walk(self, zone: str, report: Mapping[str, Any], expanded: bytes) -> list[AssetDefinition]:
        if report.get("format") != WALK_FORMAT:
            raise AssetIndexError(f"{zone}: expected {WALK_FORMAT!r}, got {report.get('format')!r}")
        actual = ZoneFingerprint.from_bytes(zone, expanded)
        expected_hash = str(report.get("expandedSha256") or "").lower()
        if expected_hash and expected_hash != actual.sha256:
            raise StaleIndexError(f"{zone}: walker expandedSha256 {expected_hash} != {actual.sha256}")
        self.add_zone(actual)
        made: list[AssetDefinition] = []
        for row in report.get("rows") or []:
            xtype = int(row["xassetType"])
            if xtype == MATERIAL: asset_type = "material"
            elif xtype == TECHNIQUE_SET: asset_type = "material_technique_set"
            else:
                raise AssetIndexError(
                    f"{zone}: unsupported row xassetType={xtype}; walker report is corrupt or from a different schema"
                )
            start, end = int(row["sourceStart"]), int(row["sourceEnd"])
            if start < 0 or end <= start or end > len(expanded):
                raise AssetIndexError(f"{zone}: invalid exact extent {start}..{end} for {asset_type}")
            definition = AssetDefinition(
                asset_type, _extract_walk_name(row), zone, start, end,
                hashlib.sha256(expanded[start:end]).hexdigest(), _row_metadata(row),
            )
            self.add_definition(definition); made.append(definition)
        return made

    def candidates(self, asset_type: str, name: str) -> tuple[AssetDefinition, ...]:
        return tuple(self.definitions.get((asset_type, name), ()))

    def resolve(self, asset_type: str, name: str, search_order: Sequence[str] | None = None) -> AssetDefinition:
        candidates = list(self.candidates(asset_type, name))
        if not candidates:
            raise MissingAssetError(f"no definition for {asset_type}:{name}")

        rank: dict[str, int] | None = None
        if search_order is not None:
            rank = {z: i for i, z in enumerate(search_order)}
            candidates = [x for x in candidates if x.zone in rank]
            if not candidates:
                raise MissingAssetError(
                    f"{asset_type}:{name} exists, but not in dependency closure {list(search_order)!r}"
                )

        identities = {x.content_identity for x in candidates}
        if len(identities) == 1:
            if rank is not None:
                candidates.sort(key=lambda x: (rank[x.zone], x.zone, x.start))
            else:
                candidates.sort(key=lambda x: (x.zone, x.start))
            return candidates[0]

        if rank is None:
            detail = ", ".join(f"{x.zone}@{x.start}:sha256={x.sha256[:12]}" for x in candidates)
            raise AmbiguousAssetError(
                f"conflicting definitions for {asset_type}:{name}; dependency order required: {detail}"
            )

        best_rank = min(rank[x.zone] for x in candidates)
        best = [x for x in candidates if rank[x.zone] == best_rank]
        if len({x.content_identity for x in best}) != 1:
            raise AmbiguousAssetError(
                f"multiple conflicting definitions for {asset_type}:{name} at dependency rank {best_rank}"
            )
        return sorted(best, key=lambda x: (x.zone, x.start))[0]

    def references_for(self, asset_type: str, name: str) -> tuple[AssetReference, ...]:
        return tuple(x for x in self.references if x.asset_type == asset_type and x.name == name)

    def verify_zone_bytes(self, zone: str, data: bytes) -> None:
        expected = self.zones.get(zone)
        if expected is None: raise MissingAssetError(f"zone {zone!r} is not indexed")
        actual = ZoneFingerprint.from_bytes(zone, data)
        if actual != expected:
            raise StaleIndexError(
                f"zone {zone!r} bytes do not match index: expected {expected.sha256}/{expected.size}, got {actual.sha256}/{actual.size}"
            )

    def as_dict(self) -> dict[str, Any]:
        defs = [d.as_dict() for key in sorted(self.definitions) for d in self.definitions[key]]
        refs = sorted((r.as_dict() for r in self.references), key=lambda r:(r["assetType"],r["name"],r["sourceZone"],-1 if r["ownerStart"] is None else r["ownerStart"]))
        return {
            "format": FORMAT,
            "zones": {z:self.zones[z].as_dict() for z in sorted(self.zones)},
            "definitions": defs, "references": refs,
            "summary": {"zoneCount":len(self.zones),"definitionCount":len(defs),"referenceCount":len(refs),"assetKeyCount":len(self.definitions)},
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RetailAssetIndex":
        if raw.get("format") != FORMAT:
            raise AssetIndexError(f"expected index format {FORMAT!r}, got {raw.get('format')!r}")
        out = cls()
        for zone,row in (raw.get("zones") or {}).items():
            out.add_zone(ZoneFingerprint(str(zone),str(row["sha256"]).lower(),int(row["size"])))
        for row in raw.get("definitions") or []: out.add_definition(AssetDefinition.from_dict(row))
        for row in raw.get("references") or []: out.add_reference(AssetReference.from_dict(row))
        return out

    @classmethod
    def load(cls, path: Path) -> "RetailAssetIndex":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(self.as_dict(),indent=2,sort_keys=True)+"\n",encoding="utf-8")


def _parse_zone_paths(values: Iterable[str]) -> dict[str, Path]:
    out: dict[str,Path] = {}
    for item in values:
        if "=" not in item: raise AssetIndexError(f"expected ZONE=PATH, got {item!r}")
        zone,raw = item.split("=",1)
        if not zone or not raw: raise AssetIndexError(f"expected non-empty ZONE=PATH, got {item!r}")
        if zone in out: raise AssetIndexError(f"duplicate zone argument {zone!r}")
        out[zone] = Path(raw)
    return out


def _cmd_build(args: argparse.Namespace) -> int:
    walks,expanded_paths = _parse_zone_paths(args.walk),_parse_zone_paths(args.expanded)
    if set(walks) != set(expanded_paths): raise AssetIndexError("--walk and --expanded must provide the same exact zone names")
    index = RetailAssetIndex()
    for zone in sorted(walks):
        index.ingest_material_techset_walk(zone,json.loads(walks[zone].read_text(encoding="utf-8")),expanded_paths[zone].read_bytes())
    index.save(args.out); print(json.dumps(index.as_dict()["summary"],indent=2,sort_keys=True)); return 0


def _cmd_resolve(args: argparse.Namespace) -> int:
    index = RetailAssetIndex.load(args.index)
    order = [x for x in args.search_order.split(",") if x] if args.search_order else None
    print(json.dumps(index.resolve(args.asset_type,args.name,order).as_dict(),indent=2,sort_keys=True)); return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    index = RetailAssetIndex.load(args.index); zones = _parse_zone_paths(args.expanded)
    for zone,path in zones.items(): index.verify_zone_bytes(zone,path.read_bytes())
    print(json.dumps({"verifiedZones":sorted(zones)},indent=2)); return 0


def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    b=sub.add_parser("build"); b.add_argument("--walk",action="append",default=[],metavar="ZONE=PATH",required=True); b.add_argument("--expanded",action="append",default=[],metavar="ZONE=PATH",required=True); b.add_argument("--out",type=Path,required=True); b.set_defaults(func=_cmd_build)
    r=sub.add_parser("resolve"); r.add_argument("index",type=Path); r.add_argument("asset_type"); r.add_argument("name"); r.add_argument("--search-order"); r.set_defaults(func=_cmd_resolve)
    v=sub.add_parser("verify"); v.add_argument("index",type=Path); v.add_argument("--expanded",action="append",default=[],metavar="ZONE=PATH",required=True); v.set_defaults(func=_cmd_verify)
    return p


def main() -> int:
    a=build_parser().parse_args(); return int(a.func(a))

if __name__ == "__main__": raise SystemExit(main())
