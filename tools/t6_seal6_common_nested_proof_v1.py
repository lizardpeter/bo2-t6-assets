#!/usr/bin/env python3
"""Retain q10/q17 common_mp nested payload only after native ownership closes.

The common_mp exact-name diagnostic deliberately does not establish top-level
XAsset ownership.  This adapter preserves that boundary: it accepts the decoded
nested candidate only if an independent pinned-native-OAT dependency proof has
already established the same canonical TechniqueSet as a resolved common_mp
definition for q10/q17.

Thus a name occurrence is never promoted into an owner.  After ownership is
independently proven, the unique matching decoded common_mp record is retained
as payload evidence (techniques, passes, exact serialized shader arguments and
direct DXBC hashes).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-common-nested-proof-v1"
EXPECTED_SOURCE_SHA256 = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
EXPECTED = {
    10: {
        "name": "mc_sw4_3d_char_cloth_4z8fq5wu",
        "start": 80581190,
        "end": 80884450,
        "inlineTechniques": 21,
        "arguments": 432,
        "argumentTypes": {"2": 60, "3": 132, "4": 54, "5": 186},
        "directShaders": 20,
    },
    17: {
        "name": "mc_sw4_3d_char_skin_j92387z3",
        "start": 80261429,
        "end": 80578311,
        "inlineTechniques": 22,
        "arguments": 496,
        "argumentTypes": {"2": 61, "3": 134, "4": 54, "5": 187, "6": 60},
        "directShaders": 20,
    },
}


def node_name(node: dict[str, Any]) -> str | None:
    x = node.get("name")
    return x.get("value") if isinstance(x, dict) else x


def values_hash(values: list[dict[str, Any]]) -> str:
    raw = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def build(diag: dict[str, Any], native: dict[str, Any]) -> dict[str, Any]:
    if diag.get("format") != "t6-techset-exact-name-diagnostic-v1":
        raise ValueError("unexpected common diagnostic format")
    if str((diag.get("source") or {}).get("expandedSha256", "")).lower() != EXPECTED_SOURCE_SHA256:
        raise ValueError("common_mp expanded SHA-256 drift")
    if native.get("format") != "t6-seal6-native-oat-techset-dependency-proof-v1" or native.get("errors"):
        raise ValueError("native dependency proof is absent or not closed")

    native_defs = {int(x["q"]): x for x in native.get("techniqueSetDefinitions") or []}
    targets = {x.get("canonicalName"): x for x in diag.get("targets") or []}
    out_targets = []

    for q in (10, 17):
        spec = EXPECTED[q]
        nd = native_defs.get(q)
        if not nd or not nd.get("resolved"):
            raise ValueError(f"q{q} native ownership unresolved")
        if nd.get("name") != spec["name"] or nd.get("definitionZone") != "common_mp":
            raise ValueError(f"q{q} native owner/name drift")

        td = targets.get(spec["name"])
        if not td or int(td.get("occurrenceCount", 0)) != 1:
            raise ValueError(f"q{q} common diagnostic does not have exactly one matching decoded record")
        occ = td["occurrences"][0]
        node = occ.get("node") or {}
        if int(occ.get("candidateFixedStart", -1)) != spec["start"] or int(node.get("end", -1)) != spec["end"]:
            raise ValueError(f"q{q} decoded common extent drift")
        if node_name(node) != spec["name"]:
            raise ValueError(f"q{q} decoded common name drift")

        techniques = []
        argument_count = 0
        type_counts: dict[str, int] = {}
        direct_count = 0
        for tref in node.get("techniqueRefs") or []:
            tech = tref.get("inlineTechnique")
            if not tech:
                continue
            tr = {
                "slot": int(tref["slot"]),
                "name": node_name(tech),
                "start": int(tech["fixedStart"]),
                "end": int(tech["end"]),
                "flags": int(tech["flags"]),
                "passCount": int(tech["passCount"]),
                "passes": [],
            }
            for p in tech.get("passes") or []:
                pr: dict[str, Any] = {
                    "index": int(p["passIndex"]),
                    "argCount": int(p["argCount"]),
                    "counts": p["counts"],
                }
                for kind in ("vs", "ps"):
                    ch = p["children"][kind]
                    sr: dict[str, Any] = {"pointer": ch["pointer"]}
                    ii = ch.get("inline")
                    if ii:
                        ir: dict[str, Any] = {
                            "name": node_name(ii),
                            "fixedStart": int(ii["fixedStart"]),
                            "end": int(ii["end"]),
                        }
                        if ii.get("program") is not None:
                            ir["program"] = ii["program"]
                            if ii["program"].get("direct"):
                                direct_count += 1
                        sr["inline"] = ir
                    pr[kind] = sr
                ach = p["children"]["args"]
                ar: dict[str, Any] = {"pointer": ach["pointer"]}
                ai = ach.get("inline")
                if ai is not None:
                    vals = ai.get("values")
                    if not isinstance(vals, list) or len(vals) != int(ai["count"]) or len(vals) != int(p["argCount"]):
                        raise ValueError(f"q{q} slot {tr['slot']} argument retention mismatch")
                    for value in vals:
                        if set(value) != {"type", "location", "size", "buffer", "u"}:
                            raise ValueError(f"q{q} malformed retained argument")
                        typ = str(int(value["type"]))
                        type_counts[typ] = type_counts.get(typ, 0) + 1
                    argument_count += len(vals)
                    ar["inline"] = {
                        "fixedStart": int(ai["fixedStart"]),
                        "end": int(ai["end"]),
                        "values": vals,
                        "valuesSha256": values_hash(vals),
                        "literals": ai.get("literals") or [],
                    }
                pr["args"] = ar
                pr["vd"] = p["children"]["vd"]
                tr["passes"].append(pr)
            techniques.append(tr)

        if len(techniques) != spec["inlineTechniques"]:
            raise ValueError(f"q{q} inline technique count drift")
        if argument_count != spec["arguments"] or type_counts != spec["argumentTypes"]:
            raise ValueError(f"q{q} shader argument census drift: {argument_count} {type_counts}")
        if direct_count != spec["directShaders"]:
            raise ValueError(f"q{q} direct shader count drift")

        out_targets.append({
            "xassetIndex": q,
            "canonicalName": spec["name"],
            "ownershipGate": {
                "method": "pinned native OAT dependency resolution",
                "definitionZone": nd["definitionZone"],
                "nativeTechniqueSetSha256": nd["sha256"],
            },
            "decodedCommonPayload": {
                "candidateFixedStart": spec["start"],
                "decodedEnd": spec["end"],
                "inlineTechniqueCount": len(techniques),
                "shaderArgumentCount": argument_count,
                "argumentTypeCounts": type_counts,
                "directInlineShaderPayloadCount": direct_count,
            },
            "techniques": techniques,
        })

    return {
        "format": FORMAT,
        "zone": "common_mp",
        "source": diag["source"],
        "targets": out_targets,
        "summary": {
            "targets": 2,
            "inlineTechniques": sum(x["decodedCommonPayload"]["inlineTechniqueCount"] for x in out_targets),
            "shaderArguments": sum(x["decodedCommonPayload"]["shaderArgumentCount"] for x in out_targets),
            "directInlineShaderPayloads": sum(x["decodedCommonPayload"]["directInlineShaderPayloadCount"] for x in out_targets),
            "ownershipEstablishedByNameScan": False,
            "nativeOwnershipGatePassed": True,
        },
        "proofBoundary": [
            "The exact-name diagnostic alone remains non-promoting and does not establish top-level common_mp XAsset ownership.",
            "Decoded q10/q17 common payload is retained only after the independent pinned-native-OAT proof resolves the faction Materials to these canonical common_mp TechniqueSets.",
            "The unique matching decoded records are then used as payload evidence only, preserving exact nested Technique/pass/shader/argument records and direct DXBC hashes.",
            "No scan rank, adjacency, mesh similarity, visual matching or PBR interpretation establishes ownership here.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("common_diagnostic", type=Path)
    ap.add_argument("native_dependency_proof", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    diag = json.loads(a.common_diagnostic.read_text(encoding="utf-8"))
    native = json.loads(a.native_dependency_proof.read_text(encoding="utf-8"))
    out = build(diag, native)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
