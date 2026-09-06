#!/usr/bin/env python3
"""Repair exact T6 static-XModel texture roles even when a legacy GLB role is occupied.

v2 source-closes image identity by MaterialTextureDef semantic and exact IPAK
(nameHash,dataHash), but intentionally skipped roles that were already populated.
That lets an older preview mistake survive forever (for example the Nuketown
Ficus bark Material stores NORMAL_MAP in slot 0 and COLOR_MAP in slot 1).

v3 preserves all v2 identity requirements and changes only the role policy:
- semantic 2 (TS_COLOR_MAP) owns glTF Base Color;
- semantic 5 (TS_NORMAL_MAP) owns glTF Normal;
- an occupied role is preserved only if it already targets the exact proven
  image; otherwise it is cleared and rebound through v2's exact-pair path;
- a role is never cleared unless the exact replacement is available in the
  supplied IPAK (or is the separately loader-proven identity normal).

No material-name similarity, texture-table position, visual color, or fallback
image lookup is admitted.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2_PATH = HERE / "t6_nuketown_static_xmodel_texture_apply_v2.py"
spec = importlib.util.spec_from_file_location("t6_static_tex_v2", V2_PATH)
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
base = v2.base


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound_texture_name(js: dict, role: dict | None) -> str | None:
    if not isinstance(role, dict):
        return None
    ti = role.get("index")
    textures = js.get("textures", [])
    images = js.get("images", [])
    if not isinstance(ti, int) or not (0 <= ti < len(textures)):
        return None
    si = textures[ti].get("source")
    if not isinstance(si, int) or not (0 <= si < len(images)):
        return None
    return images[si].get("name")


def expected_role(src: dict, sem: int, by_pair: dict) -> dict | None:
    t = v2.first_sem(src, sem)
    if not t:
        return None
    if sem == 5 and v2.packed_key(t) == (v2.IDENTITY_BLOCK, v2.IDENTITY_OFFSET):
        return {
            "semantic": sem,
            "image": v2.IDENTITY_NAME,
            "dataHash": None,
            "resolution": "loader-address-proof-identitynormal",
            "replaceable": True,
        }
    im = t.get("image") or {}
    if not (im.get("inline") and im.get("name")):
        return None
    dh = im.get("streamedPart0Hash29")
    if dh is None:
        return None
    nh = base.r_hash_string(im["name"])
    entry = by_pair.get((nh, dh))
    return {
        "semantic": sem,
        "image": im["name"],
        "nameHash": nh,
        "dataHash": dh,
        "resolution": "ipak-exact-name+data-hash",
        "replaceable": entry is not None,
    }


def role_ref(material: dict, kind: str):
    if kind == "color":
        return (material.get("pbrMetallicRoughness") or {}).get("baseColorTexture")
    return material.get("normalTexture")


def clear_role(material: dict, kind: str) -> None:
    if kind == "color":
        pbr = material.setdefault("pbrMetallicRoughness", {})
        pbr.pop("baseColorTexture", None)
    else:
        material.pop("normalTexture", None)


def build(in_glb: Path, catalog_path: Path, ipak_path: Path, out_glb: Path, manifest_path: Path) -> dict:
    cat = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_mat = {m["name"]: m for m in cat["materials"] if m.get("status") == "located"}
    js, binbuf = base.read_glb(in_glb)
    _data, _sec, by_pair, _by_name, _by_data, _lzo = v2.read_ipak(ipak_path)

    decisions = []
    exact_occupied = 0
    wrong_occupied = 0
    empty_resolvable = 0
    unresolved_preserved = 0

    for mi, material in enumerate(js.get("materials", [])):
        src = by_mat.get(material.get("name"))
        if not src:
            continue
        for sem, kind in v2.SEMANTICS:
            expected = expected_role(src, sem, by_pair)
            if not expected:
                continue
            old_ref = role_ref(material, kind)
            old_name = bound_texture_name(js, old_ref)
            occupied = old_ref is not None
            if not expected["replaceable"]:
                unresolved_preserved += int(occupied)
                decisions.append({
                    "materialIndex": mi, "material": material.get("name"), "kind": kind,
                    "semantic": sem, "expectedImage": expected["image"], "oldImage": old_name,
                    "action": "preserve-unverified-role-no-exact-replacement" if occupied else "leave-empty-no-exact-replacement",
                })
                continue

            if occupied and old_name == expected["image"]:
                exact_occupied += 1
                action = "rebind-exact-existing-role-through-v2"
            elif occupied:
                wrong_occupied += 1
                action = "repair-wrong-occupied-role"
            else:
                empty_resolvable += 1
                action = "bind-empty-role"
            clear_role(material, kind)
            decisions.append({
                "materialIndex": mi, "material": material.get("name"), "kind": kind,
                "semantic": sem, "expectedImage": expected["image"], "oldImage": old_name,
                "expectedDataHash": expected.get("dataHash"), "action": action,
            })

    with tempfile.TemporaryDirectory(prefix="t6-static-v3-") as td:
        td = Path(td)
        sanitized = td / "sanitized.glb"
        v2_manifest_path = td / "v2.json"
        base.write_glb(sanitized, js, binbuf)
        v2.build(sanitized, catalog_path, ipak_path, out_glb, v2_manifest_path)
        v2_manifest = json.loads(v2_manifest_path.read_text(encoding="utf-8"))

    out_js, _ = base.read_glb(out_glb)
    out_by_name = collections.defaultdict(list)
    for i, m in enumerate(out_js.get("materials", [])):
        out_by_name[m.get("name")].append((i, m))

    validated = 0
    for d in decisions:
        if d["action"] not in ("repair-wrong-occupied-role", "rebind-exact-existing-role-through-v2", "bind-empty-role"):
            continue
        matches = out_by_name.get(d["material"], [])
        if len(matches) != 1:
            raise ValueError(f"{d['material']}: expected one output material, got {len(matches)}")
        _, m = matches[0]
        actual = bound_texture_name(out_js, role_ref(m, d["kind"]))
        if actual != d["expectedImage"]:
            raise ValueError(f"{d['material']} {d['kind']}: {actual!r} != exact {d['expectedImage']!r}")
        validated += 1

    # Hard regression canary for the reported Nuketown Ficus failure.
    ficus = out_by_name.get("mlv/mtl_p6_tree_ficus_lrg_01_bark1", [])
    ficus_canary = None
    if ficus:
        if len(ficus) != 1:
            raise ValueError("Ficus bark material is not unique")
        _, fm = ficus[0]
        color = bound_texture_name(out_js, role_ref(fm, "color"))
        normal = bound_texture_name(out_js, role_ref(fm, "normal"))
        if color == "p6_tree_ficus_lrg_01_bark1_n":
            raise ValueError("Ficus normal map is still bound as Base Color")
        if color != "~-gp6_tree_ficus_lrg_01_bark1_c":
            raise ValueError(f"Ficus Base Color is {color!r}, expected exact semantic-2 color image")
        if normal != "p6_tree_ficus_lrg_01_bark1_n":
            raise ValueError(f"Ficus Normal is {normal!r}, expected exact semantic-5 normal image")
        ficus_canary = {"baseColor": color, "normal": normal, "passed": True}

    report = {
        "format": "t6-nuketown-static-xmodel-texture-apply-v3",
        "input": {"file": in_glb.name, "bytes": in_glb.stat().st_size, "sha256": sha(in_glb)},
        "output": {"file": out_glb.name, "bytes": out_glb.stat().st_size, "sha256": sha(out_glb)},
        "catalog": {"file": catalog_path.name, "sha256": sha(catalog_path)},
        "ipak": {"file": ipak_path.name, "sha256": sha(ipak_path)},
        "summary": {
            "exactOccupiedRolesRevalidated": exact_occupied,
            "wrongOccupiedRolesRepaired": wrong_occupied,
            "emptyResolvableRolesBound": empty_resolvable,
            "unresolvedOccupiedRolesPreserved": unresolved_preserved,
            "validatedExactOutputRoles": validated,
        },
        "ficusRegression": ficus_canary,
        "v2InnerSummary": v2_manifest.get("summary"),
        "decisions": decisions,
        "proofBoundary": (
            "MaterialTextureDef semantic owns role: 2=color, 5=normal. Occupied legacy roles are no longer trusted merely because populated. "
            "A role is cleared only when an exact-pair replacement (or loader-proven identity normal) is available, then rebound through the v2 exact identity path."
        ),
    }
    manifest_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    if ficus_canary:
        print(json.dumps({"ficusRegression": ficus_canary}, indent=2, sort_keys=True))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", type=Path, required=True)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--ipak", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    a = ap.parse_args()
    build(a.glb, a.catalog, a.ipak, a.out, a.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
