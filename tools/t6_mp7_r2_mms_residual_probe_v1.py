#!/usr/bin/env python3
"""Test the one residual MP7 XAnim bone against the raw MMS view XModel.

The base hands + MP7 gun + MP7 magazine set leaves exactly ScriptString 340,
`j_mms_flip`, unmatched. `t6_attach_optic_mms_view` is admitted only as a
candidate from the complete pinned-OAT current-R2 common_mp XModel census.
Promotion here is based solely on its fresh raw serialized XModel skeleton.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_mp7_r2_xmodel_target_probe_v1 import find_inline_xmodel, track_namespace
from t6_xmodel_skeleton_normalize_v2 import normalize_skeleton

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
    require(walk["blockers"] == [], f"MMS XModel blockers: {walk['blockers']}")
    skel = normalize_skeleton(data, walk["assetFixedStart"], identity_name=MMS_MODEL)
    require(skel["validation"]["allBoneNamesResolved"], "MMS skeleton has unresolved names")
    require(skel["validation"]["hierarchyValid"], "MMS skeleton hierarchy invalid")
    ids = [int(b["scriptStringId"]) for b in skel["skeleton"]["bones"]]
    names = [b["name"] for b in skel["skeleton"]["bones"]]
    require(EXPECTED_RESIDUAL_ID in ids, "MMS XModel does not own residual j_mms_flip ScriptString")
    idx = ids.index(EXPECTED_RESIDUAL_ID)
    require(names[idx] == EXPECTED_RESIDUAL_NAME, "MMS residual bone name mismatch")

    anim_ids = set(ns["scriptStringIds"])
    matched = [(sid, name) for sid, name in zip(ids, names) if sid in anim_ids]
    return {
        "format": FORMAT,
        "source": {"expandedCommonMp": {"bytes": len(data), "sha256": sha}},
        "candidateProvenance": {
            "model": MMS_MODEL,
            "locator": "complete pinned-OAT current-R2 common_mp XModel census run 34261677938",
            "locatorIsAuthority": False,
            "promotionAuthority": "fresh raw serialized XModel skeleton + ScriptString identity"
        },
        "residual": {"scriptStringId": EXPECTED_RESIDUAL_ID, "name": EXPECTED_RESIDUAL_NAME},
        "xmodel": {
            "name": MMS_MODEL,
            "assetFixedStart": walk["assetFixedStart"],
            "assetSerializedEnd": walk["assetSerializedEnd"],
            "assetSerializedBytes": walk["assetSerializedBytes"],
            "assetSerializedSha256": walk["assetSerializedSha256"],
            "numBones": skel["skeleton"]["numBones"],
            "numRootBones": skel["skeleton"]["numRootBones"],
            "numSurfs": walk["xmodel"]["numSurfs"],
            "numLods": walk["xmodel"]["numLods"],
            "boneScriptStringIds": ids,
            "boneNames": names,
            "matchedAnimationBones": [{"scriptStringId": sid, "name": name} for sid, name in matched],
        },
        "residualOwnedByMmsModel": True,
        "proofBoundary": "This proves that the sole bone absent from the base hands+MP7-gun+MP7-magazine raw model set is physically present in the raw current-R2 MMS optic view XModel. It does not claim MMS is equipped by the base mp7_mp Weapon; it establishes that the shared MP7 XAnim namespace contains optional attachment support."
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
