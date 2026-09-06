#!/usr/bin/env python3
"""Resolve retail T6 mp/playeranim.script references against XAnim evidence.

Inputs stay independently checkable:
- the exact retail RawFile text for mp/playeranim.script;
- a JSON XAnim inventory whose records expose name + track/bone names;
- a normalized XModel skeleton JSON.

The resolver never invents packed-name identities or bone aliases. Retail XAnim asset-name identity is joined with collision-checked ASCII case folding, matching T6 name lookup while preserving both source spellings. Bone-track binding remains exact resolved-name matching. A named XAnim can be classified as an exact skeleton subset or as a retail-compatible superset that contains animation-only controls. Unresolved animation names remain explicit blockers rather than being guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FORMAT = "t6-playeranim-retail-resolution-v2"
REF_RE = re.compile(r"^\s*(both|torso|legs)\s+([A-Za-z0-9_./+\-]+)\b")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def track_names(row: dict) -> list[str]:
    if isinstance(row.get("boneNames"), list):
        return [str(x) for x in row["boneNames"] if isinstance(x, str)]
    tracks = row.get("boneTracks", row.get("tracks"))
    if isinstance(tracks, list):
        out = []
        for t in tracks:
            if isinstance(t, dict) and isinstance(t.get("name"), str):
                out.append(t["name"])
        return out
    walk = row.get("walk")
    if isinstance(walk, dict) and isinstance(walk.get("bone_scriptstrings"), list):
        return [x["name"] for x in walk["bone_scriptstrings"] if isinstance(x, dict) and isinstance(x.get("name"), str)]
    return []


def flatten_xanims(value: Any, out: list[dict]) -> None:
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and track_names(value):
            out.append(value)
        for child in value.values():
            flatten_xanims(child, out)
    elif isinstance(value, list):
        for child in value:
            flatten_xanims(child, out)


def ascii_casefold(name: str) -> str:
    try:
        raw = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"non-ASCII XAnim asset name cannot use T6 ASCII identity fold: {name!r}") from exc
    return raw.lower().decode("ascii")


def build_inventory(path: Path) -> dict[str, dict]:
    rows: list[dict] = []
    flatten_xanims(load_json(path), rows)
    by_fold: dict[str, dict] = {}
    collisions: dict[str, list[str]] = {}
    exact_duplicates: set[str] = set()
    for row in rows:
        name = row["name"]
        key = ascii_casefold(name)
        prior = by_fold.get(key)
        if prior is not None:
            if prior["name"] == name:
                exact_duplicates.add(name)
            else:
                collisions.setdefault(key, [prior["name"]]).append(name)
            continue
        by_fold[key] = row
    if exact_duplicates:
        raise ValueError(f"ambiguous duplicate XAnim records: {sorted(exact_duplicates)[:20]}")
    if collisions:
        sample = {k: v for k, v in list(sorted(collisions.items()))[:20]}
        raise ValueError(f"ambiguous ASCII-casefold XAnim identity collisions: {sample}")
    return by_fold


def skeleton_names(path: Path) -> list[str]:
    doc = load_json(path)
    bones = doc.get("skeleton", {}).get("bones", [])
    names = [b.get("name") for b in bones if isinstance(b, dict)]
    if not names or any(not isinstance(x, str) or not x for x in names):
        raise ValueError("skeleton has missing/invalid bone names")
    if len(set(names)) != len(names):
        raise ValueError("skeleton has duplicate bone names")
    return names


def parse_playeranim(path: Path) -> list[dict]:
    text = path.read_text(encoding="latin1")
    rows = []
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.split("//", 1)[0].strip()
        m = REF_RE.match(stripped)
        if not m:
            continue
        rows.append({"line": line_no, "part": m.group(1), "animation": m.group(2), "source": line.rstrip()})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--playeranim", type=Path, required=True)
    ap.add_argument("--xanim-json", type=Path, required=True)
    ap.add_argument("--skeleton", type=Path, required=True)
    ap.add_argument("--prefix", action="append", default=[], help="optional animation-name prefix filter")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    skel = skeleton_names(args.skeleton)
    skel_set = set(skel)
    inventory = build_inventory(args.xanim_json)
    refs = parse_playeranim(args.playeranim)
    if args.prefix:
        refs = [r for r in refs if any(r["animation"].startswith(p) for p in args.prefix)]

    grouped: dict[str, list[dict]] = {}
    for ref in refs:
        grouped.setdefault(ref["animation"], []).append(ref)

    resolved = []
    unresolved = []
    for name in sorted(grouped):
        key = ascii_casefold(name)
        row = inventory.get(key)
        if row is None:
            unresolved.append({"name": name, "referenceName": name, "references": grouped[name]})
            continue
        asset_name = row["name"]
        tracks = track_names(row)
        track_set = set(tracks)
        if len(track_set) != len(tracks):
            raise ValueError(f"{name}: duplicate track names")
        matched = [n for n in tracks if n in skel_set]
        extra = [n for n in tracks if n not in skel_set]
        missing_model_bones = [n for n in skel if n not in track_set]
        resolved.append({
            "name": name,
            "referenceName": name,
            "resolvedAssetName": asset_name,
            "caseNormalizedMatch": asset_name != name,
            "rawStructOffset": row.get("rawStructOffset", row.get("raw_struct_offset", row.get("start"))),
            "numFrames": row.get("numFrames", row.get("numframes")),
            "frameRate": row.get("frameRate", row.get("framerate")),
            "trackCount": len(tracks),
            "matchedTrackCount": len(matched),
            "extraAnimationTrackCount": len(extra),
            "extraAnimationTracks": extra,
            "modelBonesNotAnimatedCount": len(missing_model_bones),
            "bindingClass": "exact-track-subset" if not extra else "animation-superset-intersection",
            "references": grouped[name],
        })

    doc = {
        "format": FORMAT,
        "authority": "retail playeranim RawFile + caller-supplied retail XAnim inventory + normalized retail XModel skeleton",
        "rules": {
            "animationAssetIdentity": "collision-checked ASCII case-insensitive lookup; both spellings retained",
            "casefoldCollisionsFailClosed": True,
            "exactBoneNameIntersectionOnly": True,
            "unresolvedNamesAreNotGuessed": True,
            "animationOnlyTracksAreReportedNotFabricated": True,
            "missingModelBonesNeedNotBeAnimatedByEveryClip": True,
        },
        "sources": {
            "playeranim": {"path": str(args.playeranim), "bytes": args.playeranim.stat().st_size, "sha256": sha256(args.playeranim)},
            "xanimInventory": {"path": str(args.xanim_json), "bytes": args.xanim_json.stat().st_size, "sha256": sha256(args.xanim_json)},
            "skeleton": {"path": str(args.skeleton), "bytes": args.skeleton.stat().st_size, "sha256": sha256(args.skeleton), "boneCount": len(skel)},
        },
        "summary": {
            "referenceLines": len(refs),
            "uniqueAnimationNames": len(grouped),
            "resolvedAnimationNames": len(resolved),
            "caseNormalizedAnimationMatches": sum(r["caseNormalizedMatch"] for r in resolved),
            "unresolvedAnimationNames": len(unresolved),
            "exactTrackSubsets": sum(r["bindingClass"] == "exact-track-subset" for r in resolved),
            "animationSupersetIntersections": sum(r["bindingClass"] == "animation-superset-intersection" for r in resolved),
        },
        "resolved": resolved,
        "unresolved": unresolved,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
