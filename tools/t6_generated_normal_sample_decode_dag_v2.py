#!/usr/bin/env python3
"""T6 generated normal sample decode DAG v2: include the exact base baseline.

v1 serializes every secondary generated normal layer's exact
normalMapSamplerN.x/y decode before any 2x2 transform. v2 also serializes the
base normal state used as the ordered recurrence baseline:

* ``zero`` when the retained pixel shader has no base normal decode pair;
* ``explicit_normal`` with exact ``normalMapSampler.x/y`` sample-only DAGs.

No signed RG formula is assumed; the compiled arithmetic remains forensic.
"""
from __future__ import annotations

import hashlib
from typing import Any

import t6_generated_normal_sample_decode_dag_v1 as v1
from t6_generated_height_weight_dag_v1 import _forensic_subgraph, validate_forensic_dag


FORMAT = "t6-generated-normal-sample-decode-dag-set-v2"


class GeneratedNormalDecodeDagV2Error(RuntimeError):
    pass


def _base_decode(comp, normal, d) -> dict:
    try:
        pair = normal.base_pair(comp, d)
    except Exception as exc:
        raise GeneratedNormalDecodeDagV2Error(f"exact base normal pair extraction failed: {exc}") from exc
    if pair is None:
        return {
            "mode": "zero",
            "normalResource": None,
            "sampleChannels": [],
            "components": [],
            "decodePairSha256": None,
        }
    if not isinstance(pair, list) or len(pair) != 2:
        raise GeneratedNormalDecodeDagV2Error("base normal pair is neither zero nor XY")
    resource = "normalMapSampler"
    components = []
    for component_index, channel in enumerate(("x", "y")):
        current_root = int(pair[component_index])
        try:
            decode_root = v1._maximal_decode_candidate(
                comp, normal, d, current_root, resource, channel
            )
            dag = _forensic_subgraph(d, decode_root)
            validate_forensic_dag(dag)
        except Exception as exc:
            raise GeneratedNormalDecodeDagV2Error(
                f"base normal {channel} decode isolation failed: {exc}"
            ) from exc
        leaves = v1._leaf_inventory(dag)
        if leaves["input"] or leaves["cb"]:
            raise GeneratedNormalDecodeDagV2Error(
                f"base normal {channel} decode has non-sample dependencies "
                f"inputs={leaves['input']} cb={leaves['cb']}"
            )
        samples = {
            (str(item["resource"]), str(item["channel"]))
            for item in leaves["sample"]
        }
        if samples != {(resource, channel)}:
            raise GeneratedNormalDecodeDagV2Error(
                f"base normal {channel} sample leaves {sorted(samples)} != {[(resource, channel)]}"
            )
        components.append({
            "component": channel,
            "currentNormalRoot": current_root,
            "decodeRoot": decode_root,
            "forensicDag": dag,
            "forensicDagSha256": dag["forensicDagSha256"],
            "leafInventory": leaves,
        })
    return {
        "mode": "explicit_normal",
        "normalResource": resource,
        "sampleChannels": ["x", "y"],
        "components": components,
        "decodePairSha256": v1._jhash([
            component["forensicDagSha256"] for component in components
        ]),
    }


def extract_normal_decode_dags(shader_bytes: bytes, technique_set: str, *, modules=None) -> dict:
    comp, normal, opcode, operand, inspect = modules or v1._load_default_modules()
    try:
        secondary = v1.extract_normal_decode_dags(
            shader_bytes,
            technique_set,
            modules=(comp, normal, opcode, operand, inspect),
        )
        d = comp.symbolic(shader_bytes, opcode, operand, inspect)
        baseline = _base_decode(comp, normal, d)
    except GeneratedNormalDecodeDagV2Error:
        raise
    except Exception as exc:
        raise GeneratedNormalDecodeDagV2Error(
            f"{technique_set!r}: normal decode v2 extraction failed: {exc}"
        ) from exc
    return {
        "format": FORMAT,
        "techniqueSet": technique_set,
        "pixelShaderSha256": hashlib.sha256(shader_bytes).hexdigest(),
        "baseline": baseline,
        "normalLayerCount": secondary["normalLayerCount"],
        "layers": secondary["layers"],
        "secondaryDecodePairSetSha256": secondary["decodePairSetSha256"],
        "baselineDecodePairSha256": baseline["decodePairSha256"],
        "allDecodeLeavesSampleOnly": bool(secondary["allDecodeLeavesSampleOnly"]),
        "proof": (
            "exact retained base_pair(normalMapSampler.x/y) baseline plus exact secondary current-pair "
            "sample-only decode DAGs; zero baseline retained explicitly when base_pair is absent"
        ),
    }
