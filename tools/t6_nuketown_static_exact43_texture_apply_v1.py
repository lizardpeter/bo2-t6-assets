#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_INPUT_SHA256 = "bc8f0c14518ccd15fabcdc0dd283dbecea410e0383c5057e4036ad1e95d8835b"
EXPECTED_MATERIALS = 344
EXPECTED_MESHES = 297
EXPECTED_INSTANCES = 1943
EXPECTED_BINDINGS = 41
EXPECTED_COLORS = 28
EXPECTED_NORMALS = 13
EXPECTED_UNIQUE_IMAGES = 30


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_glb(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"{path}: truncated GLB")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError(f"{path}: invalid GLB header")
    off = 12
    root = None
    bin_chunk = None
    while off < len(data):
        length, kind = struct.unpack_from("<I4s", data, off)
        off += 8
        chunk = data[off:off + length]
        off += length
        if kind == b"JSON":
            root = json.loads(chunk.rstrip(b" \0"))
        elif kind == b"BIN\0":
            if bin_chunk is not None:
                raise ValueError("multiple BIN chunks")
            bin_chunk = bytes(chunk)
    if root is None or bin_chunk is None:
        raise ValueError("expected one JSON and one BIN chunk")
    return root, bin_chunk


def write_glb(path: Path, root: dict, binbuf: bytearray) -> None:
    while len(binbuf) % 4:
        binbuf.append(0)
    root = copy.deepcopy(root)
    root["buffers"] = [{"byteLength": len(binbuf)}]
    jb = json.dumps(root, separators=(",", ":"), ensure_ascii=False).encode()
    while len(jb) % 4:
        jb += b" "
    out = bytearray(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(jb) + 8 + len(binbuf)))
    out += struct.pack("<I4s", len(jb), b"JSON") + jb
    out += struct.pack("<I4s", len(binbuf), b"BIN\0") + binbuf
    path.write_bytes(out)


def sampler_key(flags: int) -> tuple[bool, bool]:
    # Preserve the same T6 IWI wrapping interpretation already used by the
    # exact texture recovery stack: 0x40 clamps S, 0x80 clamps T.
    return bool(flags & 0x40), bool(flags & 0x80)


def build(
    in_glb: Path,
    role_plan_path: Path,
    exact43_report_path: Path,
    payload_dir: Path,
    out_glb: Path,
    manifest_path: Path,
    expected_input_sha: str = EXPECTED_INPUT_SHA256,
) -> dict:
    if sha256_file(in_glb) != expected_input_sha:
        raise ValueError(f"input GLB is not the authoritative static reconstruction: {sha256_file(in_glb)}")

    plan = json.loads(role_plan_path.read_text())
    report = json.loads(exact43_report_path.read_text())
    root, original_bin = read_glb(in_glb)
    before = copy.deepcopy(root)

    materials = root.get("materials", [])
    meshes = root.get("meshes", [])
    mesh_nodes = [n for n in root.get("nodes", []) if "mesh" in n]
    if len(materials) != EXPECTED_MATERIALS:
        raise ValueError(f"materials {len(materials)} != {EXPECTED_MATERIALS}")
    if len(meshes) != EXPECTED_MESHES:
        raise ValueError(f"meshes {len(meshes)} != {EXPECTED_MESHES}")
    if len(mesh_nodes) != EXPECTED_INSTANCES:
        raise ValueError(f"mesh instances {len(mesh_nodes)} != {EXPECTED_INSTANCES}")
    if root.get("images") or root.get("textures") or root.get("samplers"):
        raise ValueError("authoritative input unexpectedly already contains texture/image/sampler objects")

    bindings = list(plan.get("baseIpakExact43Bindings") or [])
    if len(bindings) != EXPECTED_BINDINGS:
        raise ValueError(f"exact43 plan bindings {len(bindings)} != {EXPECTED_BINDINGS}")
    colors = sum(r.get("gltfRole") == "baseColorTexture" for r in bindings)
    normals = sum(r.get("gltfRole") == "normalTexture" for r in bindings)
    if (colors, normals) != (EXPECTED_COLORS, EXPECTED_NORMALS):
        raise ValueError(f"exact43 role counts {(colors, normals)} != {(EXPECTED_COLORS, EXPECTED_NORMALS)}")
    if len({(r["material"], r["gltfRole"]) for r in bindings}) != len(bindings):
        raise ValueError("duplicate material/role binding in exact43 plan")

    exact_rows = {r["name"]: r for r in report.get("rows", []) if r.get("status") == "validated"}
    if len(exact_rows) != 43:
        raise ValueError(f"validated exact43 report identities {len(exact_rows)} != 43")
    needed_images = sorted({r["image"] for r in bindings})
    if len(needed_images) != EXPECTED_UNIQUE_IMAGES:
        raise ValueError(f"needed exact43 images {len(needed_images)} != {EXPECTED_UNIQUE_IMAGES}")
    missing = [n for n in needed_images if n not in exact_rows]
    if missing:
        raise ValueError(f"role plan references images absent from exact43 report: {missing}")

    material_index = {m.get("name"): i for i, m in enumerate(materials)}
    if len(material_index) != len(materials):
        raise ValueError("material names are not unique")

    images = root.setdefault("images", [])
    textures = root.setdefault("textures", [])
    samplers = root.setdefault("samplers", [])
    buffer_views = root.setdefault("bufferViews", [])
    original_bv_count = len(buffer_views)
    binbuf = bytearray(original_bin)
    texture_by_image: dict[str, int] = {}
    sampler_cache: dict[tuple[bool, bool], int] = {}
    embedded_images: list[dict] = []

    for image_name in needed_images:
        row = exact_rows[image_name]
        png_file = row.get("pngFile")
        if not png_file:
            raise ValueError(f"{image_name}: exact43 report lacks pngFile")
        png_path = payload_dir / png_file
        if not png_path.is_file():
            raise FileNotFoundError(png_path)
        png = png_path.read_bytes()
        if len(png) != int(row["pngBytes"]):
            raise ValueError(f"{image_name}: PNG byte count mismatch")
        if sha256_bytes(png) != row["pngSha256"]:
            raise ValueError(f"{image_name}: PNG SHA mismatch")

        while len(binbuf) % 4:
            binbuf.append(0)
        offset = len(binbuf)
        binbuf.extend(png)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(png),
                "name": f"T6_{image_name}_base_ipak_exact43_PNG",
            }
        )
        bvi = len(buffer_views) - 1
        images.append(
            {
                "name": image_name,
                "bufferView": bvi,
                "mimeType": "image/png",
                "extras": {
                    "T6": {
                        "source": "base.ipak",
                        "identityResolution": "exact-nameHash+dataHash",
                        "nameHash": row["hash"],
                        "dataHash": row["dataHash"],
                        "iwiSha256": row["iwiSha256"],
                        "pngSha256": row["pngSha256"],
                        "crc29Validated": bool(row["crc29Validated"]),
                        "iwi27Validated": bool(row["iwi27Validated"]),
                        "dimensionsValidated": bool(row["dimensionsValidated"]),
                        "width": row["width"],
                        "height": row["height"],
                        "depth": row["depth"],
                        "skipCommandCount": row.get("skipCommandCount", 0),
                    }
                },
            }
        )
        image_index = len(images) - 1
        key = sampler_key(int(row["flags"]))
        if key not in sampler_cache:
            samplers.append(
                {
                    "magFilter": 9729,
                    "minFilter": 9987,
                    "wrapS": 33071 if key[0] else 10497,
                    "wrapT": 33071 if key[1] else 10497,
                }
            )
            sampler_cache[key] = len(samplers) - 1
        textures.append(
            {
                "name": image_name,
                "sampler": sampler_cache[key],
                "source": image_index,
            }
        )
        texture_by_image[image_name] = len(textures) - 1
        embedded_images.append(
            {
                "image": image_name,
                "textureIndex": texture_by_image[image_name],
                "nameHash": row["hash"],
                "dataHash": row["dataHash"],
                "iwiSha256": row["iwiSha256"],
                "pngSha256": row["pngSha256"],
                "pngBytes": row["pngBytes"],
            }
        )

    promotions: list[dict] = []
    for binding in bindings:
        material_name = binding["material"]
        if material_name not in material_index:
            raise ValueError(f"binding references absent material {material_name}")
        image_name = binding["image"]
        row = exact_rows[image_name]
        if int(binding["aliasHash"]) != int(row["hash"]):
            raise ValueError(f"{material_name}: role-plan/image nameHash mismatch")
        if int(binding["aliasDataHash"]) != int(row["dataHash"]):
            raise ValueError(f"{material_name}: role-plan/image dataHash mismatch")
        material = materials[material_index[material_name]]
        texture_index = texture_by_image[image_name]
        role = binding["gltfRole"]
        if role == "baseColorTexture":
            pbr = material.setdefault("pbrMetallicRoughness", {})
            if pbr.get("baseColorTexture") is not None:
                raise ValueError(f"{material_name}: baseColorTexture already present")
            pbr["baseColorTexture"] = {"index": texture_index, "texCoord": 0}
            pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
            kind = "color"
        elif role == "normalTexture":
            if material.get("normalTexture") is not None:
                raise ValueError(f"{material_name}: normalTexture already present")
            material["normalTexture"] = {"index": texture_index, "texCoord": 0, "scale": 1.0}
            kind = "normal"
        else:
            raise ValueError(f"unsupported glTF role {role}")

        proof_row = {
            "kind": kind,
            "gltfRole": role,
            "image": image_name,
            "semantic": binding["rawSemantic"],
            "retailTextureIndex": binding["textureIndex"],
            "sourceContainer": "base.ipak",
            "identityResolution": "exact-nameHash+dataHash",
            "nameHash": row["hash"],
            "dataHash": row["dataHash"],
            "iwiSha256": row["iwiSha256"],
            "pngSha256": row["pngSha256"],
        }
        material.setdefault("extras", {}).setdefault("T6", {}).setdefault("realTextureBindings", []).append(proof_row)
        promotions.append({"materialIndex": material_index[material_name], "material": material_name, **proof_row, "textureIndex": texture_index})

    root.setdefault("extras", {}).setdefault("T6", {})["baseIpakExact43TextureApplyV1"] = {
        "promotionCount": len(promotions),
        "colorPromotions": colors,
        "normalPromotions": normals,
        "uniqueEmbeddedImages": len(needed_images),
        "proofBoundary": (
            "Bindings are only the exact first-semantic role-plan rows whose image identities are among the "
            "43 base.ipak payloads independently validated by exact nameHash+dataHash, CRC29, IWI27 parse and "
            "dimensions. No filename role inference, same-name fallback, or later-slot substitution is allowed."
        ),
    }

    # Geometry and placement data must be byte-for-byte/logically untouched.
    if root["nodes"] != before["nodes"]:
        raise ValueError("node/placement data changed during texture application")
    if root["meshes"] != before["meshes"]:
        raise ValueError("mesh/primitive data changed during texture application")
    if root["accessors"] != before["accessors"]:
        raise ValueError("accessors changed during texture application")
    if root["bufferViews"][:original_bv_count] != before["bufferViews"]:
        raise ValueError("pre-existing bufferViews changed during texture application")
    if bytes(binbuf[:len(original_bin)]) != original_bin:
        raise ValueError("original geometry BIN prefix changed during texture application")
    if [m.get("name") for m in materials] != [m.get("name") for m in before["materials"]]:
        raise ValueError("material identity/order changed during texture application")

    write_glb(out_glb, root, binbuf)
    check, check_bin = read_glb(out_glb)
    if check["nodes"] != before["nodes"] or check["meshes"] != before["meshes"] or check["accessors"] != before["accessors"]:
        raise ValueError("emitted GLB geometry/placement regression")
    if check_bin[:len(original_bin)] != original_bin:
        raise ValueError("emitted GLB original BIN prefix regression")
    if len(check.get("images", [])) != EXPECTED_UNIQUE_IMAGES or len(check.get("textures", [])) != EXPECTED_UNIQUE_IMAGES:
        raise ValueError("emitted exact image/texture count regression")

    manifest = {
        "format": "t6-nuketown-static-exact43-texture-apply-v1",
        "inputGlb": {"file": in_glb.name, "bytes": in_glb.stat().st_size, "sha256": sha256_file(in_glb)},
        "rolePlan": {"file": role_plan_path.name, "sha256": sha256_file(role_plan_path)},
        "exact43Report": {"file": exact43_report_path.name, "sha256": sha256_file(exact43_report_path)},
        "summary": {
            "promotionCount": len(promotions),
            "colorPromotions": colors,
            "normalPromotions": normals,
            "uniqueImageCount": len(needed_images),
            "materialCount": len(materials),
            "meshDefinitions": len(meshes),
            "meshInstances": len(mesh_nodes),
        },
        "embeddedImages": embedded_images,
        "promotions": promotions,
        "validation": {
            "authoritativeInputSha": "pass",
            "nodePlacementIdentity": "pass",
            "meshPrimitiveIdentity": "pass",
            "accessorIdentity": "pass",
            "preexistingBufferViewIdentity": "pass",
            "originalBinPrefixIdentity": "pass",
            "materialNameOrderIdentity": "pass",
            "allPayloadPngSha256": "pass",
            "allRolePlanNameDataHashPairs": "pass",
            "sameNameFallbacks": 0,
            "filenameRoleInference": 0,
            "laterSlotSubstitutions": 0,
        },
        "outputGlb": {"file": out_glb.name, "bytes": out_glb.stat().st_size, "sha256": sha256_file(out_glb)},
        "proofBoundary": (
            "This pass changes only glTF material texture bindings plus appended exact PNG image payloads/samplers. "
            "All authoritative 1943 placements and geometry structures are required to remain identical, and the "
            "original BIN chunk must remain an exact prefix of the output BIN."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", type=Path, required=True)
    ap.add_argument("--role-plan", type=Path, required=True)
    ap.add_argument("--exact43-report", type=Path, required=True)
    ap.add_argument("--payload-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--expected-input-sha", default=EXPECTED_INPUT_SHA256)
    args = ap.parse_args()
    result = build(
        args.glb,
        args.role_plan,
        args.exact43_report,
        args.payload_dir,
        args.out,
        args.manifest,
        args.expected_input_sha,
    )
    print(json.dumps({"summary": result["summary"], "outputGlb": result["outputGlb"], "validation": result["validation"]}, indent=2))


if __name__ == "__main__":
    main()
