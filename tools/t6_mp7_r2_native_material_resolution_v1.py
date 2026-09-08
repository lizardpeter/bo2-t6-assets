#!/usr/bin/env python3
"""Join raw T6 XModel Material handles to pinned-OAT post-loader GLB material names.

The raw side proves whether each XModel surface Material* is FOLLOWING/INSERT-owned
or a packed block/offset alias. The native side is produced only after the
pinned T6 loader has executed AddPointerLookup/ConvertOffsetToPointerLookup.
Direct surfaces are used as an order-preserving canary: every direct raw
Material name must match the material name on the same native GLB primitive
before any packed surface identity is accepted.

This closes the resolved Material identity of a packed handle. It deliberately
does not claim which earlier AddPointerLookup slot originally registered that
packed block/offset; that separate origin-slot ownership proof remains a
stronger provenance layer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

RAW_FORMAT = "t6-mp7-r2-material-handle-probe-v1"
TARGETS = (
    ("t6_wpn_smg_mp7_view", "common_mp", 8),
    ("t6_attach_mag_mp7_view", "common_mp", 3),
    ("c_usa_mp_seal6_shortsleeve_viewhands", "faction_seals_mp", 5),
)
EXPECTED_PACKED = {
    ("t6_attach_mag_mp7_view", 0): (5, 16930796),
    ("t6_attach_mag_mp7_view", 2): (5, 16930816),
    ("c_usa_mp_seal6_shortsleeve_viewhands", 2): (5, 4554964),
    ("c_usa_mp_seal6_shortsleeve_viewhands", 3): (5, 1960952),
    ("c_usa_mp_seal6_shortsleeve_viewhands", 4): (5, 1960956),
}
EXPECTED_RESOLVED = {
    ("c_usa_mp_seal6_shortsleeve_viewhands", 2): "mc/mtl_viewarm_usa_mp_seal6_skin",
    ("c_usa_mp_seal6_shortsleeve_viewhands", 3): "mc/mtl_viewarm_gen_datapad",
    ("c_usa_mp_seal6_shortsleeve_viewhands", 4): "mc/mtl_viewarm_watchglass",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_glb_json(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"short GLB: {path}")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError(f"invalid GLB header: {path}")
    length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError(f"first GLB chunk is not JSON: {path}")
    raw = data[20:20 + length].rstrip(b" \t\r\n\0")
    return json.loads(raw.decode("utf-8"))


def native_surface_materials(path: Path, expected_count: int) -> list[str]:
    doc = load_glb_json(path)
    materials = doc.get("materials") or []
    meshes = doc.get("meshes") or []
    rows: list[str] = []
    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives") or []
        if len(primitives) != 1:
            raise ValueError(
                f"{path}: mesh {mesh_index} has {len(primitives)} primitives; "
                "surface-order mapping is not one-mesh/one-primitive"
            )
        material_index = primitives[0].get("material")
        if not isinstance(material_index, int) or not 0 <= material_index < len(materials):
            raise ValueError(f"{path}: mesh {mesh_index} has invalid material index {material_index!r}")
        name = materials[material_index].get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{path}: mesh {mesh_index} material has no name")
        rows.append(name)
    if len(rows) != expected_count:
        raise ValueError(f"{path}: native surface count {len(rows)} != {expected_count}")
    return rows


def find_raw_model(raw: dict[str, Any], name: str) -> dict[str, Any]:
    for row in raw.get("targets", []):
        if row.get("name") == name:
            return row
    for row in raw.get("models", []):
        if row.get("modelName") == name:
            return row
    raise ValueError(f"raw material probe missing model {name!r}")


def raw_surface_rows(raw_model: dict[str, Any], expected_count: int) -> list[dict[str, Any]]:
    rows = raw_model.get("surfaceMaterials")
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise ValueError(
            f"{raw_model.get('name')!r}: raw surfaceMaterials count "
            f"{len(rows) if isinstance(rows, list) else None} != {expected_count}"
        )
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("surface") != index:
            raise ValueError(
                f"{raw_model.get('name')!r}: raw surface row {index} is not exact index-preserving data"
            )
        if not isinstance(row.get("handle"), dict):
            raise ValueError(f"{raw_model.get('name')!r} surface {index}: missing raw handle")
    return rows


def direct_name(surface_row: dict[str, Any]) -> str | None:
    direct = surface_row.get("directMaterial")
    if direct is None:
        return None
    if not isinstance(direct, dict):
        raise ValueError("directMaterial is not an object")
    name = direct.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("directMaterial has no exact consumed name")
    return name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-probe", required=True)
    ap.add_argument("--common-dir", required=True)
    ap.add_argument("--faction-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw_path = Path(args.raw_probe)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw.get("format") != RAW_FORMAT:
        raise ValueError(f"raw probe format drift {raw.get('format')!r} != {RAW_FORMAT!r}")
    summary = raw.get("summary") or {}
    if (
        summary.get("targetCount") != 3
        or summary.get("surfaceCount") != 16
        or summary.get("directMaterialNameCount") != 11
        or summary.get("packedHandleCount") != 5
        or summary.get("blockerCount") != 0
    ):
        raise ValueError(f"raw probe summary drift: {summary}")

    dirs = {
        "common_mp": Path(args.common_dir),
        "faction_seals_mp": Path(args.faction_dir),
    }

    result_models: list[dict[str, Any]] = []
    direct_canaries = 0
    packed_rows: list[dict[str, Any]] = []
    packed_seen: set[tuple[str, int]] = set()

    for name, zone, expected_count in TARGETS:
        glb = dirs[zone] / "model_export" / f"{name}_lod0.glb"
        if not glb.is_file():
            raise ValueError(f"native OAT GLB missing: {glb}")
        native = native_surface_materials(glb, expected_count)
        raw_model = find_raw_model(raw, name)
        rows = raw_surface_rows(raw_model, expected_count)

        surfaces: list[dict[str, Any]] = []
        for index, (surface_row, resolved_name) in enumerate(zip(rows, native)):
            handle = surface_row["handle"]
            kind = str(handle.get("kind") or "")
            raw_name = direct_name(surface_row)
            row: dict[str, Any] = {
                "surfaceIndex": index,
                "rawPointer": handle,
                "rawInlineName": raw_name,
                "nativeResolvedMaterial": resolved_name,
            }
            key = (name, index)

            if kind == "packed":
                if raw_name is not None:
                    raise ValueError(f"{name} surface {index}: packed handle unexpectedly consumed direct Material")
                expected = EXPECTED_PACKED.get(key)
                if expected is None:
                    raise ValueError(f"unexpected packed surface {name} surface {index}")
                block = handle.get("block")
                offset = handle.get("offset")
                if (block, offset) != expected:
                    raise ValueError(
                        f"{name} surface {index}: packed address drift {(block, offset)} != {expected}"
                    )
                expected_name = EXPECTED_RESOLVED.get(key)
                if expected_name is not None and resolved_name != expected_name:
                    raise ValueError(
                        f"{name} surface {index}: retained native material drift "
                        f"{resolved_name!r} != {expected_name!r}"
                    )
                row["classification"] = "packed_raw_native_postloader_resolved_exact"
                row["packedBlock"] = block
                row["packedOffset"] = offset
                packed_rows.append({
                    "modelName": name,
                    "surfaceIndex": index,
                    "block": block,
                    "offset": offset,
                    "nativeResolvedMaterial": resolved_name,
                })
                packed_seen.add(key)
            else:
                if kind not in ("following", "insert"):
                    raise ValueError(f"{name} surface {index}: unsupported direct handle kind {kind!r}")
                if key in EXPECTED_PACKED:
                    raise ValueError(f"{name} surface {index}: expected packed handle became {kind!r}")
                if raw_name is None:
                    raise ValueError(f"{name} surface {index}: direct raw Material has no consumed name")
                if raw_name != resolved_name:
                    raise ValueError(
                        f"{name} surface {index}: native order/material canary mismatch: "
                        f"raw={raw_name!r}, native={resolved_name!r}"
                    )
                row["classification"] = "direct_raw_and_native_exact"
                direct_canaries += 1
            surfaces.append(row)

        result_models.append({
            "modelName": name,
            "zone": zone,
            "nativeGlb": str(glb),
            "nativeGlbSha256": sha256(glb),
            "surfaceCount": expected_count,
            "surfaces": surfaces,
        })

    if direct_canaries != 11:
        raise ValueError(f"direct raw/native canary count {direct_canaries} != 11")
    if len(packed_rows) != 5 or packed_seen != set(EXPECTED_PACKED):
        raise ValueError(
            f"packed raw/native resolution set drift: count={len(packed_rows)} "
            f"seen={sorted(packed_seen)} expected={sorted(EXPECTED_PACKED)}"
        )

    out = {
        "schema": "t6_mp7_r2_native_material_resolution_v1",
        "authority": {
            "raw": "exact_current_r2_expanded_xmodel_material_handles",
            "native": "pinned_oat_postloader_xmodel_glb_material_resolution",
            "oatCommit": "9dca965366541504b71fa8cfb7ac049cb9b717e1",
            "surfaceOrderCanary": "all_11_direct_raw_material_names_match_native_glb_primitives_at_same_surface_index",
        },
        "rawProbe": {
            "path": str(raw_path),
            "sha256": sha256(raw_path),
        },
        "models": result_models,
        "summary": {
            "surfaceCount": 16,
            "directCanaryMatches": direct_canaries,
            "packedNativeResolutions": len(packed_rows),
            "packedResolved": packed_rows,
        },
        "proofBoundary": {
            "materialIdentityClosed": True,
            "packedOriginAddPointerLookupSlotOwnershipClosed": False,
            "note": (
                "The native T6 loader has authoritatively resolved each packed handle to its Material identity, "
                "with all direct surfaces validating primitive/surface order. This manifest does not yet claim "
                "which earlier AddPointerLookup slot registered each packed block/offset."
            ),
        },
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PASS native Material resolution: 16 surfaces, 11 direct canaries, 5 packed identities")
    for row in packed_rows:
        print(
            f"  {row['modelName']} s{row['surfaceIndex']}: "
            f"block {row['block']} offset {row['offset']} -> {row['nativeResolvedMaterial']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
