#!/usr/bin/env python3
"""One-command fail-closed multiplayer T6 player-body closure driver.

Pipeline:
  exact target XModel probe
  -> exact top-level XAsset index binding
  -> skeleton normalize v2 (including unique reusable-owner resolution)
  -> mesh normalize v2 (packed skeleton reuse allowed only via skeleton-v2 proof)
  -> registry-ready retail body proof promotion

Every stage emits a durable artifact. If any stage cannot close exactly, the
driver writes a blocked closure report and does not emit a promoted body proof.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

FORMAT = "t6-player-body-closure-v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path: Path, obj: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_path(path)}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def default_modules(here: Path, raw_parser_path: Path):
    return SimpleNamespace(
        raw=load_module(raw_parser_path, "t6_body_close_raw"),
        probe=load_module(here / "t6_xmodel_target_probe_v1.py", "t6_body_close_probe"),
        skeleton=load_module(here / "t6_xmodel_skeleton_normalize_v2.py", "t6_body_close_skeleton"),
        mesh=load_module(here / "t6_xmodel_mesh_normalize_v2.py", "t6_body_close_mesh"),
        promoter=load_module(here / "t6_player_body_retail_proof_v1.py", "t6_body_close_promoter"),
    )


def _blocked(base: dict[str, Any], stage: str, reason: str, report_path: Path) -> dict[str, Any]:
    out = dict(base)
    out.update({"status": "blocked", "blockerStage": stage, "blocker": reason, "retailProof": None})
    dump(report_path, out)
    return out


def _probe_doc(data: bytes, stream: Path, name: str, row: dict[str, Any], rawmod, front: dict[str, Any]) -> dict[str, Any]:
    required = [row]
    exact = [r for r in required if r.get("status") == "exact_inline_xmodel"]
    return {
        "format": "t6-xmodel-target-probe-v1",
        "authority": "direct expanded retail T6 XFile bytes",
        "source": {
            "path": str(stream), "bytes": len(data), "sha256": sha256_bytes(data),
            "declaredBlockSizes": front.get("block_sizes"),
        },
        "rules": {
            "exactIdentityMatch": True, "fixedRecordBytes": 248,
            "allTopLevelPointersValidatedAgainstDeclaredBlocks": True,
            "packedOrReusedNamesAreNotGuessed": True, "rawStringOccurrenceAloneIsNotProof": True,
            "generatedByPlayerBodyClosure": True,
        },
        "summary": {
            "targets": 1, "requiredTargets": 1, "exactRequired": len(exact),
            "allRequiredExactInline": len(exact) == 1,
            "unresolvedRequired": [] if exact else [name],
        },
        "targets": [row],
    }


def resolve_xasset_index(data: bytes, name: str, fixed_start: int, skmod) -> tuple[int, dict[str, Any]]:
    table = skmod.parse_top_level_xasset_table(data)
    entries = table.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("top-level XAsset table is empty/unresolved")
    catalog = skmod.build_xmodel_catalog(data, len(entries) - 1)
    matches = []
    for idx, rec in catalog.items():
        if not isinstance(rec, dict):
            continue
        if int(rec.get("fixedSourceStart", -1)) == int(fixed_start) and rec.get("name") == name:
            matches.append((int(idx), rec))
    if len(matches) != 1:
        slim = [{"xassetIndex": i, "name": r.get("name"), "fixedSourceStart": r.get("fixedSourceStart")} for i, r in matches]
        raise ValueError(f"exact XModel could not bind to one top-level XAsset index: {slim}")
    return matches[0]


def close_body(*, name: str, zone_name: str, fastfile: Path, expanded: Path, raw_parser_path: Path,
               out_dir: Path, modules=None) -> dict[str, Any]:
    if not name or not zone_name:
        raise ValueError("name and zone_name are required")
    out_dir.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    mods = modules or default_modules(here, raw_parser_path)
    data = expanded.read_bytes()
    expanded_sha = sha256_bytes(data)
    base = {
        "format": FORMAT,
        "name": name,
        "zoneName": zone_name,
        "sourceFastfile": {"path": str(fastfile), "bytes": fastfile.stat().st_size, "sha256": sha256_path(fastfile)},
        "expandedStream": {"path": str(expanded), "bytes": len(data), "sha256": expanded_sha},
        "proofBoundary": "Closure requires exact XModel identity, unique top-level XAsset binding, closed skeleton decode, closed render-mesh decode, and successful retail body proof promotion. No candidate naming evidence is promoted by this driver.",
    }
    report_path = out_dir / "player_body_closure_v1.json"

    try:
        front = mods.raw.parse_front(data)
        blocks = [int(x["bytes"]) for x in front["block_sizes"]]
        row = mods.probe.probe_name(data, {"name": name, "required": True, "role": "multiplayer_full_body"}, mods.raw, blocks)
        probe_doc = _probe_doc(data, expanded, name, row, mods.raw, front)
        probe_art = dump(out_dir / "xmodel_target_probe_v1.json", probe_doc)
        base["xmodelProbe"] = probe_art
        if row.get("status") != "exact_inline_xmodel":
            return _blocked(base, "xmodel-identity", f"target probe status: {row.get('status')}: {row.get('reason')}", report_path)
    except Exception as e:
        return _blocked(base, "xmodel-identity", str(e), report_path)

    fixed_start = int(row["rawStructOffset"])

    try:
        xasset_index, catalog_row = resolve_xasset_index(data, name, fixed_start, mods.skeleton)
        base["xassetBinding"] = {
            "status": "exact", "xassetIndex": xasset_index,
            "catalogName": catalog_row.get("name"), "fixedSourceStart": catalog_row.get("fixedSourceStart"),
        }
    except Exception as e:
        return _blocked(base, "xasset-index-binding", str(e), report_path)

    try:
        sk = mods.skeleton.normalize_skeleton(data, fixed_start, xasset_index=xasset_index, identity_name=name)
        sk_art = dump(out_dir / "xmodel_skeleton_normalized_v2.json", sk)
        base["skeleton"] = sk_art
        val = sk.get("validation", {})
        if val.get("allBoneNamesResolved") is not True or val.get("hierarchyValid") is not True:
            raise ValueError("normalized skeleton did not close bone names and hierarchy")
    except Exception as e:
        return _blocked(base, "skeleton", str(e), report_path)

    try:
        if hasattr(mods.mesh, "normalize_mesh"):
            mesh = mods.mesh.normalize_mesh(data, fixed_start, sk)
        else:
            mesh = mods.mesh.Normalizer(data, fixed_start).normalize()
            mesh["expandedSha256"] = expanded_sha
        mesh_name = "xmodel_mesh_normalized_v2.json" if mesh.get("format") == "t6-xmodel-mesh-normalized-v2" else "xmodel_mesh_normalized_v1.json"
        mesh_art = dump(out_dir / mesh_name, mesh)
        base["mesh"] = mesh_art
        if mesh.get("validation", {}).get("allLocalTriangleIndicesInRange") is not True:
            raise ValueError("normalized mesh did not close local triangle ranges")
    except Exception as e:
        return _blocked(base, "mesh", str(e), report_path)

    try:
        proof_path = out_dir / "player_body_retail_proof_v1.json"
        proof = mods.promoter.build(
            name=name, zone_name=zone_name, fastfile_path=fastfile, expanded_path=expanded,
            probe_path=Path(base["xmodelProbe"]["path"]), skeleton_path=Path(base["skeleton"]["path"]),
            mesh_path=Path(base["mesh"]["path"]),
        )
        proof_art = dump(proof_path, proof)
    except Exception as e:
        return _blocked(base, "promotion", str(e), report_path)

    out = dict(base)
    out.update({
        "status": "closed", "blockerStage": None, "blocker": None,
        "retailProof": proof_art,
        "summary": {
            "xassetIndex": xasset_index,
            "bones": proof["fullBody"]["bones"], "rootBones": proof["fullBody"]["rootBones"],
            "surfaces": proof["fullBody"]["surfaces"], "vertices": proof["fullBody"]["mesh"]["vertices"],
            "triangles": proof["fullBody"]["mesh"]["triangles"],
        },
    })
    dump(report_path, out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--zone-name", required=True)
    ap.add_argument("--fastfile", type=Path, required=True)
    ap.add_argument("--expanded", type=Path, required=True)
    ap.add_argument("--raw-parser", type=Path, default=Path(__file__).with_name("t6_raw_xasset_inventory_v2.py"))
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    out = close_body(name=a.name, zone_name=a.zone_name, fastfile=a.fastfile, expanded=a.expanded,
                     raw_parser_path=a.raw_parser, out_dir=a.out_dir)
    print(json.dumps({"status": out["status"], "name": a.name, "blockerStage": out.get("blockerStage"),
                      "blocker": out.get("blocker"), "summary": out.get("summary")}, indent=2))
    return 0 if out["status"] == "closed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
