#!/usr/bin/env python3
"""Probe exact current-R2 MP7 view XModels against the MP7 XAnim bone namespace.

Target XModel names come only from the retained native-OAT Weapon model-reference
manifest. Each target must be found as an inline serialized XModel name in the
same SHA-pinned common_mp stream; the candidate fixed record is then walked and
normalized with the existing fail-closed XModel skeleton normalizer.

XAnim track order is not assumed to equal XModel skeleton order. T6 serializes
per-animation tracks in encoding-category order, so binding comparisons use
exact ScriptString identity and retain the observed per-clip ordering facts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from t6_xanim_normalize_v1 import normalize as normalize_xanim
from t6_xmodel_serialized_walker import XModelWalker, XMODEL_SIZE
from t6_xmodel_skeleton_normalize_v2 import normalize_skeleton

FORMAT = "t6-mp7-r2-xmodel-target-probe-v1"
EXPECTED_STREAM_BYTES = 206_493_911
EXPECTED_STREAM_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
FOLLOW = 0xFFFFFFFF


class ProbeError(RuntimeError):
    pass


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ProbeError(msg)


def find_inline_xmodel(data: bytes, name: str) -> dict:
    needle = name.encode("ascii") + b"\0"
    occurrences = []
    p = 0
    while True:
        hit = data.find(needle, p)
        if hit < 0:
            break
        occurrences.append(hit)
        p = hit + 1
    matches = []
    for hit in occurrences:
        start = hit - XMODEL_SIZE
        if start < 0 or struct.unpack_from("<I", data, start)[0] != FOLLOW:
            continue
        try:
            walk = XModelWalker(data, start).walk_xmodel()
        except Exception:
            continue
        if walk.get("xmodel", {}).get("name") != name or walk["assetFixedStart"] != start:
            continue
        matches.append(walk)
    if len(matches) != 1:
        raise ProbeError(f"{name}: expected one exact inline-name XModel record, got {len(matches)} from {len(occurrences)} literal occurrences")
    return matches[0]


def track_namespace(data: bytes, notetrack_closure: dict) -> dict:
    full = [x for x in notetrack_closure["targets"] if int(x["bones"]) == 76]
    require(full, "retained closure has no 76-track target")
    docs = [normalize_xanim(data, int(x["rawStructOffset"])) for x in full]
    per_clip = []
    union_ids: set[int] = set()
    name_by_id: dict[int, str] = {}
    set_fingerprints: Counter[tuple[int, ...]] = Counter()
    order_fingerprints: Counter[tuple[int, ...]] = Counter()
    for doc in docs:
        ids = [int(t["scriptString"]) for t in doc["boneTracks"]]
        names = [t["name"] for t in doc["boneTracks"]]
        require(len(ids) == 76 and len(set(ids)) == 76, f"{doc['name']}: not 76 unique track ScriptStrings")
        for sid, name in zip(ids, names):
            old = name_by_id.setdefault(sid, name)
            require(old == name, f"ScriptString {sid}: name changed {old!r} -> {name!r}")
        union_ids.update(ids)
        set_fingerprints[tuple(sorted(ids))] += 1
        order_fingerprints[tuple(ids)] += 1
        per_clip.append({"name": doc["name"], "scriptStringIds": ids, "names": names})
    union_sorted = sorted(union_ids)
    return {
        "fullTargetCount": len(docs),
        "trackCountPerFullTarget": 76,
        "uniqueBoneScriptStringCountAcrossFullTargets": len(union_sorted),
        "scriptStringIds": union_sorted,
        "names": [name_by_id[sid] for sid in union_sorted],
        "distinctBoneSetsAcrossFullTargets": len(set_fingerprints),
        "distinctTrackOrdersAcrossFullTargets": len(order_fingerprints),
        "allFullTargetsSameBoneSet": len(set_fingerprints) == 1,
        "allFullTargetsSameTrackOrder": len(order_fingerprints) == 1,
        "perClip": per_clip,
    }


def compare_model(skel: dict, anim_ns: dict) -> dict:
    bones = skel["skeleton"]["bones"]
    mids = [int(b["scriptStringId"]) for b in bones]
    mnames = [b["name"] for b in bones]
    aids = anim_ns["scriptStringIds"]
    anames = anim_ns["names"]
    aset = set(aids); mset = set(mids)
    matched = [sid for sid in aids if sid in mset]
    missing = [name for sid, name in zip(aids, anames) if sid not in mset]
    extra = [name for sid, name in zip(mids, mnames) if sid not in aset]
    return {
        "modelBoneCount": len(mids),
        "animationUnionBoneCount": len(aids),
        "matchedAnimationUnionBoneCount": len(matched),
        "coverageFraction": len(matched) / len(aids),
        "allAnimationUnionBonesPresent": len(matched) == len(aids),
        "missingAnimationBoneNames": missing,
        "extraModelBoneNames": extra,
        "modelBoneScriptStringIds": mids,
        "modelBoneNames": mnames,
    }


def build(stream: Path, models_manifest: Path, notetrack_manifest: Path) -> dict:
    data = stream.read_bytes()
    require(len(data) == EXPECTED_STREAM_BYTES, f"expanded bytes {len(data)} != {EXPECTED_STREAM_BYTES}")
    sha = hashlib.sha256(data).hexdigest()
    require(sha == EXPECTED_STREAM_SHA256, f"expanded stream SHA mismatch {sha}")
    models = json.loads(models_manifest.read_text(encoding="utf-8"))
    notetracks = json.loads(notetrack_manifest.read_text(encoding="utf-8"))
    require(models.get("format") == "t6-mp7-r2-model-targets-v1", "wrong model-target manifest")
    require(notetracks.get("format") == "t6-mp7-r2-xanim-notetrack-retained-closure-v1", "wrong notetrack manifest")
    anim_ns = track_namespace(data, notetracks)

    targets = []
    for role in ("gunModel", "attachViewModel7"):
        name = models["references"][role]
        walk = find_inline_xmodel(data, name)
        require(walk["blockers"] == [], f"{name}: XModel walk blockers {walk['blockers']}")
        skel = normalize_skeleton(data, walk["assetFixedStart"], identity_name=name)
        require(skel["validation"]["allBoneNamesResolved"], f"{name}: unresolved bone names")
        require(skel["validation"]["hierarchyValid"], f"{name}: invalid skeleton hierarchy")
        targets.append({
            "weaponRole": role,
            "name": name,
            "xmodelFixedStart": walk["assetFixedStart"],
            "xmodelSerializedEnd": walk["assetSerializedEnd"],
            "xmodelSerializedBytes": walk["assetSerializedBytes"],
            "xmodelSerializedSha256": walk["assetSerializedSha256"],
            "numSurfs": walk["xmodel"]["numSurfs"],
            "numLods": walk["xmodel"]["numLods"],
            "skeletonSource": skel["skeletonSource"],
            "bindingComparison": compare_model(skel, anim_ns),
        })

    return {
        "format": FORMAT,
        "source": {"expandedCommonMp": {"bytes": len(data), "sha256": sha}},
        "animationNamespace": anim_ns,
        "targets": targets,
        "summary": {
            "animationTrackCountPerFullTarget": 76,
            "animationUnionBoneCount": anim_ns["uniqueBoneScriptStringCountAcrossFullTargets"],
            "fullAnimationTargetCount": anim_ns["fullTargetCount"],
            "distinctAnimationBoneSets": anim_ns["distinctBoneSetsAcrossFullTargets"],
            "distinctAnimationTrackOrders": anim_ns["distinctTrackOrdersAcrossFullTargets"],
            "gunModelMatchedUnionBones": targets[0]["bindingComparison"]["matchedAnimationUnionBoneCount"],
            "gunModelCoversAnimationUnion": targets[0]["bindingComparison"]["allAnimationUnionBonesPresent"],
            "attachmentMatchedUnionBones": targets[1]["bindingComparison"]["matchedAnimationUnionBoneCount"],
            "attachmentCoversAnimationUnion": targets[1]["bindingComparison"]["allAnimationUnionBonesPresent"],
        },
        "proofBoundary": (
            "The two view XModels named directly by the source Weapon are resolved as exact inline-name serialized XModel records in the same current-R2 common_mp stream and compared by exact ScriptString identity to the union of the 76-track MP7 XAnim bone namespaces. Per-animation track order is retained but is not treated as XModel skeleton order. If the Weapon-authored models are incomplete, this probe does not infer a view-hands model; the residual namespace remains an explicit next binding gate."
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
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    for t in doc["targets"]:
        c=t["bindingComparison"]
        print(f"{t['weaponRole']} {t['name']} bones={c['modelBoneCount']} matched={c['matchedAnimationUnionBoneCount']}/{c['animationUnionBoneCount']} surfs={t['numSurfs']} sha256={t['xmodelSerializedSha256']}")
        if c['missingAnimationBoneNames']:
            print("missing=" + ",".join(c['missingAnimationBoneNames']))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
