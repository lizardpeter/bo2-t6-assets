#!/usr/bin/env python3
"""Close all 30 proven base-MP player bodies through the full XModel v2 walker.

Inputs are deliberately independent and already-retained:
- the direct-retail 30-body corpus (fixed offsets, fixed-record hashes, skeleton
  and fixed-surface totals, faction FastFile hashes),
- per-zone native XModel identity reports from the 215-zone census, and
- freshly expanded exact faction FastFiles.

A body closes only when all of those agree and the unchanged v2 walker reaches
the exact pinned-native source endpoint with zero blockers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from t6_xmodel_serialized_walker_v2 import XModelWalker

BODY_FORMAT = "t6-mp-player-body-faction-corpus-checkpoint-v1"
IDENTITY_FORMAT = "t6-native-xmodel-zone-identity-closure-v2"
FORMAT = "t6-mp-player-body-nested-closure-v1"
XMODEL_FIXED_BYTES = 248


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: expected JSON object")
    return obj


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_identity_reports(root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(root.rglob("*.xmodel-identity.json")):
        o = load(p)
        if o.get("format") != IDENTITY_FORMAT:
            raise ValueError(f"{p}: unexpected identity format {o.get('format')!r}")
        zone = o.get("zone")
        if not isinstance(zone, str) or not zone:
            raise ValueError(f"{p}: invalid zone")
        if zone in out:
            raise ValueError(f"duplicate native identity report for {zone}")
        out[zone] = o
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-corpus", type=Path, required=True)
    ap.add_argument("--identity-results-root", type=Path, required=True)
    ap.add_argument("--expanded-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--require-closed", action="store_true")
    a = ap.parse_args()

    corpus = load(a.body_corpus)
    if corpus.get("format") != BODY_FORMAT:
        raise ValueError(f"unexpected body corpus format {corpus.get('format')!r}")
    columns = corpus.get("columns")
    rows = corpus.get("rows")
    sources = corpus.get("sources")
    if not isinstance(columns, list) or not isinstance(rows, list) or not isinstance(sources, dict):
        raise ValueError("body corpus missing columns/rows/sources")
    col = {name: i for i, name in enumerate(columns)}
    required = ["name", "zone", "fixedStart", "fixedRecordSha256", "bones", "roots", "surfaces", "vertices", "triangles", "corpusSkeletonSha256"]
    missing = [x for x in required if x not in col]
    if missing:
        raise ValueError(f"body corpus missing columns {missing}")
    if len(rows) != 30:
        raise ValueError(f"expected 30 proven body rows, got {len(rows)}")

    reports = load_identity_reports(a.identity_results_root)
    bodies = []
    failures = []
    totals = {
        "bodies": 0,
        "nativeEndpointMatches": 0,
        "fixedRecordHashMatches": 0,
        "skeletonCountMatches": 0,
        "surfaceCountMatches": 0,
        "vertexTotalMatches": 0,
        "triangleTotalMatches": 0,
        "zeroBlockerWalks": 0,
        "inlineGfxImagesObserved": 0,
        "inlineNameBodies": 0,
        "packedNameBodies": 0,
    }

    for raw in rows:
        if not isinstance(raw, list) or len(raw) != len(columns):
            raise ValueError("invalid body row shape")
        name = str(raw[col["name"]])
        zone = str(raw[col["zone"]])
        fixed_start = int(raw[col["fixedStart"]])
        expected_fixed_sha = str(raw[col["fixedRecordSha256"]])
        expected_bones = int(raw[col["bones"]])
        expected_roots = int(raw[col["roots"]])
        expected_surfs = int(raw[col["surfaces"]])
        expected_verts = int(raw[col["vertices"]])
        expected_tris = int(raw[col["triangles"]])
        zone_path = f"zone/all/{zone}.ff"
        expanded_path = a.expanded_root / f"{zone}.expanded"
        totals["bodies"] += 1

        rec: dict[str, Any] = {
            "name": name,
            "zone": zone,
            "zonePath": zone_path,
            "fixedStart": fixed_start,
            "expectedFixedRecordSha256": expected_fixed_sha,
            "expectedBones": expected_bones,
            "expectedRoots": expected_roots,
            "expectedSurfaces": expected_surfs,
            "expectedVertices": expected_verts,
            "expectedTriangles": expected_tris,
            "corpusSkeletonSha256": raw[col["corpusSkeletonSha256"]],
        }
        body_failures: list[str] = []
        try:
            if not expanded_path.is_file():
                raise ValueError(f"missing expanded faction FastFile {expanded_path}")
            data = expanded_path.read_bytes()
            source_hashes = sources.get(zone)
            if not isinstance(source_hashes, list) or len(source_hashes) != 2:
                raise ValueError(f"{zone}: invalid retained compressed/expanded hash pair")
            expected_expanded_sha = str(source_hashes[1])
            observed_expanded_sha = sha256(data)
            rec["expandedBytes"] = len(data)
            rec["expectedExpandedSha256"] = expected_expanded_sha
            rec["observedExpandedSha256"] = observed_expanded_sha
            rec["expandedSha256Matches"] = observed_expanded_sha == expected_expanded_sha
            if not rec["expandedSha256Matches"]:
                body_failures.append("expanded FastFile SHA-256 mismatch")

            if fixed_start < 0 or fixed_start + XMODEL_FIXED_BYTES > len(data):
                body_failures.append("fixed record lies outside expanded FastFile")
                raise ValueError(body_failures[-1])
            observed_fixed_sha = sha256(data[fixed_start:fixed_start + XMODEL_FIXED_BYTES])
            rec["observedFixedRecordSha256"] = observed_fixed_sha
            rec["fixedRecordSha256Matches"] = observed_fixed_sha == expected_fixed_sha
            if rec["fixedRecordSha256Matches"]:
                totals["fixedRecordHashMatches"] += 1
            else:
                body_failures.append("fixed XModel record SHA-256 mismatch")

            report = reports.get(zone_path)
            if report is None:
                body_failures.append("missing native identity report for faction FastFile")
                raise ValueError(body_failures[-1])
            candidates = [x for x in report.get("xmodels", []) if isinstance(x, dict) and x.get("nativeResolvedName") == name]
            if len(candidates) != 1:
                body_failures.append(f"expected exactly one native identity row in faction FastFile, got {len(candidates)}")
                raise ValueError(body_failures[-1])
            ident = candidates[0]
            rec["nativeIdentity"] = {
                "xassetIndex": ident.get("xassetIndex"),
                "sourceStart": ident.get("sourceStart"),
                "sourceEnd": ident.get("sourceEnd"),
                "sourceKind": ident.get("sourceKind"),
                "identityClosed": ident.get("identityClosed"),
                "nameIdentityMethod": ident.get("nameIdentityMethod") or ident.get("identityMethod"),
            }
            native_start = int(ident.get("sourceStart", -1))
            native_end = int(ident.get("sourceEnd", -1))
            rec["nativeSourceStartMatchesCorpusFixedStart"] = native_start == fixed_start
            if not rec["nativeSourceStartMatchesCorpusFixedStart"]:
                body_failures.append("native sourceStart != retained direct-body fixedStart")
            if ident.get("sourceKind") != "native-source-consuming" or ident.get("identityClosed") is not True or native_end <= native_start:
                body_failures.append("native identity row is not a closed source-consuming XModel")

            walk = XModelWalker(data, fixed_start).walk_xmodel()
            xm = walk["xmodel"]
            rec["walker"] = {
                "assetSerializedEnd": walk["assetSerializedEnd"],
                "assetSerializedBytes": walk["assetSerializedBytes"],
                "assetSerializedSha256": walk["assetSerializedSha256"],
                "name": xm.get("name"),
                "namePointer": xm.get("namePointer"),
                "numBones": xm.get("numBones"),
                "numRootBones": xm.get("numRootBones"),
                "numSurfs": xm.get("numSurfs"),
                "numLods": xm.get("numLods"),
                "numCollSurfs": xm.get("numCollSurfs"),
                "numCollmaps": xm.get("numCollmaps"),
                "blockers": walk.get("blockers"),
                "inlineGfxImages": walk.get("details", {}).get("inlineGfxImages", []),
            }
            rec["walkerEndpointMatchesNative"] = int(walk["assetSerializedEnd"]) == native_end
            if rec["walkerEndpointMatchesNative"]:
                totals["nativeEndpointMatches"] += 1
            else:
                body_failures.append("walker endpoint != pinned native endpoint")

            blockers = walk.get("blockers") or []
            rec["zeroWalkerBlockers"] = not blockers
            if rec["zeroWalkerBlockers"]:
                totals["zeroBlockerWalks"] += 1
            else:
                body_failures.append("walker reported nested serializer blockers")

            name_ptr_kind = (xm.get("namePointer") or {}).get("kind")
            if name_ptr_kind in ("following", "insert"):
                totals["inlineNameBodies"] += 1
                rec["nameClosed"] = xm.get("name") == name
                if not rec["nameClosed"]:
                    body_failures.append("inline walker name != proven native body name")
            elif name_ptr_kind == "packed":
                totals["packedNameBodies"] += 1
                rec["nameClosed"] = ident.get("nativeResolvedName") == name
                if not rec["nameClosed"]:
                    body_failures.append("packed-name native identity mismatch")
            else:
                rec["nameClosed"] = False
                body_failures.append(f"unsupported/null body name pointer kind {name_ptr_kind!r}")

            rec["skeletonCountMatches"] = xm.get("numBones") == expected_bones and xm.get("numRootBones") == expected_roots
            if rec["skeletonCountMatches"]:
                totals["skeletonCountMatches"] += 1
            else:
                body_failures.append("walker skeleton counts != retained body corpus")
            rec["surfaceCountMatches"] = xm.get("numSurfs") == expected_surfs and len(xm.get("surfaces") or []) == expected_surfs
            if rec["surfaceCountMatches"]:
                totals["surfaceCountMatches"] += 1
            else:
                body_failures.append("walker surface count != retained body corpus")
            observed_verts = sum(int(s.get("vertCount", 0)) for s in (xm.get("surfaces") or []))
            observed_tris = sum(int(s.get("triCount", 0)) for s in (xm.get("surfaces") or []))
            rec["observedVertices"] = observed_verts
            rec["observedTriangles"] = observed_tris
            rec["vertexTotalMatches"] = observed_verts == expected_verts
            rec["triangleTotalMatches"] = observed_tris == expected_tris
            if rec["vertexTotalMatches"]:
                totals["vertexTotalMatches"] += 1
            else:
                body_failures.append("walker vertex total != retained body corpus")
            if rec["triangleTotalMatches"]:
                totals["triangleTotalMatches"] += 1
            else:
                body_failures.append("walker triangle total != retained body corpus")
            gfx = walk.get("details", {}).get("inlineGfxImages", [])
            totals["inlineGfxImagesObserved"] += len(gfx)
            rec["inlineGfxImageCount"] = len(gfx)
        except Exception as exc:
            rec["exception"] = repr(exc)
            if not body_failures:
                body_failures.append(f"exception: {exc!r}")

        rec["failures"] = body_failures
        rec["closed"] = not body_failures
        if body_failures:
            failures.append({"name": name, "zone": zone, "failures": body_failures})
        bodies.append(rec)

    gates = {
        "all30BodiesAccounted": totals["bodies"] == 30,
        "allExpandedFactionFastFilesExact": all(b.get("expandedSha256Matches") is True for b in bodies),
        "allFixedRecordsExact": totals["fixedRecordHashMatches"] == 30,
        "allNativeStartsMatchDirectCorpus": all(b.get("nativeSourceStartMatchesCorpusFixedStart") is True for b in bodies),
        "allNativeEndpointsMatched": totals["nativeEndpointMatches"] == 30,
        "allNestedWalksZeroBlocker": totals["zeroBlockerWalks"] == 30,
        "allNamesClosed": all(b.get("nameClosed") is True for b in bodies),
        "allSkeletonCountsMatch": totals["skeletonCountMatches"] == 30,
        "allSurfaceCountsMatch": totals["surfaceCountMatches"] == 30,
        "allVertexTotalsMatch": totals["vertexTotalMatches"] == 30,
        "allTriangleTotalsMatch": totals["triangleTotalMatches"] == 30,
        "zeroFailures": not failures,
    }
    out = {
        "format": FORMAT,
        "scope": "All 30 independently proven base-MP player bodies, full nested serialized XModel v2 structural closure",
        "walker": "t6-xmodel-serialized-walk-v2",
        "totals": totals,
        "gates": gates,
        "failures": failures,
        "bodies": bodies,
        "proofBoundary": [
            "Body membership, fixed source starts, fixed-record hashes, skeleton counts, and fixed-surface totals come only from the retained direct-retail 30-body corpus.",
            "Native source endpoints and native identities come only from the already-green 215-zone native XModel identity census; this tool does not derive or fit endpoints.",
            "Each of the six faction FastFiles must independently reproduce its retained expanded SHA-256 before any body is evaluated.",
            "The unchanged t6_xmodel_serialized_walker_v2 must reach the exact native source endpoint with zero blockers for every body.",
            "Material/GfxImage objects consumed inline by the structural walker are counted as nested serializer coverage only; this proof does not claim exact portable Material/TechniqueSet/shader visual fidelity.",
            "No name-pattern discovery, adjacency inference, visual matching, or cross-zone same-name byte-identity assumption participates in closure."
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"totals": totals, "gates": gates, "failureCount": len(failures)}, indent=2, sort_keys=True))
    if a.require_closed and not all(gates.values()):
        raise SystemExit("30-body nested XModel closure did not fully close")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
