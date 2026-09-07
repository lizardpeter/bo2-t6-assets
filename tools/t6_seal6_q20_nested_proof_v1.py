#!/usr/bin/env python3
"""Persist the exact faction_seals_mp SEAL6 q20 TechniqueSet nested proof.

Input is the exact continuous q0..q20 source-order replay JSON produced by
`t6_early_techset_source_order_walk_v2.py`.  This adapter does not rediscover
any source offset.  It fail-closes on the already pinned q20 extent/hash and
then retains the exact nested Technique/pass/shader/vdecl/argument records in a
compact durable manifest.

In particular, every inline MaterialShaderArgument is retained as its five
serialized fields: type, location, size, buffer and raw union value `u`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-seal6-q20-techset-nested-proof-v1"
EXPECTED_SOURCE_SHA256 = "21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30"
EXPECTED_Q20 = {
    "start": 1974315,
    "end": 2316141,
    "bytes": 341826,
    "sha256": "82cf1c6f46d5a8e6bc04d7bd3b22d9eb08a0e498d7a79201b81362225de097fb",
    "name": "mc_sw4_3d_char_skin_hero_9949fq1j",
}
EXPECTED_ACTIVE_SLOTS = [0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 32, 35]
EXPECTED_INLINE_TECHNIQUES = 23
EXPECTED_DIRECT_INLINE_SHADERS = 22
EXPECTED_ARGUMENTS = 538
EXPECTED_ARGUMENT_TYPE_COUNTS = {"2": 81, "3": 136, "4": 54, "5": 187, "6": 80}


def canonical_values_hash(values: list[dict[str, Any]]) -> str:
    raw = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def node_name(node: dict[str, Any]) -> str | None:
    name = node.get("name")
    return name.get("value") if isinstance(name, dict) else name


def build(doc: dict[str, Any]) -> dict[str, Any]:
    source = doc.get("source") or {}
    if str(source.get("expandedSha256", "")).lower() != EXPECTED_SOURCE_SHA256:
        raise ValueError("faction source SHA-256 drift")

    targets = {int(x["xassetIndex"]): x for x in doc.get("targetTechniqueSets") or []}
    if 20 not in targets:
        raise ValueError("q20 target missing")
    q20 = targets[20]
    if int(q20["sourceStart"]) != EXPECTED_Q20["start"]:
        raise ValueError("q20 sourceStart drift")
    if int(q20["sourceEnd"]) != EXPECTED_Q20["end"]:
        raise ValueError("q20 sourceEnd drift")
    if int(q20["serializedBytes"]) != EXPECTED_Q20["bytes"]:
        raise ValueError("q20 serialized byte count drift")
    if str(q20["serializedSha256"]).lower() != EXPECTED_Q20["sha256"]:
        raise ValueError("q20 serialized SHA-256 drift")

    node = q20.get("node") or {}
    if node_name(node) != EXPECTED_Q20["name"]:
        raise ValueError("q20 TechniqueSet name drift")
    if int(node.get("worldVertFormat", -1)) != 0:
        raise ValueError("q20 worldVertFormat drift")

    active_slots = [int(x["slot"]) for x in node.get("techniqueRefs") or [] if (x.get("pointer") or {}).get("kind") != "null"]
    if active_slots != EXPECTED_ACTIVE_SLOTS:
        raise ValueError(f"q20 active slots drift: {active_slots}")

    techniques = []
    direct_inline_shaders = 0
    argument_count = 0
    argument_type_counts: dict[str, int] = {}

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
        if tr["passCount"] != len(tech.get("passes") or []):
            raise ValueError(f"slot {tr['slot']} pass count mismatch")

        for p in tech.get("passes") or []:
            pr: dict[str, Any] = {
                "index": int(p["passIndex"]),
                "argCount": int(p["argCount"]),
                "counts": p["counts"],
            }
            for kind in ("vs", "ps"):
                ch = p["children"][kind]
                out: dict[str, Any] = {"pointer": ch["pointer"]}
                inline = ch.get("inline")
                if inline:
                    ii: dict[str, Any] = {
                        "name": node_name(inline),
                        "fixedStart": int(inline["fixedStart"]),
                        "end": int(inline["end"]),
                    }
                    program = inline.get("program")
                    if program is not None:
                        ii["program"] = program
                        if program.get("direct"):
                            direct_inline_shaders += 1
                    out["inline"] = ii
                pr[kind] = out

            vd = p["children"]["vd"]
            pr["vd"] = {"pointer": vd["pointer"]}
            if vd.get("inline") is not None:
                pr["vd"]["inline"] = vd["inline"]

            ach = p["children"]["args"]
            ao: dict[str, Any] = {"pointer": ach["pointer"]}
            inline_args = ach.get("inline")
            if inline_args is not None:
                values = inline_args.get("values")
                if not isinstance(values, list):
                    raise ValueError(f"slot {tr['slot']} pass {pr['index']} lacks retained argument values")
                if len(values) != int(inline_args["count"]) or len(values) != pr["argCount"]:
                    raise ValueError(f"slot {tr['slot']} pass {pr['index']} argument count mismatch")
                for value in values:
                    if set(value) != {"type", "location", "size", "buffer", "u"}:
                        raise ValueError(f"slot {tr['slot']} pass {pr['index']} malformed argument")
                    typ = str(int(value["type"]))
                    argument_type_counts[typ] = argument_type_counts.get(typ, 0) + 1
                argument_count += len(values)
                ao["inline"] = {
                    "fixedStart": int(inline_args["fixedStart"]),
                    "end": int(inline_args["end"]),
                    "values": values,
                    "valuesSha256": canonical_values_hash(values),
                    "literals": inline_args.get("literals") or [],
                }
            elif pr["argCount"]:
                # Packed argument blocks are legal; the exact pointer remains in the proof.
                if (ach.get("pointer") or {}).get("kind") == "null":
                    raise ValueError(f"slot {tr['slot']} pass {pr['index']} nonzero args with null pointer")
            pr["args"] = ao
            tr["passes"].append(pr)
        techniques.append(tr)

    if len(techniques) != EXPECTED_INLINE_TECHNIQUES:
        raise ValueError(f"q20 inline TechniqueSet count drift: {len(techniques)}")
    if direct_inline_shaders != EXPECTED_DIRECT_INLINE_SHADERS:
        raise ValueError(f"q20 direct inline shader count drift: {direct_inline_shaders}")
    if argument_count != EXPECTED_ARGUMENTS:
        raise ValueError(f"q20 argument count drift: {argument_count}")
    if argument_type_counts != EXPECTED_ARGUMENT_TYPE_COUNTS:
        raise ValueError(f"q20 argument type counts drift: {argument_type_counts}")

    return {
        "format": FORMAT,
        "zone": "faction_seals_mp",
        "source": source,
        "producer": "tools/t6_seal6_q20_nested_proof_v1.py",
        "target": {
            "xassetIndex": 20,
            "material": "mc/mtl_c_usa_milcas_mcknight_head_camo",
            "name": EXPECTED_Q20["name"],
            "start": EXPECTED_Q20["start"],
            "end": EXPECTED_Q20["end"],
            "bytes": EXPECTED_Q20["bytes"],
            "sha256": EXPECTED_Q20["sha256"],
            "worldVertFormat": 0,
            "activeSlots": active_slots,
            "inlineTechniqueCount": len(techniques),
            "directInlineShaderPayloadCount": direct_inline_shaders,
            "shaderArgumentCount": argument_count,
            "argumentTypeCounts": argument_type_counts,
        },
        "techniques": techniques,
        "proofBoundary": [
            "Top-level q20 ownership and source extent come only from the continuous q0..q20 retail loader-order replay.",
            "Every inline technique, pass, shader, vertex declaration and MaterialShaderArgument child is consumed in retail serialization order; packed/null references consume zero source bytes.",
            "Each retained shader argument records the exact serialized fields type/location/size/buffer/u; inline literal payloads retain exact source starts and byte counts.",
            "Direct inline shader programs are required by the source walker to begin with DXBC and are retained by exact source start, byte count and SHA-256.",
            "No Blender/PBR semantic interpretation is asserted by this proof.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_order_json", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = json.loads(a.source_order_json.read_text(encoding="utf-8"))
    out = build(doc)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    # Compact JSON keeps all exact records while avoiding unnecessary repository bloat.
    a.out.write_text(json.dumps(out, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(out["target"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
