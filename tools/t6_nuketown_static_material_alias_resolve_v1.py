#!/usr/bin/env python3
"""Fail-closed exact material-alias resolver for Nuketown static XModels.

This tool combines two independent retained retail proofs:
1. The playable-static LOD0 material proof, which gives exact material identity
   for every LOD0 surface of 297 static XModels.
2. T6's 4-byte contiguous XModel material-handle array contract.  A packed
   reusable material pointer may target a previously established handle slot.

A packed target is promoted directly when a proof-covered source slot names it.
Additional same-XModel handle slots are promoted only when at least two DISTINCT
already-resolved packed target offsets independently imply the SAME contiguous
handle-array base and each target material is also present as an inline material
slot in that XModel.  One-anchor inferences are intentionally rejected.

No filename similarity, material-name similarity, render appearance, GLB state,
or old scene assignment is used to resolve an alias.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

PTR_BYTES = 4
VIRTUAL_BLOCK = 5
EXPECTED_PROOF_FORMAT = "bo2-t6-xmodel-material-proof-v1"
EXPECTED_SOURCE_FORMAT = "bo2-t6-nuketown-all-static-xmodel-extraction-manifest-v3"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def packed_key(handle: dict) -> tuple[int, int] | None:
    p = handle.get("pointer") or {}
    if p.get("kind") != "offset":
        return None
    block = p.get("block")
    off = p.get("offset")
    if not isinstance(block, int) or not isinstance(off, int):
        return None
    return block, off


def build(source: dict, proof: dict) -> dict:
    if proof.get("format") != EXPECTED_PROOF_FORMAT:
        raise ValueError(f"unexpected proof format: {proof.get('format')!r}")
    if source.get("format") != EXPECTED_SOURCE_FORMAT:
        raise ValueError(f"unexpected source format: {source.get('format')!r}")
    source_sha = ((source.get("source") or {}).get("expandedSha256"))
    proof_sha = proof.get("sourceFastFileSha256")
    if source_sha != proof_sha:
        raise ValueError(f"source/proof expanded SHA mismatch: {source_sha!r} vs {proof_sha!r}")
    if source.get("map") != proof.get("map"):
        raise ValueError(f"map mismatch: source={source.get('map')} proof={proof.get('map')}")
    if proof.get("unresolvedMaterialSlots") != 0 or proof.get("genericPlaceholderSlots") != 0:
        raise ValueError("retained playable-static proof is not fully resolved")

    source_models = source.get("models") or []
    by_xasset = {int(m["xassetIndex"]): m for m in source_models}
    if len(by_xasset) != len(source_models):
        raise ValueError("duplicate source XAsset indices")

    # Enumerate every packed static material reference once, preserving occurrence evidence.
    packed_occurrences: list[dict] = []
    referenced_keys: set[tuple[int, int]] = set()
    for model in source_models:
        for h in model.get("materials") or []:
            key = packed_key(h)
            if key is None:
                continue
            if key[0] != VIRTUAL_BLOCK:
                raise ValueError(
                    f"unexpected static material packed block {key[0]} "
                    f"for XAsset {model['xassetIndex']} surface {h.get('surfaceIndex')}"
                )
            referenced_keys.add(key)
            packed_occurrences.append({
                "xassetIndex": int(model["xassetIndex"]),
                "modelName": model.get("modelName"),
                "surfaceIndex": int(h["surfaceIndex"]),
                "block": key[0],
                "offset": key[1],
            })

    aliases: dict[tuple[int, int], str] = {}
    evidence: dict[tuple[int, int], list[dict]] = collections.defaultdict(list)
    direct_slots = 0

    def admit(key: tuple[int, int], material: str, ev: dict) -> None:
        old = aliases.get(key)
        if old is not None and old != material:
            raise ValueError(
                f"material alias conflict at block {key[0]} offset {key[1]}: "
                f"{old!r} vs {material!r}"
            )
        aliases[key] = material
        if ev not in evidence[key]:
            evidence[key].append(ev)

    # Stage A: exact proof-covered source slots.
    seen_proof_xassets: set[int] = set()
    for row in proof.get("models") or []:
        xi = int(row["xassetIndex"])
        if xi in seen_proof_xassets:
            raise ValueError(f"duplicate proof XAsset {xi}")
        seen_proof_xassets.add(xi)
        src = by_xasset.get(xi)
        if src is None:
            raise ValueError(f"proof XAsset {xi} absent from source manifest")
        if src.get("modelName") != row.get("xmodelName"):
            raise ValueError(
                f"proof/source model-name mismatch for XAsset {xi}: "
                f"{row.get('xmodelName')!r} vs {src.get('modelName')!r}"
            )
        first = int(row.get("surfaceIndex", 0))
        count = int(row.get("surfaceCount", 0))
        mats = list(row.get("materials") or [])
        if count != len(mats):
            raise ValueError(f"proof surface/material count mismatch for XAsset {xi}")
        src_handles = src.get("materials") or []
        if first < 0 or first + count > len(src_handles):
            raise ValueError(f"proof surface range outside source model XAsset {xi}")
        for local, material in enumerate(mats):
            si = first + local
            h = src_handles[si]
            if int(h.get("surfaceIndex", -1)) != si:
                raise ValueError(f"source material ordering drift XAsset {xi} surface {si}")
            # Inline names are an independent consistency check; packed handles get alias evidence.
            if h.get("inline"):
                if h.get("name") != material:
                    raise ValueError(
                        f"proof/source inline material mismatch XAsset {xi} surface {si}: "
                        f"{material!r} vs {h.get('name')!r}"
                    )
                continue
            key = packed_key(h)
            if key is None:
                raise ValueError(
                    f"proof-covered non-inline material is not a packed pointer: XAsset {xi} surface {si}"
                )
            direct_slots += 1
            admit(key, material, {
                "kind": "retained-lod0-proof",
                "xassetIndex": xi,
                "modelName": src.get("modelName"),
                "surfaceIndex": si,
                "proofMaterial": material,
            })

    direct_alias_keys = set(aliases)
    direct_global_refs = sum((o["block"], o["offset"]) in direct_alias_keys for o in packed_occurrences)

    # Stage B: strict multi-anchor solve of a same-XModel contiguous material-handle array.
    # Iterate because newly proven neighbor slots can provide anchors in another model.
    anchored_models: dict[int, dict] = {}
    iteration = 0
    while True:
        iteration += 1
        additions_before = len(aliases)
        for model in source_models:
            xi = int(model["xassetIndex"])
            handles = model.get("materials") or []
            inline_by_name: dict[str, list[int]] = collections.defaultdict(list)
            for h in handles:
                if h.get("inline") and isinstance(h.get("name"), str):
                    inline_by_name[h["name"]].append(int(h["surfaceIndex"]))

            anchor_rows: list[dict] = []
            for h in handles:
                key = packed_key(h)
                if key is None or key not in aliases:
                    continue
                material = aliases[key]
                # Ambiguous duplicate inline names do not establish which slot was targeted.
                slots = inline_by_name.get(material, [])
                if len(slots) != 1:
                    continue
                target_surface = slots[0]
                base = key[1] - PTR_BYTES * target_surface
                anchor_rows.append({
                    "packedSurfaceIndex": int(h["surfaceIndex"]),
                    "targetOffset": key[1],
                    "material": material,
                    "inlineTargetSurfaceIndex": target_surface,
                    "impliedArrayBase": base,
                })

            # Strictly require >=2 DISTINCT target offsets and one unanimous base.
            distinct_targets = {r["targetOffset"] for r in anchor_rows}
            bases = {r["impliedArrayBase"] for r in anchor_rows}
            if len(distinct_targets) < 2 or len(bases) != 1:
                continue
            base = next(iter(bases))
            if base < 0 or base % PTR_BYTES:
                raise ValueError(f"invalid inferred handle-array base {base} for XAsset {xi}")

            # Every anchor must land exactly on its inline slot at 4-byte spacing.
            for r in anchor_rows:
                expected = base + PTR_BYTES * r["inlineTargetSurfaceIndex"]
                if expected != r["targetOffset"]:
                    raise AssertionError((xi, r, expected))

            added_here = []
            for h in handles:
                if not (h.get("inline") and isinstance(h.get("name"), str)):
                    continue
                si = int(h["surfaceIndex"])
                key = (VIRTUAL_BLOCK, base + PTR_BYTES * si)
                if key not in referenced_keys:
                    continue
                was_new = key not in aliases
                admit(key, h["name"], {
                    "kind": "multi-anchor-contiguous-handle-array",
                    "xassetIndex": xi,
                    "modelName": model.get("modelName"),
                    "inlineSurfaceIndex": si,
                    "arrayBase": base,
                    "pointerWidthBytes": PTR_BYTES,
                    "anchorTargetOffsets": sorted(distinct_targets),
                    "anchorCount": len(distinct_targets),
                })
                if was_new:
                    added_here.append({"block": key[0], "offset": key[1], "material": h["name"]})

            prior = anchored_models.get(xi)
            if prior is None:
                anchored_models[xi] = {
                    "xassetIndex": xi,
                    "modelName": model.get("modelName"),
                    "arrayBase": base,
                    "initialDistinctAnchorCount": len(distinct_targets),
                    "initialDistinctAnchorOffsets": sorted(distinct_targets),
                    "initialAnchors": anchor_rows,
                    "newReferencedAliases": list(added_here),
                }
            else:
                if prior["arrayBase"] != base:
                    raise ValueError(f"anchored array base drift for XAsset {xi}: {prior['arrayBase']} vs {base}")
                known = {(x["block"], x["offset"], x["material"]) for x in prior["newReferencedAliases"]}
                for x in added_here:
                    sig = (x["block"], x["offset"], x["material"] )
                    if sig not in known:
                        prior["newReferencedAliases"].append(x)
                        known.add(sig)
                prior["finalDistinctAnchorCount"] = len(distinct_targets)
                prior["finalDistinctAnchorOffsets"] = sorted(distinct_targets)

        if len(aliases) == additions_before:
            break
        if iteration > len(source_models) + 1:
            raise RuntimeError("alias propagation did not converge")

    exact_keys = set(aliases) & referenced_keys
    exact_refs = sum((o["block"], o["offset"]) in exact_keys for o in packed_occurrences)
    unresolved_keys = sorted(referenced_keys - exact_keys)
    unresolved_refs = [o for o in packed_occurrences if (o["block"], o["offset"]) not in exact_keys]
    strict_added = exact_keys - direct_alias_keys

    records = []
    for key in sorted(exact_keys):
        records.append({
            "block": key[0],
            "offset": key[1],
            "offsetHex": f"0x{key[1]:08x}",
            "material": aliases[key],
            "evidence": evidence[key],
            "globalReferenceCount": sum((o["block"], o["offset"]) == key for o in packed_occurrences),
        })

    result = {
        "format": "t6-nuketown-static-material-alias-closure-v1",
        "map": source.get("map"),
        "source": {
            "staticManifestFormat": source.get("format"),
            "retainedProofFormat": proof.get("format"),
            "retainedProofSourceFastFileSha256": proof.get("sourceFastFileSha256"),
            "retainedProofVirtualBlockBase": proof.get("virtualBlockBase"),
            "retainedProofInsertAliasSlots": proof.get("insertAliasSlots"),
        },
        "contract": {
            "materialHandlePointerWidthBytes": PTR_BYTES,
            "materialHandleBlock": VIRTUAL_BLOCK,
            "strictNeighborPromotion": (
                "requires at least two distinct already-resolved packed target offsets in one XModel; "
                "both/all must map to unique inline material slots and imply one identical 4-byte-array base"
            ),
            "oneAnchorPromotionAllowed": False,
        },
        "summary": {
            "staticModelCount": len(source_models),
            "packedMaterialReferenceCount": len(packed_occurrences),
            "uniquePackedTargetCount": len(referenced_keys),
            "directProofPackedSlotCount": direct_slots,
            "directProofUniquePackedTargetCount": len(direct_alias_keys & referenced_keys),
            "directProofResolvedGlobalReferenceCount": direct_global_refs,
            "strictArrayAnchoredModelCount": len(anchored_models),
            "strictNeighborUniquePackedTargetsAdded": len(strict_added),
            "exactResolvedUniquePackedTargetCount": len(exact_keys),
            "exactResolvedPackedReferenceCount": exact_refs,
            "unresolvedUniquePackedTargetCount": len(unresolved_keys),
            "unresolvedPackedReferenceCount": len(unresolved_refs),
            "aliasConflictCount": 0,
            "propagationIterations": iteration,
        },
        "strictArrayAnchoredModels": [anchored_models[k] for k in sorted(anchored_models)],
        "resolvedAliases": records,
        "unresolvedPackedTargets": [
            {
                "block": b,
                "offset": off,
                "offsetHex": f"0x{off:08x}",
                "globalReferenceCount": sum((o["block"], o["offset"]) == (b, off) for o in packed_occurrences),
            }
            for b, off in unresolved_keys
        ],
        "proofBoundary": (
            "Exact closure only. Direct aliases come from retained retail LOD0 material proof applied to the matching "
            "source XModel surface. Neighbor aliases require >=2 independent packed anchors proving a single contiguous "
            "4-byte material-handle-array base. Single-anchor, name-similarity, geometry-similarity, GLB assignment, "
            "render appearance, and ordering-only guesses are not promoted."
        ),
    }
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-static-manifest", type=Path, required=True)
    ap.add_argument("--retained-proof", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    source = json.loads(args.source_static_manifest.read_text(encoding="utf-8"))
    proof = json.loads(args.retained_proof.read_text(encoding="utf-8"))
    out = build(source, proof)
    out["inputFiles"] = {
        "sourceStaticManifest": {
            "file": args.source_static_manifest.name,
            "bytes": args.source_static_manifest.stat().st_size,
            "sha256": sha256_file(args.source_static_manifest),
        },
        "retainedProof": {
            "file": args.retained_proof.name,
            "bytes": args.retained_proof.stat().st_size,
            "sha256": sha256_file(args.retained_proof),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    print(f"out={args.out} bytes={args.out.stat().st_size} sha256={sha256_file(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
