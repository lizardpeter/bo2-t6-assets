#!/usr/bin/env python3
"""Prove exact Nuketown shadowcaster depth/shadow render-state semantics.

The two Nuketown Materials classified as `shadowcaster` are not interpreted from
that family label. Their native OAT Material `stateBitsEntry` arrays are indexed
with T6's exact 36-entry MaterialTechniqueType order, then joined to the exact
stateBits records and exact Technique/shader groups from the special census.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

FORMAT = "t6-nuketown-shadowcaster-state-v1"
SPECIAL_FORMAT = "t6-nuketown-special-material-census-v1"
BINDING_FORMAT = "t6-nuketown-special-material-input-binding-v1"
TARGETS = ("wpc/caulk_shadow_primary", "wpc/shadowcaster")
EXPECTED_SLOT_STATES = {
    "depth prepass": 0,
    "build shadowmap depth": 1,
    "unlit": 2,
    "emissive": 2,
    "solid wireframe": 3,
    "debug performance": 4,
}
EXPECTED_VS = "b77f42b646f07d63214ebf3132d187f13073329756c437c91dfcfe7131952ba3"
EXPECTED_PS = "ba6a650c7c7f4a7703a13ad59ba939958af63e114e90ef67d74c4acad7fecf0b"


class ShadowStateError(RuntimeError):
    pass


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ShadowStateError(f"expected object in {path}")
    return obj


def digest(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def exact_stage_pair(group: dict[str, Any]) -> dict[str, str]:
    passes = group.get("passes", [])
    if len(passes) != 1:
        raise ShadowStateError(f"group {group.get('groupKey')}: expected one pass")
    stages = passes[0].get("stages", [])
    vs = [str(s.get("sha256") or "") for s in stages if s.get("kind") == "vertexShader"]
    ps = [str(s.get("sha256") or "") for s in stages if s.get("kind") == "pixelShader"]
    if vs != [EXPECTED_VS] or ps != [EXPECTED_PS]:
        raise ShadowStateError(f"unexpected depth/shadow shader pair vs={vs} ps={ps}")
    return {"vertexShaderSha256": vs[0], "pixelShaderSha256": ps[0]}


def require_shadow_state(state: dict[str, Any]) -> None:
    expected = {
        "alphaTest": "disabled",
        "blendOpAlpha": "disabled",
        "blendOpRgb": "disabled",
        "colorWriteAlpha": False,
        "colorWriteRgb": False,
        "cullFace": "back",
        "depthTest": "less_equal",
        "depthWrite": True,
        "dstBlendAlpha": "zero",
        "dstBlendRgb": "zero",
        "polygonOffset": "offsetShadowmap",
        "polymodeLine": False,
        "srcBlendAlpha": "one",
        "srcBlendRgb": "one",
    }
    for k, v in expected.items():
        if state.get(k) != v:
            raise ShadowStateError(f"shadowmap state {k}={state.get(k)!r}, expected {v!r}")


def require_depth_state(state: dict[str, Any]) -> None:
    expected = {
        "alphaTest": "disabled",
        "blendOpAlpha": "disabled",
        "blendOpRgb": "disabled",
        "colorWriteAlpha": False,
        "colorWriteRgb": False,
        "cullFace": "back",
        "depthTest": "less_equal",
        "depthWrite": True,
        "dstBlendAlpha": "zero",
        "dstBlendRgb": "zero",
        "polygonOffset": "offset0",
        "polymodeLine": False,
        "srcBlendAlpha": "one",
        "srcBlendRgb": "one",
    }
    for k, v in expected.items():
        if state.get(k) != v:
            raise ShadowStateError(f"depth-prepass state {k}={state.get(k)!r}, expected {v!r}")
    stencil = state.get("stencilFront")
    if not isinstance(stencil, dict) or stencil != {"fail": "keep", "func": "equal", "pass": "keep", "zfail": "keep"}:
        raise ShadowStateError(f"depth-prepass stencilFront changed: {stencil}")


def build(special_path: Path, binding_path: Path, slot_tool: Path) -> dict[str, Any]:
    special = read_json(special_path)
    binding = read_json(binding_path)
    if special.get("format") != SPECIAL_FORMAT:
        raise ShadowStateError(f"unexpected special format {special.get('format')}")
    if binding.get("format") != BINDING_FORMAT:
        raise ShadowStateError(f"unexpected binding format {binding.get('format')}")
    if int(special.get("summary", {}).get("pcServerDuplicateParentSelectionDependencyCount", -1)) != 0:
        raise ShadowStateError("special population depends on unresolved duplicate parent")

    slot = load(slot_tool, "t6_slot_names")
    names = tuple(slot.TECHNIQUE_TYPE_NAMES)
    if len(names) != 36 or names[0:4] != ("depth prepass", "build shadowmap depth", "unlit", "emissive"):
        raise ShadowStateError("T6 TechniqueType table changed")

    sm = {str(x.get("material")): x for x in special.get("materials", [])}
    bm = {str(x.get("material")): x for x in binding.get("materials", [])}
    groups = {str(x.get("groupKey")): x for x in special.get("shaderGroups", [])}
    rows = []
    state_payloads = []

    for material_name in TARGETS:
        srow = sm.get(material_name)
        brow = bm.get(material_name)
        if not srow or not brow or srow.get("family") != "shadowcaster":
            raise ShadowStateError(f"missing exact shadowcaster Material {material_name}")
        entries = brow.get("stateBitsEntry")
        states = brow.get("stateBits")
        if not isinstance(entries, list) or len(entries) != len(names):
            raise ShadowStateError(f"{material_name}: stateBitsEntry shape changed")
        if not isinstance(states, list) or len(states) != 5:
            raise ShadowStateError(f"{material_name}: stateBits count changed")

        slot_rows = []
        programs = {str(p.get("techniqueType")): p for p in srow.get("programs", [])}
        if set(programs) != set(EXPECTED_SLOT_STATES):
            raise ShadowStateError(f"{material_name}: declared program set changed {sorted(programs)}")
        for technique_type, expected_state_index in EXPECTED_SLOT_STATES.items():
            idx = names.index(technique_type)
            state_index = entries[idx]
            if state_index != expected_state_index:
                raise ShadowStateError(
                    f"{material_name}/{technique_type}: stateBitsEntry[{idx}]={state_index}, expected {expected_state_index}"
                )
            if state_index < 0 or state_index >= len(states):
                raise ShadowStateError(f"{material_name}/{technique_type}: invalid state index {state_index}")
            prog = programs[technique_type]
            group = groups.get(str(prog.get("groupKey") or ""))
            if not group:
                raise ShadowStateError(f"{material_name}/{technique_type}: missing group")
            pair = None
            if technique_type in ("depth prepass", "build shadowmap depth"):
                pair = exact_stage_pair(group)
            slot_rows.append(
                {
                    "techniqueType": technique_type,
                    "techniqueTypeIndex": idx,
                    "stateBitsIndex": state_index,
                    "stateBits": states[state_index],
                    "technique": prog.get("technique"),
                    "groupKey": prog.get("groupKey"),
                    "depthShaderPair": pair,
                }
            )

        require_depth_state(states[0])
        require_shadow_state(states[1])
        state_payloads.append({"entries": entries, "states": states})
        rows.append(
            {
                "material": material_name,
                "techniqueSet": srow.get("techniqueSet"),
                "stateBitsEntry": entries,
                "stateBits": states,
                "slots": slot_rows,
                "statePayloadSha256": digest({"entries": entries, "states": states}),
            }
        )

    if state_payloads[0] != state_payloads[1]:
        raise ShadowStateError("two shadowcaster Materials disagree on state payload")

    core = {"techniqueTypeNames": list(names), "materials": rows}
    return {
        "format": FORMAT,
        "producer": "tools/t6_nuketown_shadowcaster_state_v1.py",
        "map": "mp_nuketown_2020",
        "summary": {
            "materialCount": 2,
            "identicalStatePayloadCount": 2,
            "stateBitsCount": 5,
            "declaredTechniqueCountPerMaterial": 6,
            "depthPrepassColorWrites": False,
            "depthPrepassDepthWrites": True,
            "shadowmapColorWrites": False,
            "shadowmapDepthWrites": True,
            "shadowmapPolygonOffset": "offsetShadowmap",
            "exactDepthShaderPairCount": 2,
        },
        **core,
        "evidenceDigestSha256": digest(core),
        "proofBoundary": (
            "The shadow/depth behavior is derived from exact native OAT Material stateBitsEntry/stateBits records indexed by T6's exact MaterialTechniqueType order, and from the exact native Technique/shader groups. "
            "The family name `shadowcaster` contributes only target population identity. This proves the selected depth-prepass and build-shadowmap-depth state/shader behavior; it does not by itself prove which runtime render list invokes each technique or replace the separately exact unlit/emissive bindings."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--special-census", type=Path, required=True)
    ap.add_argument("--binding", type=Path, required=True)
    ap.add_argument("--slot-tool", type=Path, default=Path("tools/t6_oat_slot_shader_resolver_v1.py"))
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = build(a.special_census, a.binding, a.slot_tool)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print(doc["evidenceDigestSha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
