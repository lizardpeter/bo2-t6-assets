#!/usr/bin/env python3
"""Build the T6 world-vertex registry from baseline and direct retail proofs.

V2 keeps the V1 policy boundary but additionally accepts the stronger
`t6-retail-world-formats-45-proof-v1` schema, where each format is bound from
GfxSurface -> MaterialMemory -> Material -> TechniqueSet and the raw vd1 stride
is independently derived from allocation spans.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SPECS = {
    0: ("TEX_1_NRM_1", 1, 1, 0, []),
    1: ("TEX_2_NRM_1", 2, 1, 4, ["uv1"]),
    2: ("TEX_2_NRM_2", 2, 2, 8, ["uv1", "normalTransform0"]),
    3: ("TEX_3_NRM_1", 3, 1, 8, ["uv1", "uv2"]),
    4: ("TEX_3_NRM_2", 3, 2, 12, ["uv1", "uv2", "normalTransform0"]),
    5: ("TEX_3_NRM_3", 3, 3, 16, ["uv1", "uv2", "normalTransform0", "normalTransform1"]),
    6: ("TEX_4_NRM_1", 4, 1, 12, ["uv1", "uv2", "uv3"]),
    7: ("TEX_4_NRM_2", 4, 2, 16, ["uv1", "uv2", "uv3", "normalTransform0"]),
    8: ("TEX_4_NRM_3", 4, 3, 20, ["uv1", "uv2", "uv3", "normalTransform0", "normalTransform1"]),
}
DIRECT_PROOF_FORMATS = {"t6-retail-world-formats-45-proof-v1"}


class RegistryError(RuntimeError):
    pass


def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RegistryError(f"{path}: top level must be an object")
    return obj


def validate_baseline(doc: dict) -> None:
    if doc.get("format") != "t6-world-vertex-format-census-v1":
        raise RegistryError(f"unsupported baseline {doc.get('format')!r}")
    rows = doc.get("formats")
    if not isinstance(rows, dict) or set(rows) != {str(i) for i in range(9)}:
        raise RegistryError("baseline formats must be exactly 0..8")
    for fmt, (name, uv, nrm, stride, fields) in SPECS.items():
        row = rows[str(fmt)]
        expected = {"name": name, "uvCount": uv, "normalCount": nrm, "vd1Stride": stride, "vd1Fields": fields}
        for key, value in expected.items():
            if row.get(key) != value:
                raise RegistryError(f"baseline format {fmt} {key}={row.get(key)!r} != {value!r}")


def validate_direct_proof(doc: dict, source: str) -> None:
    if doc.get("format") not in DIRECT_PROOF_FORMATS:
        raise RegistryError(f"{source}: unsupported direct proof {doc.get('format')!r}")
    if int(doc.get("summary", {}).get("contradictionCount", -1)) != 0:
        raise RegistryError(f"{source}: direct proof summary contains contradictions")
    maps = doc.get("maps")
    if not isinstance(maps, list) or not maps:
        raise RegistryError(f"{source}: direct proof has no maps")
    for m in maps:
        if not isinstance(m.get("map"), str) or not m["map"]:
            raise RegistryError(f"{source}: map without name")
        fmts = m.get("formats", {})
        for key, row in fmts.items():
            fmt = int(key)
            if fmt not in SPECS:
                raise RegistryError(f"{source}: invalid format {fmt}")
            expected_stride = SPECS[fmt][3]
            if int(row.get("contradictions", -1)) != 0:
                raise RegistryError(f"{source}: {m['map']} format {fmt} contradictions")
            if int(row.get("directAllocationCount", 0)) <= 0:
                raise RegistryError(f"{source}: {m['map']} format {fmt} has no direct allocations")
            if row.get("rawStrides") != [expected_stride]:
                raise RegistryError(
                    f"{source}: {m['map']} format {fmt} rawStrides={row.get('rawStrides')!r} "
                    f"!= [{expected_stride}]"
                )


def build_registry(baseline: dict, proofs: list[tuple[str, dict]]) -> dict:
    validate_baseline(baseline)
    for source, proof in proofs:
        validate_direct_proof(proof, source)

    rows = {}
    for fmt, (name, uv, nrm, stride, fields) in SPECS.items():
        base = baseline["formats"][str(fmt)]
        baseline_proven = bool(base.get("retailByteProven"))
        baseline_maps = sorted({str(x) for x in base.get("maps", []) if str(x)})
        evidence = []
        observed = set()
        contradictory = set()
        maps = set(baseline_maps)

        for source, proof in proofs:
            for m in proof["maps"]:
                row = m.get("formats", {}).get(str(fmt))
                if row is None:
                    continue
                raw = sorted({int(x) for x in row["rawStrides"]})
                contradictions = int(row.get("contradictions", 0))
                evidence.append({
                    "fixture": m["map"],
                    "source": source,
                    "proofFormat": proof["format"],
                    "directAllocationCount": int(row["directAllocationCount"]),
                    "observedRawStrides": raw,
                    "sharedNonseparableCount": int(row.get("sharedNonseparableCount", 0)),
                    "contradictionCount": contradictions,
                    "clean": contradictions == 0,
                })
                if contradictions == 0:
                    observed.update(raw)
                    if stride in raw:
                        maps.add(m["map"])
                contradictory.update(x for x in raw if x != stride)

        matching = stride in observed
        raw_proven = matching and not contradictory
        proven = (baseline_proven or raw_proven) and not contradictory
        proof_kinds = []
        if baseline_proven:
            proof_kinds.append("direct-retail-vertex-proof")
        if raw_proven:
            proof_kinds.append("material-bound-unambiguous-retail-vd1-allocation-stride")

        rows[str(fmt)] = {
            "format": fmt,
            "name": name,
            "sourceClosedFamily": {
                "uvCount": uv,
                "normalCount": nrm,
                "vd1Stride": stride,
                "vd1Fields": fields,
                "layoutRule": "vd0 owns uv0 + first normal/tangent basis; vd1 appends 4-byte half2 UV lanes then 4-byte packed normal-transform lanes",
            },
            "baselineDirectRetailProof": baseline_proven,
            "baselineMaps": baseline_maps,
            "rawAllocationEvidence": evidence,
            "cleanObservedRawStrides": sorted(observed),
            "matchingExpectedRawStrideObserved": matching,
            "rawStrideRetailProven": raw_proven,
            "contradictoryRawStrides": sorted(contradictory),
            "rawEvidenceWithBlockers": [],
            "retailByteProven": proven,
            "exportEnabled": proven,
            "proofKinds": proof_kinds,
            "retailProofMaps": sorted(maps),
            "status": "contradicted" if contradictory else "export-enabled" if proven else "pending-retail-byte-proof",
        }

    enabled = [i for i in range(9) if rows[str(i)]["exportEnabled"]]
    pending = [i for i in range(9) if not rows[str(i)]["exportEnabled"]]
    contradicted = [i for i in range(9) if rows[str(i)]["contradictoryRawStrides"]]
    return {
        "format": "t6-world-vertex-format-registry-v1",
        "sourceClosedFormatCount": 9,
        "formats": rows,
        "coverage": {
            "exportEnabledCount": len(enabled),
            "exportEnabledFormats": enabled,
            "pendingCount": len(pending),
            "pendingFormats": pending,
            "contradictedCount": len(contradicted),
            "contradictedFormats": contradicted,
            "allFormatsExportEnabled": len(enabled) == 9,
        },
        "inputs": {
            "baselineFormat": baseline.get("format"),
            "baselineMapCount": len(baseline.get("maps", [])),
            "directRetailProofCount": len(proofs),
            "directRetailProofSources": [source for source, _ in proofs],
            "acceptedDirectRetailProofFormats": sorted(DIRECT_PROOF_FORMATS),
        },
        "policy": {
            "formulaAloneCannotEnableExport": True,
            "ambiguousRawAllocationCannotPromote": True,
            "cleanContradictoryStrideDisablesFormat": True,
            "directExistingRetailProofRemainsValid": True,
            "pendingFormatPromotionRequiresExpectedUnambiguousRawStride": True,
            "materialBoundDirectProofAccepted": True,
        },
        "proofBoundary": "exportEnabled certifies the serialized world-vertex binary layout needed for normalized geometry export. Packed normalTransformN words remain raw unless/until their downstream shader-space meaning is independently closed; this registry does not invent that renderer semantic.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--retail-proof", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    baseline = load(args.baseline)
    proofs = [(str(p), load(p)) for p in args.retail_proof]
    registry = build_registry(baseline, proofs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(registry["coverage"], indent=2, sort_keys=True))
    if registry["coverage"]["contradictedCount"]:
        return 3
    return 0 if registry["coverage"]["allFormatsExportEnabled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
