#!/usr/bin/env python3
"""Close the current-R2 MP7 76-bone XAnim namespace against raw view models.

`viewmodel_hands_no_model` is admitted only as a candidate discovered by the
complete native-OAT common_mp XModel census. Promotion is based exclusively on
fresh raw current-R2 serialized XModel + ScriptString evidence. The Weapon gun
and magazine names remain source-authored by both physical MP7 Weapon copies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from t6_mp7_r2_xmodel_target_probe_v1 import find_inline_xmodel, track_namespace, compare_model
from t6_xmodel_skeleton_normalize_v2 import normalize_skeleton

FORMAT = "t6-mp7-r2-viewhands-binding-v1"
EXPECTED_STREAM_BYTES = 206_493_911
EXPECTED_STREAM_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
VIEWHANDS_CANDIDATE = "viewmodel_hands_no_model"


class BindingError(RuntimeError):
    pass


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise BindingError(msg)


def load_model(data: bytes, name: str, role: str, anim_ns: dict) -> dict:
    walk = find_inline_xmodel(data, name)
    require(walk["blockers"] == [], f"{name}: XModel walk blockers {walk['blockers']}")
    skel = normalize_skeleton(data, walk["assetFixedStart"], identity_name=name)
    require(skel["validation"]["allBoneNamesResolved"], f"{name}: unresolved bone names")
    require(skel["validation"]["hierarchyValid"], f"{name}: invalid hierarchy")
    comparison = compare_model(skel, anim_ns)
    return {
        "role": role,
        "name": name,
        "xmodelFixedStart": walk["assetFixedStart"],
        "xmodelSerializedEnd": walk["assetSerializedEnd"],
        "xmodelSerializedBytes": walk["assetSerializedBytes"],
        "xmodelSerializedSha256": walk["assetSerializedSha256"],
        "numBones": skel["skeleton"]["numBones"],
        "numRootBones": skel["skeleton"]["numRootBones"],
        "numSurfs": walk["xmodel"]["numSurfs"],
        "numLods": walk["xmodel"]["numLods"],
        "skeletonSource": skel["skeletonSource"],
        "boneScriptStringIds": [int(b["scriptStringId"]) for b in skel["skeleton"]["bones"]],
        "boneNames": [b["name"] for b in skel["skeleton"]["bones"]],
        "bindingComparison": comparison,
    }


def build(stream_path: Path, models_path: Path, notetracks_path: Path) -> dict:
    data = stream_path.read_bytes()
    require(len(data) == EXPECTED_STREAM_BYTES, f"expanded bytes {len(data)} != {EXPECTED_STREAM_BYTES}")
    stream_sha = hashlib.sha256(data).hexdigest()
    require(stream_sha == EXPECTED_STREAM_SHA256, f"expanded SHA mismatch: {stream_sha}")
    models = json.loads(models_path.read_text(encoding="utf-8"))
    notetracks = json.loads(notetracks_path.read_text(encoding="utf-8"))
    require(models.get("format") == "t6-mp7-r2-model-targets-v1", "wrong model-target manifest")
    require(notetracks.get("format") == "t6-mp7-r2-xanim-notetrack-retained-closure-v1", "wrong XAnim closure")
    anim_ns = track_namespace(data, notetracks)
    require(anim_ns["allFullTargetsSameBoneSet"] is True, "full MP7 XAnims do not share one exact bone set")
    require(anim_ns["uniqueBoneScriptStringCountAcrossFullTargets"] == 76, "MP7 full-animation union is not 76 bones")

    rows = [
        load_model(data, VIEWHANDS_CANDIDATE, "viewHandsCandidate", anim_ns),
        load_model(data, models["references"]["gunModel"], "gunModel", anim_ns),
        load_model(data, models["references"]["attachViewModel7"], "attachViewModel7", anim_ns),
    ]

    anim_ids = set(anim_ns["scriptStringIds"])
    union_ids: set[int] = set()
    owner_roles: dict[int, list[str]] = {}
    for row in rows:
        for sid in row["boneScriptStringIds"]:
            if sid in anim_ids:
                union_ids.add(sid)
                owner_roles.setdefault(sid, []).append(row["role"])
    missing_ids = sorted(anim_ids - union_ids)
    name_by_id = dict(zip(anim_ns["scriptStringIds"], anim_ns["names"]))
    missing_names = [name_by_id[sid] for sid in missing_ids]
    overlapping = {str(sid): roles for sid, roles in sorted(owner_roles.items()) if len(roles) > 1}

    return {
        "format": FORMAT,
        "source": {"expandedCommonMp": {"bytes": len(data), "sha256": stream_sha}},
        "candidateProvenance": {
            "viewHandsCandidate": VIEWHANDS_CANDIDATE,
            "locator": "complete pinned-OAT current-R2 common_mp XModel census run 34261677938",
            "locatorIsAuthority": False,
            "promotionAuthority": "raw serialized XModel skeleton + current-R2 ScriptString identity",
        },
        "animationNamespace": {
            "fullTargetCount": anim_ns["fullTargetCount"],
            "trackCountPerFullTarget": anim_ns["trackCountPerFullTarget"],
            "boneCount": anim_ns["uniqueBoneScriptStringCountAcrossFullTargets"],
            "distinctBoneSets": anim_ns["distinctBoneSetsAcrossFullTargets"],
            "distinctTrackOrders": anim_ns["distinctTrackOrdersAcrossFullTargets"],
            "scriptStringIds": anim_ns["scriptStringIds"],
            "names": anim_ns["names"],
        },
        "models": rows,
        "combinedBinding": {
            "matchedAnimationBoneCount": len(union_ids),
            "animationBoneCount": len(anim_ids),
            "coversAllAnimationBones": union_ids == anim_ids,
            "missingScriptStringIds": missing_ids,
            "missingBoneNames": missing_names,
            "overlappingAnimationBoneOwners": overlapping,
        },
        "proofBoundary": (
            "The candidate name was located by a complete native-OAT XModel census, but binding promotion uses only raw current-R2 XModel records, normalized skeletons, and exact ScriptString identities. This proves or disproves 76-bone namespace coverage by the candidate hands + source-authored MP7 gun + source-authored MP7 magazine model set. It does not yet prove which visible faction-specific hand mesh the runtime selects, nor final DObj model ordering/attachment transforms beyond the source Weapon fields."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True)
    ap.add_argument("--models", type=Path, required=True)
    ap.add_argument("--notetracks", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.stream, args.models, args.notetracks)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "models": [{
            "role": r["role"], "name": r["name"], "bones": r["numBones"],
            "surfs": r["numSurfs"], "matched": r["bindingComparison"]["matchedAnimationUnionBoneCount"]
        } for r in doc["models"]],
        "combinedBinding": doc["combinedBinding"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
