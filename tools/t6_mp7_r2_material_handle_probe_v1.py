#!/usr/bin/env python3
"""Probe exact current-R2 MP7 export-model Material handles from serialized XModels.

This is a diagnostic closure layer, not yet final Material authority. It uses the
retail-boundary XModel serialized walker and exact current-R2 model starts already
closed by the mesh layer. Direct surface Material names are accepted only when the
walker actually consumes exactly `XModel.materialHandles[i].Material.name`.
Nested Material references (for example thermalMaterial) are retained separately.
Packed handles remain unresolved for allocator/backreference replay.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_xmodel_serialized_walker import XModelWalker

FORMAT = "t6-mp7-r2-material-handle-probe-v1"
TARGETS = [
    {"role":"gunModel","stream":"common_mp","name":"t6_wpn_smg_mp7_view","start":16904908,"surfaceCount":8},
    {"role":"attachViewModel7","stream":"common_mp","name":"t6_attach_mag_mp7_view","start":17273272,"surfaceCount":3},
    {"role":"viewHandsVisibleShortSleeve","stream":"faction_seals_mp","name":"c_usa_mp_seal6_shortsleeve_viewhands","start":4259399,"surfaceCount":5},
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_cstring(raw: bytes, label: str) -> str:
    if not raw or raw[-1] != 0:
        raise ValueError(f"{label}: consumed Material.name range is not NUL terminated")
    payload = raw[:-1]
    if b"\0" in payload:
        raise ValueError(f"{label}: embedded NUL in Material.name range")
    return payload.decode("ascii")


def _material_name_sections(data: bytes, walk: dict, surface_count: int) -> tuple[dict[int,dict],dict[int,list[dict]]]:
    direct: dict[int,dict] = {}
    nested: dict[int,list[dict]] = {}
    sections = walk.get("sections", [])
    for i in range(surface_count):
        prefix = f"XModel.materialHandles[{i}].Material"
        direct_name = prefix + ".name"
        direct_candidates = [s for s in sections if str(s.get("name", "")) == direct_name]
        if len(direct_candidates) > 1:
            raise ValueError(f"surface {i}: multiple direct consumed Material.name sections: {direct_candidates}")
        if direct_candidates:
            s = direct_candidates[0]
            start = int(s["start"]); end = int(s["end"]); raw = data[start:end]
            direct[i] = {
                "name": _decode_cstring(raw, f"surface {i} direct Material"),
                "sourceStart": start, "sourceEnd": end, "sourceBytes": end-start,
                "sourceSha256": sha256(raw), "sectionName": s["name"],
            }
        rows = []
        for s in sections:
            name = str(s.get("name", ""))
            if not (name.startswith(prefix + ".") and name.endswith(".Material.name")):
                continue
            start = int(s["start"]); end = int(s["end"]); raw = data[start:end]
            rows.append({
                "name": _decode_cstring(raw, f"surface {i} nested Material"),
                "sourceStart": start, "sourceEnd": end, "sourceBytes": end-start,
                "sourceSha256": sha256(raw), "sectionName": name,
            })
        nested[i] = rows
    return direct, nested


def probe_one(data: bytes, target: dict) -> dict:
    walk = XModelWalker(data, int(target["start"])).walk_xmodel()
    x = walk["xmodel"]
    if x.get("name") != target["name"]:
        raise ValueError(f"{target['role']}: identity mismatch {x.get('name')!r} != {target['name']!r}")
    if int(x.get("numSurfs", -1)) != int(target["surfaceCount"]):
        raise ValueError(f"{target['role']}: surface count changed")
    blockers = walk.get("blockers") or []
    handles = x.get("materialHandles", [])
    if len(handles) != target["surfaceCount"]:
        raise ValueError(f"{target['role']}: expected {target['surfaceCount']} material handles, got {len(handles)}")
    direct, nested = _material_name_sections(data, walk, int(target["surfaceCount"]))
    rows = []
    for i, handle in enumerate(handles):
        rows.append({
            "surface": i,
            "handle": handle,
            "directMaterial": direct.get(i),
            "nestedMaterialReferences": nested.get(i, []),
        })
    kind_counts: dict[str,int] = {}
    for row in rows:
        kind = str(row["handle"].get("kind")); kind_counts[kind] = kind_counts.get(kind,0)+1
    return {
        **target,
        "assetSerializedEnd": walk.get("assetSerializedEnd"),
        "assetSerializedBytes": walk.get("assetSerializedBytes"),
        "assetSerializedSha256": walk.get("assetSerializedSha256"),
        "blockers": blockers,
        "materialHandleKindCounts": kind_counts,
        "directMaterialNameCount": len(direct),
        "nestedMaterialReferenceCount": sum(len(v) for v in nested.values()),
        "surfaceMaterials": rows,
    }


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--common-stream",type=Path,required=True); ap.add_argument("--faction-stream",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); args=ap.parse_args()
    streams={"common_mp":args.common_stream.read_bytes(),"faction_seals_mp":args.faction_stream.read_bytes()}
    doc={"format":FORMAT,"sources":{k:{"bytes":len(v),"sha256":sha256(v)} for k,v in streams.items()},"targets":[]}
    for target in TARGETS:
        doc["targets"].append(probe_one(streams[target["stream"]],target))
    surface_count=sum(t["surfaceCount"] for t in doc["targets"])
    direct_count=sum(t["directMaterialNameCount"] for t in doc["targets"])
    packed_count=sum(t["materialHandleKindCounts"].get("packed",0) for t in doc["targets"])
    blocker_count=sum(len(t["blockers"]) for t in doc["targets"])
    doc["summary"]={
        "targetCount":len(doc["targets"]),"surfaceCount":surface_count,
        "directMaterialNameCount":direct_count,
        "nestedMaterialReferenceCount":sum(t["nestedMaterialReferenceCount"] for t in doc["targets"]),
        "packedHandleCount":packed_count,"blockerCount":blocker_count,
        "allSurfaceMaterialsResolvedInline":direct_count==surface_count and packed_count==0 and blocker_count==0,
    }
    doc["proofBoundary"]=(
        "Exact current-R2 XModel identity and material-handle pointer classes come directly from the SHA-pinned serialized streams. "
        "A surface Material name is reported only for the exact direct walker section XModel.materialHandles[i].Material.name. "
        "Nested thermal/other Material references are preserved separately. Packed handles are not dereferenced by address arithmetic or naming; "
        "they remain open until exact VIRTUAL/backreference ownership replay resolves them."
    )
    payload=json.dumps(doc,indent=2,sort_keys=True)+"\n"; args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(payload,encoding="utf-8")
    print(json.dumps({**doc["summary"],"manifestSha256":sha256(payload.encode())},sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
