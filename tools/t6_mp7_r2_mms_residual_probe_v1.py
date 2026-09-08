#!/usr/bin/env python3
"""Test the one residual MP7 XAnim bone against the raw MMS view XModel.

The base hands + MP7 gun + MP7 magazine set leaves exactly ScriptString 340,
`j_mms_flip`, unmatched. `t6_attach_optic_mms_view` is admitted only as a
candidate from the complete pinned-OAT current-R2 common_mp XModel census.
Promotion here is based solely on its fresh raw serialized XModel skeleton
prefix. Downstream Material/TechniqueSet dispatch is explicitly outside this
bone-ownership proof and is not skipped or treated as resolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_mp7_r2_xmodel_target_probe_v1 import find_inline_xmodel, track_namespace
from t6_xmodel_skeleton_normalize_v1 import parse_script_strings

FORMAT = "t6-mp7-r2-mms-residual-probe-v1"
EXPECTED_STREAM_BYTES = 206_493_911
EXPECTED_STREAM_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
MMS_MODEL = "t6_attach_optic_mms_view"
EXPECTED_RESIDUAL_ID = 340
EXPECTED_RESIDUAL_NAME = "j_mms_flip"


class ProbeError(RuntimeError):
    pass


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ProbeError(msg)


def one_section(walk: dict, name: str) -> dict:
    rows = [s for s in walk["sections"] if s["name"] == name]
    require(len(rows) == 1, f"{name}: expected exactly one section, got {len(rows)}")
    return rows[0]


def build(stream_path: Path, notetracks_path: Path) -> dict:
    data = stream_path.read_bytes()
    require(len(data) == EXPECTED_STREAM_BYTES, "expanded byte count changed")
    sha = hashlib.sha256(data).hexdigest()
    require(sha == EXPECTED_STREAM_SHA256, f"expanded SHA mismatch {sha}")
    notetracks = json.loads(notetracks_path.read_text(encoding="utf-8"))
    ns = track_namespace(data, notetracks)
    by_id = dict(zip(ns["scriptStringIds"], ns["names"]))
    require(by_id.get(EXPECTED_RESIDUAL_ID) == EXPECTED_RESIDUAL_NAME, "residual ScriptString identity changed")

    walk = find_inline_xmodel(data, MMS_MODEL)
    require(walk["blockers"], "expected MMS downstream Material blocker disappeared; review proof boundary")
    require(all(b.get("kind") == "inline_external_asset_reference_requires_xasset_dispatch" for b in walk["blockers"]),
            f"unexpected MMS blocker class: {walk['blockers']}")
    bone_sec = one_section(walk, "XModel.boneNames")
    num_bones = int(walk["xmodel"]["numBones"])
    require(bone_sec["end"] - bone_sec["start"] == num_bones * 2, "MMS boneNames section size mismatch")
    bone_ids = list(struct.unpack_from(f"<{num_bones}H", data, bone_sec["start"])) if num_bones else []
    scripts = parse_script_strings(data)
    require(all(sid < scripts["count"] for sid in bone_ids), "MMS bone ScriptString outside table")
    bone_names = [scripts["strings"][sid] for sid in bone_ids]
    require(all(name is not None for name in bone_names), "MMS bone name unresolved")
    require(EXPECTED_RESIDUAL_ID in bone_ids, "MMS XModel skeleton prefix does not own residual j_mms_flip ScriptString")
    idx = bone_ids.index(EXPECTED_RESIDUAL_ID)
    require(bone_names[idx] == EXPECTED_RESIDUAL_NAME, "MMS residual bone name mismatch")

    anim_ids = set(ns["scriptStringIds"])
    matched = [(sid, name) for sid, name in zip(bone_ids, bone_names) if sid in anim_ids]
    return {
        "format": FORMAT,
        "source": {"expandedCommonMp": {"bytes": len(data), "sha256": sha}},
        "candidateProvenance": {
            "model": MMS_MODEL,
            "locator": "complete pinned-OAT current-R2 common_mp XModel census run 34261677938",
            "locatorIsAuthority": False,
            "promotionAuthority": "fresh raw serialized XModel fixed record + pre-material boneNames prefix + ScriptString identity"
        },
        "residual": {"scriptStringId": EXPECTED_RESIDUAL_ID, "name": EXPECTED_RESIDUAL_NAME},
        "xmodel": {
            "name": MMS_MODEL,
            "assetFixedStart": walk["assetFixedStart"],
            "numBones": num_bones,
            "numRootBones": int(walk["xmodel"]["numRootBones"]),
            "numSurfs": int(walk["xmodel"]["numSurfs"]),
            "numLods": int(walk["xmodel"]["numLods"]),
            "boneNamesRawRange": [bone_sec["start"], bone_sec["end"]],
            "boneScriptStringIds": bone_ids,
            "boneNames": bone_names,
            "matchedAnimationBones": [{"scriptStringId": sid, "name": name} for sid, name in matched],
            "downstreamBlockersPreserved": walk["blockers"],
        },
        "residualOwnedByMmsModel": True,
        "proofBoundary": "This proves that the sole bone absent from the base hands+MP7-gun+MP7-magazine raw model set is physically present in the pre-material skeleton prefix of the raw current-R2 MMS optic view XModel. The unresolved downstream Material/TechniqueSet dispatch remains a blocker for whole-XModel serialization and is not crossed by this proof. This does not claim MMS is equipped by base mp7_mp; it establishes optional attachment support in the shared MP7 XAnim namespace."
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True)
    ap.add_argument("--notetracks", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.stream, args.notetracks)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"residual": doc["residual"], "xmodel": doc["xmodel"], "residualOwnedByMmsModel": True}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
