#!/usr/bin/env python3
"""Fail-closed current-R2 MP7 ordinary XAnim motion closure.

This consumes only targets already retained by the MP7 Weapon->XAnim ownership
closure. For every target it re-normalizes the exact serialized XAnimParts
record from the freshly expanded current-R2 common_mp stream, requires exact
pool exhaustion, exact record identity, exact notetrack reproduction, and then
applies the separately retained T6 quaternion component semantics.

This closes serialized ordinary bone-track payload decoding. It intentionally
does not claim XModel bind-pose composition or ordinary animated root-bone
translation composition; those require a target skeleton/binding proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from t6_xanim_normalize_v1 import normalize
from t6_xanim_quaternion_semantics import augment_normalized_xanim

FORMAT = "t6-mp7-r2-xanim-motion-closure-v1"
EXPECTED_STREAM_BYTES = 206_493_911
EXPECTED_STREAM_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
EXPECTED_HALF_PROOF_FORMAT = "t6-xanim-half-quaternion-semantics-proof-v1"


class MotionClosureError(RuntimeError):
    pass


def canonical_sha256(doc: Any) -> str:
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MotionClosureError(message)


def target_notifies(doc: dict) -> list[list[Any]]:
    return [[n.get("name"), n.get("scriptString"), n.get("time")] for n in doc.get("notifies", [])]


def frame_count(track: dict | None) -> int:
    if not track:
        return 0
    if "rawInt16Frames" in track:
        return len(track["rawInt16Frames"])
    if "decodedFrames" in track:
        return len(track["decodedFrames"])
    if "constant" in track or track.get("type") in ("HALF_QUAT_NO_SIZE", "FULL_QUAT_NO_SIZE", "TRANS_NO_SIZE"):
        return 1
    return 0


def build(stream_path: Path, retained_path: Path, half_proof_path: Path) -> dict:
    stream = stream_path.read_bytes()
    require(len(stream) == EXPECTED_STREAM_BYTES, f"expanded stream bytes {len(stream)} != {EXPECTED_STREAM_BYTES}")
    stream_sha = hashlib.sha256(stream).hexdigest()
    require(stream_sha == EXPECTED_STREAM_SHA256, f"expanded stream SHA mismatch: {stream_sha}")

    retained = json.loads(retained_path.read_text(encoding="utf-8"))
    half = json.loads(half_proof_path.read_text(encoding="utf-8"))
    require(retained.get("format") == "t6-mp7-r2-xanim-notetrack-retained-closure-v1", "wrong retained MP7 closure format")
    require(retained["source"]["expandedCommonMp"]["sha256"] == stream_sha, "retained closure stream SHA disagrees")
    require(retained["summary"]["uniqueTargetXAnimCount"] == 23, "retained target count is not 23")
    require(half.get("format") == EXPECTED_HALF_PROOF_FORMAT, "wrong half-quaternion proof format")
    require(half.get("mapping", {}).get("halfQuatRaw0") == "z", "half quaternion raw0 mapping changed")
    require(half.get("mapping", {}).get("halfQuatRaw1") == "w", "half quaternion raw1 mapping changed")
    require(abs(float(half.get("engineScale", 0.0)) - (1.0 / 32767.0)) < 1e-15, "half quaternion scale changed")

    quat_types: Counter[str] = Counter()
    trans_types: Counter[str] = Counter()
    total_quat_keys = 0
    total_trans_keys = 0
    total_tracks = 0
    long_index_tracks = 0
    random_data_int_records = 0
    target_rows = []

    for expected in retained["targets"]:
        start = int(expected["rawStructOffset"])
        doc = normalize(stream, start)
        require(doc["name"] == expected["name"], f"{expected['name']}: normalized name mismatch {doc['name']!r}")
        require(doc["assetFixedStart"] == start, f"{expected['name']}: start mismatch")
        require(doc["assetSerializedEnd"] == expected["rawEndOffset"], f"{expected['name']}: serialized end mismatch")
        require(doc["assetSerializedSha256"] == expected["serializedSha256"], f"{expected['name']}: serialized SHA mismatch")
        require(doc.get("allFlatPoolsExhausted") is True, f"{expected['name']}: flat pools did not exhaust")
        require(all(v.get("remaining") == 0 for v in doc["flatPoolExhaustion"].values()), f"{expected['name']}: nonzero flat pool remainder")
        require(doc.get("walkerBlockers") == [], f"{expected['name']}: walker blockers {doc.get('walkerBlockers')!r}")
        require(len(doc["boneTracks"]) == expected["bones"], f"{expected['name']}: bone-track count mismatch")
        require(target_notifies(doc) == expected["notifies"], f"{expected['name']}: notetrack reproduction mismatch")
        require(doc.get("delta") is None, f"{expected['name']}: unexpected deltaPart on retained deltaFlag=0 target")

        augment_normalized_xanim(doc)
        qhist: Counter[str] = Counter()
        thist: Counter[str] = Counter()
        qkeys = 0
        tkeys = 0
        long_here = 0
        for track in doc["boneTracks"]:
            q = track.get("quat") or {"type": "MISSING"}
            t = track.get("trans") or {"type": "MISSING"}
            qtype = q.get("type", "MISSING")
            ttype = t.get("type", "MISSING")
            qhist[qtype] += 1
            thist[ttype] += 1
            quat_types[qtype] += 1
            trans_types[ttype] += 1
            qk = frame_count(q)
            tk = frame_count(t)
            qkeys += qk
            tkeys += tk
            total_quat_keys += qk
            total_trans_keys += tk
            for component in (q, t):
                storage = component.get("indexStorage") if isinstance(component, dict) else None
                if storage and storage.get("sourcePool") == "indices":
                    long_here += 1
                    long_index_tracks += 1
        total_tracks += len(doc["boneTracks"])
        if doc.get("randomDataIntRaw"):
            random_data_int_records += 1

        target_rows.append({
            "name": doc["name"],
            "assetFixedStart": doc["assetFixedStart"],
            "assetSerializedEnd": doc["assetSerializedEnd"],
            "assetSerializedSha256": doc["assetSerializedSha256"],
            "frames": doc["header"]["numframes"],
            "framerate": doc["header"]["framerate"],
            "boneTrackCount": len(doc["boneTracks"]),
            "quatTypeCounts": dict(sorted(qhist.items())),
            "transTypeCounts": dict(sorted(thist.items())),
            "quatStoredKeyCount": qkeys,
            "transStoredKeyCount": tkeys,
            "longIndexTrackCount": long_here,
            "notifies": target_notifies(doc),
            "flatPoolExhaustion": doc["flatPoolExhaustion"],
            "normalizedAugmentedCanonicalSha256": canonical_sha256(doc),
        })

    require(len(target_rows) == 23, f"normalized target count {len(target_rows)} != 23")
    require(total_tracks == retained["summary"]["targetBoneReferenceCount"], "aggregate bone-track count disagrees with retained closure")

    return {
        "format": FORMAT,
        "source": {
            "expandedCommonMp": {"bytes": len(stream), "sha256": stream_sha},
            "retainedNotetrackClosure": str(retained_path),
            "halfQuaternionProof": str(half_proof_path),
        },
        "summary": {
            "targetCount": len(target_rows),
            "boneTrackCount": total_tracks,
            "quatTypeCounts": dict(sorted(quat_types.items())),
            "transTypeCounts": dict(sorted(trans_types.items())),
            "quatStoredKeyCount": total_quat_keys,
            "transStoredKeyCount": total_trans_keys,
            "longIndexTrackCount": long_index_tracks,
            "randomDataIntRecordCount": random_data_int_records,
            "allTargetsFlatPoolsExhausted": True,
            "allTargetsDeltaPartAbsent": True,
        },
        "targets": target_rows,
        "proofBoundary": (
            "For the 23 source-selected current-R2 MP7 XAnim records, ordinary bone-track pool assignment, "
            "packed index selection, translation quantization decode, raw quaternion payloads, ScriptString naming, "
            "and serialized notetracks are closed with exact per-record identity and zero unconsumed flat-pool data. "
            "The retained half-quaternion proof supplies raw[0]->z/raw[1]->w and 1/32767 scaling for standard quaternion expansion. "
            "These targets contain no deltaPart. XModel bind-pose composition, ordinary animated root-bone translation composition, "
            "and final weapon-viewmodel skeleton binding remain separate gates."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", type=Path, required=True)
    ap.add_argument("--retained", type=Path, required=True)
    ap.add_argument("--half-proof", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    doc = build(args.stream, args.retained, args.half_proof)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    for row in doc["targets"]:
        print(f"{row['name']} tracks={row['boneTrackCount']} qkeys={row['quatStoredKeyCount']} tkeys={row['transStoredKeyCount']} sha256={row['normalizedAugmentedCanonicalSha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
