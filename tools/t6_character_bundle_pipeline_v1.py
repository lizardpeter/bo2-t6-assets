#!/usr/bin/env python3
"""Deterministic T6 character/XModel bundle pipeline v1.

This orchestrates the proof-backed model/skin/animation tools already retained in
bo2-t6-assets. It does not invent missing data and it intentionally keeps
material/image extraction as separately supplied proof-backed sidecars.

Inputs:
- one expanded/decrypted T6 fastfile byte stream
- exact XModel fixed-record source offset
- optional XAsset index (required for reusable skeleton-owner resolution)
- zero or more already-normalized t6-xanim-normalized-v1 JSON files
- optional material/image dependency manifests

Outputs:
- normalized mesh JSON
- normalized skeleton JSON
- bind-pose glTF
- one animated glTF per supplied XAnim
- hash-pinned bundle manifest tying all outputs back to the expanded retail bytes

The pipeline fails closed when a downstream source-backed extractor rejects the
fixture. No fallback mesh, skeleton, animation, texture, or material is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

FORMAT = "t6-character-bundle-v1"
SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(value: str) -> str:
    value = value.replace("\\", "/").strip("/")
    value = value.rsplit("/", 1)[-1]
    value = SAFE.sub("_", value).strip("._")
    return value or "asset"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def run(cmd: list[str], *, cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if proc.returncode:
        if proc.stdout:
            sys.stderr.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")
    if proc.stdout:
        sys.stdout.write(proc.stdout)


def artifact(path: Path, *, root: Path, kind: str, format_name: str | None = None) -> dict:
    row = {
        "kind": kind,
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }
    if format_name is not None:
        row["format"] = format_name
    return row


def parse_named_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        p = Path(value)
        return p.stem, p
    name, raw = value.split("=", 1)
    if not name or not raw:
        raise argparse.ArgumentTypeError("expected NAME=PATH or PATH")
    return name, Path(raw)


def verify_xanim(path: Path, expected_name: str | None = None) -> tuple[dict, str]:
    doc = load_json(path)
    if doc.get("format") != "t6-xanim-normalized-v1":
        raise ValueError(f"{path}: unsupported XAnim format {doc.get('format')!r}")
    name = expected_name or str(doc.get("name") or path.stem)
    return doc, name


def dependency_sidecar(path: Path, *, kind: str) -> dict:
    doc = load_json(path)
    return {
        "kind": kind,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
        "declaredFormat": doc.get("format"),
        "embeddedInBundle": False,
        "policy": "reference-only; exact dependency sidecar is not rewritten",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expanded", type=Path)
    ap.add_argument("--asset-start", required=True, type=lambda x: int(x, 0))
    ap.add_argument("--xasset-index", type=int)
    ap.add_argument("--name")
    ap.add_argument("--xanim", action="append", default=[], type=parse_named_path,
                    help="repeatable normalized XAnim as NAME=PATH or PATH")
    ap.add_argument("--material-manifest", action="append", default=[], type=Path)
    ap.add_argument("--image-manifest", action="append", default=[], type=Path)
    ap.add_argument("--lod", type=int, default=0)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    expanded = args.expanded.resolve()
    if not expanded.is_file():
        raise FileNotFoundError(expanded)
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    stem = safe_name(args.name or f"xmodel_{args.asset_start:08x}")
    mesh = out / f"{stem}.mesh.json"
    skeleton = out / f"{stem}.skeleton.json"
    bind_gltf = out / f"{stem}.bind.gltf"

    py = sys.executable
    mesh_tool = repo / "tools" / "t6_xmodel_mesh_normalize_v1.py"
    skeleton_tool = repo / "tools" / "t6_xmodel_skeleton_normalize_v2.py"
    export_tool = repo / "tools" / "t6_xanim_skinned_gltf_export_v7.py"
    for tool in (mesh_tool, skeleton_tool, export_tool):
        if not tool.is_file():
            raise FileNotFoundError(tool)

    run([py, str(mesh_tool), str(expanded), "--asset-start", hex(args.asset_start),
         "--out", str(mesh)], cwd=repo)

    skel_cmd = [py, str(skeleton_tool), str(expanded),
                "--asset-start", hex(args.asset_start), "--out", str(skeleton)]
    if args.xasset_index is not None:
        skel_cmd += ["--xasset-index", str(args.xasset_index)]
    if args.name:
        skel_cmd += ["--name", args.name]
    run(skel_cmd, cwd=repo)

    mesh_doc = load_json(mesh)
    skeleton_doc = load_json(skeleton)
    mesh_name = mesh_doc.get("identity", {}).get("name")
    skel_name = skeleton_doc.get("identity", {}).get("name")
    if args.name is None and mesh_name != skel_name:
        raise RuntimeError(f"mesh/skeleton identity mismatch before export: {mesh_name!r} != {skel_name!r}")

    run([py, str(export_tool), str(mesh), str(skeleton), str(bind_gltf),
         "--lod", str(args.lod)], cwd=repo)

    outputs = [
        artifact(mesh, root=out, kind="normalized-mesh", format_name=mesh_doc.get("format")),
        artifact(skeleton, root=out, kind="normalized-skeleton", format_name=skeleton_doc.get("format")),
        artifact(bind_gltf, root=out, kind="bind-pose-gltf", format_name="gltf-2.0"),
    ]

    animations = []
    used_names: set[str] = set()
    for requested_name, xanim_path in args.xanim:
        xanim_path = xanim_path.resolve()
        xanim_doc, anim_name = verify_xanim(xanim_path, requested_name)
        base = safe_name(anim_name)
        unique = base
        i = 2
        while unique in used_names:
            unique = f"{base}_{i}"
            i += 1
        used_names.add(unique)
        gltf = out / f"{stem}.{unique}.gltf"
        run([py, str(export_tool), str(mesh), str(skeleton), str(gltf),
             "--xanim", str(xanim_path), "--lod", str(args.lod)], cwd=repo)
        out_row = artifact(gltf, root=out, kind="animated-gltf", format_name="gltf-2.0")
        outputs.append(out_row)
        animations.append({
            "name": anim_name,
            "source": {
                "path": str(xanim_path),
                "bytes": xanim_path.stat().st_size,
                "sha256": sha256_path(xanim_path),
                "format": xanim_doc.get("format"),
            },
            "output": out_row,
        })

    deps = []
    deps.extend(dependency_sidecar(p.resolve(), kind="material-manifest")
                for p in args.material_manifest)
    deps.extend(dependency_sidecar(p.resolve(), kind="image-manifest")
                for p in args.image_manifest)

    mesh_vertices = sum(int(s.get("vertCount", 0)) for s in mesh_doc.get("surfaces", []))
    mesh_triangles = sum(int(s.get("triCount", 0)) for s in mesh_doc.get("surfaces", []))
    bones = skeleton_doc.get("skeleton", {}).get("bones", [])

    manifest = {
        "format": FORMAT,
        "policy": {
            "failClosed": True,
            "noFallbackGeometry": True,
            "noFallbackSkeleton": True,
            "noFallbackAnimation": True,
            "noFallbackMaterialsOrImages": True,
            "materialsAndImagesRemainIndependentProofBackedDependencies": True,
        },
        "source": {
            "expandedPath": str(expanded),
            "expandedBytes": expanded.stat().st_size,
            "expandedSha256": sha256_path(expanded),
            "xmodelAssetStart": args.asset_start,
            "xmodelAssetStartHex": f"0x{args.asset_start:08X}",
            "xassetIndex": args.xasset_index,
            "requestedName": args.name,
        },
        "identity": {
            "meshName": mesh_name,
            "skeletonName": skel_name,
        },
        "summary": {
            "lod": args.lod,
            "surfaces": len(mesh_doc.get("surfaces", [])),
            "vertices": mesh_vertices,
            "triangles": mesh_triangles,
            "bones": len(bones),
            "animations": len(animations),
            "dependencySidecars": len(deps),
        },
        "toolchain": [
            "tools/t6_xmodel_mesh_normalize_v1.py",
            "tools/t6_xmodel_skeleton_normalize_v2.py",
            "tools/t6_xanim_skinned_gltf_export_v7.py",
        ],
        "outputs": outputs,
        "animations": animations,
        "dependencySidecars": deps,
    }
    manifest_path = out / f"{stem}.bundle.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = {
        "bundle": str(manifest_path),
        "bundleSha256": sha256_path(manifest_path),
        **manifest["summary"],
        "identity": manifest["identity"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
