#!/usr/bin/env python3
"""Close the single retail T6 patch_mp WEAPON into final selector precedence.

The command is deliberately strict. It will only emit a promotable patch_mp
selector layer when all of these gates pass on the exact retained retail data:

1. source patch_mp.ff size + SHA-256 (when --fastfile is used),
2. expanded stream size + SHA-256,
3. XAsset count == 1764,
4. top-level WEAPON count == 1,
5. exactly one structural/cardinality WeaponVariantDef binding,
6. exact internal-name identity, and
7. exact direct WeaponDef player-animation selector.

No public dump, weapon-category assumption, or string-proximity heuristic is
consulted. If any gate fails, the result is BLOCKED and precedence is not
promoted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_PATCH_FF_BYTES = 3_638_592
EXPECTED_PATCH_FF_SHA256 = "459077cda8e4a1457f7ee7d8f6c5e0abf30f41767a21ff6744df6a4307cbce1e"
EXPECTED_EXPANDED_BYTES = 14_713_756
EXPECTED_EXPANDED_SHA256 = "1bd82b0e99fcea3a9cb1c2342634f1da0d699b3fdadfa9f7c7fe15595952a7b9"
EXPECTED_ASSET_COUNT = 1764
EXPECTED_WEAPON_COUNT = 1
EXACT_NAME_STATUSES = {"exact-inline-following", "exact-packed-front-xstring"}
EXACT_BINDING_STATUS = "exact-by-single-inline-weapon-cardinality"
EXACT_STRUCTURAL_SELECTOR_STATUS = "exact-direct-weapdef-prefix"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_artifact(path: Path, expected_bytes: int, expected_sha256: str, label: str) -> dict[str, Any]:
    actual_bytes = path.stat().st_size
    actual_sha = sha256_path(path)
    ok = actual_bytes == expected_bytes and actual_sha.lower() == expected_sha256.lower()
    proof = {
        "label": label,
        "path": str(path),
        "expectedBytes": expected_bytes,
        "actualBytes": actual_bytes,
        "expectedSha256": expected_sha256,
        "actualSha256": actual_sha,
        "exact": ok,
    }
    if not ok:
        raise ValueError(
            f"{label} mismatch: bytes {actual_bytes} != {expected_bytes} or "
            f"sha256 {actual_sha} != {expected_sha256}"
        )
    return proof


def blocked(code: str, message: str, **evidence: Any) -> dict[str, Any]:
    return {
        "status": "blocked",
        "blocker": {"code": code, "message": message, **evidence},
    }


def evaluate_probe_result(
    probe: dict[str, Any],
    expected_asset_count: int = EXPECTED_ASSET_COUNT,
    expected_weapon_count: int = EXPECTED_WEAPON_COUNT,
) -> dict[str, Any]:
    front = probe.get("front") or {}
    asset_count = front.get("assetCount")
    weapon_count = front.get("weaponAssetCount")
    if asset_count != expected_asset_count:
        return blocked(
            "asset-count-mismatch",
            "expanded patch_mp XAsset count does not match the retained retail proof",
            expected=expected_asset_count,
            actual=asset_count,
        )
    if weapon_count != expected_weapon_count:
        return blocked(
            "weapon-count-mismatch",
            "patch_mp must contain exactly the retained top-level WEAPON cardinality",
            expected=expected_weapon_count,
            actual=weapon_count,
        )

    bindings = [b for b in (probe.get("bindings") or []) if b.get("status") == EXACT_BINDING_STATUS]
    if len(bindings) != 1:
        return blocked(
            "cardinality-binding-not-unique",
            "exactly one structural WeaponVariantDef cardinality binding is required",
            exactBindings=len(bindings),
            bindings=probe.get("bindings") or [],
        )

    binding = bindings[0]
    wvd = binding.get("weaponVariantDef") or {}
    name_status = wvd.get("internalNameStatus")
    name = wvd.get("internalName")
    if name_status not in EXACT_NAME_STATUSES or not isinstance(name, str) or not name:
        resolution = wvd.get("packedInternalNameResolution")
        return blocked(
            "internal-name-unresolved",
            "the sole patch_mp WeaponVariantDef internal name is not exact under the retail proof rules",
            internalNameStatus=name_status,
            internalName=name,
            packedResolution=resolution,
        )

    structural_selector = wvd.get("selector") or {}
    if structural_selector.get("status") != EXACT_STRUCTURAL_SELECTOR_STATUS:
        return blocked(
            "selector-unresolved",
            "the sole patch_mp WeaponDef player-animation selector is not exact",
            selectorStatus=structural_selector.get("status"),
            selector=structural_selector,
        )
    pair = structural_selector.get("selector") or {}
    weaponclass = pair.get("weaponclass")
    player_anim = pair.get("playerAnimType")
    if not isinstance(weaponclass, str) or not weaponclass or not isinstance(player_anim, str) or not player_anim:
        return blocked(
            "selector-pair-invalid",
            "exact structural selector did not contain a complete weaponclass/playerAnimType pair",
            selector=pair,
        )

    return {
        "status": "exact",
        "weapon": name,
        "assetIndex": binding.get("assetIndex"),
        "internalNameStatus": name_status,
        "structuralSelectorStatus": structural_selector.get("status"),
        "selector": {"weaponclass": weaponclass, "playerAnimType": player_anim},
        "weaponMetadata": {
            "weaponType": structural_selector.get("weaponType"),
            "fireType": structural_selector.get("fireType"),
            "weaponClass": structural_selector.get("weaponClass"),
            "playerAnimType": structural_selector.get("playerAnimType"),
        },
        "rawStructOffset": wvd.get("rawStructOffset"),
        "rawFixedSha256": wvd.get("rawFixedSha256"),
        "rawWeaponDefPrefixOffset": structural_selector.get("rawOffset"),
        "rawWeaponDefPrefixSha256": structural_selector.get("rawPrefixSha256"),
    }


def build_selector_layer(exact: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    if exact.get("status") != "exact":
        raise ValueError("cannot build selector layer from blocked closure result")
    return {
        "format": "t6-weapon-playeranim-selector-layer-v1",
        "zone": "patch_mp",
        "authority": "exact retained retail patch_mp structural selector closure",
        "source": source,
        "weapons": [{
            "weapon": exact["weapon"],
            # Normalized status accepted by t6_weapon_playeranim_precedence_v1.py.
            "selectorStatus": "exact",
            "selector": exact["selector"],
            "structuralSelectorStatus": exact["structuralSelectorStatus"],
            "internalNameStatus": exact["internalNameStatus"],
            "assetIndex": exact.get("assetIndex"),
            "weaponMetadata": exact.get("weaponMetadata"),
            "rawStructOffset": exact.get("rawStructOffset"),
            "rawFixedSha256": exact.get("rawFixedSha256"),
            "rawWeaponDefPrefixOffset": exact.get("rawWeaponDefPrefixOffset"),
            "rawWeaponDefPrefixSha256": exact.get("rawWeaponDefPrefixSha256"),
        }],
        "proofBoundary": (
            "This layer exists only after exact retained patch_mp source/expanded identity, "
            "single-WEAPON cardinality, exact WeaponVariantDef name, and exact direct "
            "WeaponDef selector all pass. No external weapon dump or category assumption "
            "participates in naming or selector promotion."
        ),
    }


def promote_patch_layer_in_spec(spec: dict[str, Any], selector_manifest: str) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    layers = out.get("layers")
    if not isinstance(layers, list):
        raise ValueError("precedence spec has no layers list")
    matches = [layer for layer in layers if isinstance(layer, dict) and layer.get("name") == "patch_mp"]
    if len(matches) != 1:
        raise ValueError(f"precedence spec must contain exactly one patch_mp layer, found {len(matches)}")
    layer = matches[0]
    unknown = int(layer.get("unknownWeaponAssetCount", 0) or 0)
    if unknown != 1:
        raise ValueError(f"patch_mp layer expected unknownWeaponAssetCount=1 before promotion, found {unknown}")
    layer["selectorManifest"] = selector_manifest
    layer["unknownWeaponAssetCount"] = 0
    return out


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_summary(fastfile_proof: dict[str, Any] | None, expanded_proof: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "expandedBytes": expanded_proof["actualBytes"],
        "expandedSha256": expanded_proof["actualSha256"],
    }
    if fastfile_proof is not None:
        out["fastfileBytes"] = fastfile_proof["actualBytes"]
        out["fastfileSha256"] = fastfile_proof["actualSha256"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--fastfile", type=Path, help="exact retained retail patch_mp.ff")
    src.add_argument("--expanded", type=Path, help="exact retained expanded patch_mp stream")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--precedence-spec", type=Path)
    ap.add_argument("--precedence-spec-out", type=Path)
    ap.add_argument("--precedence-out", type=Path)
    args = ap.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    fastfile_proof = None

    if args.fastfile is not None:
        fastfile_proof = verify_artifact(
            args.fastfile, EXPECTED_PATCH_FF_BYTES, EXPECTED_PATCH_FF_SHA256, "retail patch_mp.ff"
        )
        expanded_path = out_dir / "patch_mp.expanded.bin"
        expander = load_module(Path(__file__).with_name("t6_pc_fastfile_expand_v1.py"), "t6_pc_fastfile_expand_for_patch_closure")
        expander.expand_fastfile(args.fastfile, expanded_path)
    else:
        expanded_path = args.expanded
        assert expanded_path is not None

    expanded_proof = verify_artifact(
        expanded_path, EXPECTED_EXPANDED_BYTES, EXPECTED_EXPANDED_SHA256, "retail expanded patch_mp"
    )

    rawmod = load_module(Path(__file__).with_name("t6_raw_xasset_inventory_v2.py"), "t6_raw_xasset_inventory_for_patch_closure")
    v1mod = load_module(Path(__file__).with_name("t6_weapon_xasset_structural_probe_v1.py"), "t6_weapon_probe_v1_for_patch_closure")
    frontmap = load_module(Path(__file__).with_name("t6_virtual_front_map_v1.py"), "t6_virtual_front_map_for_patch_closure")
    v2mod = load_module(Path(__file__).with_name("t6_weapon_xasset_structural_probe_v2.py"), "t6_weapon_probe_v2_for_patch_closure")

    data = expanded_path.read_bytes()
    probe = v2mod.probe(data, rawmod, v1mod, frontmap)
    probe_path = out_dir / "patch_mp_weapon_structural_probe_v2.json"
    write_json(probe_path, probe)

    evaluated = evaluate_probe_result(probe)
    closure: dict[str, Any] = {
        "format": "t6-patch-weapon-closure-v1",
        "zone": "patch_mp",
        "sourceVerification": {
            "fastfile": fastfile_proof,
            "expanded": expanded_proof,
        },
        "probe": {
            "path": str(probe_path),
            "format": probe.get("format"),
            "summary": probe.get("summary"),
        },
        "result": evaluated,
        "proofBoundary": (
            "Exact retail identity requires exact source/expanded hashes and sizes, the retained "
            "1764-XAsset / one-WEAPON cardinality, one exact structural binding, one exact "
            "WeaponVariantDef internal name, and one exact direct WeaponDef selector. External "
            "Peacekeeper expectations are not consulted. Blocked results never clear precedence."
        ),
    }

    selector_path = out_dir / "patch_mp_playeranim_selector_layer_v1.json"
    closure_path = out_dir / "patch_mp_weapon_closure_v1.json"
    if evaluated.get("status") != "exact":
        write_json(closure_path, closure)
        print(json.dumps({"status": "blocked", "blocker": evaluated.get("blocker")}, indent=2, sort_keys=True))
        return 2

    selector_layer = build_selector_layer(evaluated, _source_summary(fastfile_proof, expanded_proof))
    write_json(selector_path, selector_layer)
    closure["selectorLayer"] = {"path": str(selector_path), "weapon": evaluated["weapon"], "selector": evaluated["selector"]}

    if args.precedence_spec is not None:
        if args.precedence_spec_out is None:
            raise ValueError("--precedence-spec requires --precedence-spec-out")
        if args.precedence_spec_out.parent.resolve() != args.precedence_spec.parent.resolve():
            raise ValueError(
                "--precedence-spec-out must be in the same directory as --precedence-spec so existing relative layer references remain unchanged"
            )
        spec = json.loads(args.precedence_spec.read_text(encoding="utf-8-sig"))
        selector_ref = os.path.relpath(selector_path.resolve(), args.precedence_spec.parent.resolve()).replace(os.sep, "/")
        promoted = promote_patch_layer_in_spec(spec, selector_ref)
        write_json(args.precedence_spec_out, promoted)
        closure["precedencePromotion"] = {
            "inputSpec": str(args.precedence_spec),
            "outputSpec": str(args.precedence_spec_out),
            "patchSelectorManifest": selector_ref,
            "patchUnknownWeaponAssetCount": 0,
        }
        if args.precedence_out is not None:
            command = [
                sys.executable,
                str(Path(__file__).with_name("t6_weapon_playeranim_precedence_v1.py")),
                "--spec", str(args.precedence_spec_out),
                "--out", str(args.precedence_out),
            ]
            proc = subprocess.run(command, capture_output=True, text=True)
            closure["precedenceResolver"] = {
                "output": str(args.precedence_out),
                "returnCode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
    elif args.precedence_spec_out is not None or args.precedence_out is not None:
        raise ValueError("precedence output arguments require --precedence-spec")

    write_json(closure_path, closure)
    print(json.dumps({"status": "exact", "weapon": evaluated["weapon"], "selector": evaluated["selector"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
