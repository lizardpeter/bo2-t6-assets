#!/usr/bin/env python3
"""Apply the retail-proven Nuketown $identitynormalmap to a textured GLB.

The identity is not an IPAK guess. It is admitted only when a proof manifest
closes block 5 / 514620 to the inline 1x1 $identitynormalmap GfxImage and the
material catalog's *first* semantic-5 texture points to that exact address.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
from pathlib import Path
from PIL import Image

EXPECTED_PROOF_FORMAT = "t6-nuketown-identitynormalmap-block5-proof-v1"
EXPECTED_SOURCE_SHA = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
EXPECTED_BLOCK = 5
EXPECTED_OFFSET = 514620
EXPECTED_NAME = "$identitynormalmap"
EXPECTED_RGBA = (0x80, 0x80, 0xFF, 0x80)
SEMANTIC_NORMAL = 5


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_glb(path: Path) -> tuple[dict, bytearray]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("GLB too short")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError("invalid GLB header")
    off = 12
    js = None
    bins = []
    while off < total:
        length, typ = struct.unpack_from("<I4s", data, off)
        off += 8
        chunk = data[off:off + length]
        off += length
        if typ == b"JSON":
            js = json.loads(chunk)
        elif typ == b"BIN\0":
            bins.append(chunk)
    if js is None or len(bins) != 1:
        raise ValueError("expected one JSON and one BIN chunk")
    return js, bytearray(bins[0])


def write_glb(path: Path, js: dict, binbuf: bytearray) -> None:
    while len(binbuf) % 4:
        binbuf.append(0)
    js.setdefault("buffers", [{}])[0]["byteLength"] = len(binbuf)
    jb = json.dumps(js, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    while len(jb) % 4:
        jb += b" "
    total = 12 + 8 + len(jb) + 8 + len(binbuf)
    out = bytearray(struct.pack("<4sII", b"glTF", 2, total))
    out += struct.pack("<I4s", len(jb), b"JSON") + jb
    out += struct.pack("<I4s", len(binbuf), b"BIN\0") + binbuf
    path.write_bytes(out)


def identity_png() -> bytes:
    im = Image.new("RGBA", (1, 1), EXPECTED_RGBA)
    out = io.BytesIO()
    im.save(out, format="PNG", optimize=False)
    return out.getvalue()


def validate_proof(proof: dict) -> None:
    if proof.get("format") != EXPECTED_PROOF_FORMAT or proof.get("status") != "closed":
        raise ValueError("identitynormal proof is not a closed v1 proof")
    source = proof.get("source") or {}
    if source.get("sha256") != EXPECTED_SOURCE_SHA:
        raise ValueError("identitynormal proof source SHA drift")
    promotion = proof.get("promotion") or {}
    expected = {
        "block": EXPECTED_BLOCK,
        "virtualOffset": EXPECTED_OFFSET,
        "image": EXPECTED_NAME,
        "semantic": SEMANTIC_NORMAL,
        "xassetIndex": 836,
    }
    for key, value in expected.items():
        if promotion.get(key) != value:
            raise ValueError(f"identitynormal proof promotion drift: {key}={promotion.get(key)!r}")
    image = proof.get("identityImage") or {}
    if image.get("name") != EXPECTED_NAME or image.get("resourceSize") != 4:
        raise ValueError("identitynormal inline image evidence drift")
    control = proof.get("alignmentControl") or {}
    if control.get("correctSlot1VirtualOffset") != EXPECTED_OFFSET or control.get("deltaBytes") != 16:
        raise ValueError("identitynormal alignment control drift")


def first_normal_texture(material: dict) -> dict | None:
    for texture in material.get("textures", []):
        if texture.get("semantic") == SEMANTIC_NORMAL:
            return texture
    return None


def points_to_identity(texture: dict | None) -> bool:
    if not texture:
        return False
    image = texture.get("image") or {}
    pointer = image.get("pointer") or {}
    return (
        not image.get("inline")
        and pointer.get("kind") == "offset"
        and pointer.get("block") == EXPECTED_BLOCK
        and pointer.get("offset") == EXPECTED_OFFSET
    )


def build(input_glb: Path, materials_path: Path, proof_path: Path, out: Path, manifest_path: Path) -> dict:
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    validate_proof(proof)
    catalog_doc = json.loads(materials_path.read_text(encoding="utf-8"))
    materials = catalog_doc.get("materials")
    if not isinstance(materials, list):
        raise ValueError("material catalog missing materials[]")
    by_name = {m.get("name"): m for m in materials if m.get("name")}

    js, binbuf = read_glb(input_glb)
    glb_materials = js.get("materials") or []
    candidates = []
    for index, glb_material in enumerate(glb_materials):
        name = glb_material.get("name")
        src = by_name.get(name)
        if not src:
            continue
        first = first_normal_texture(src)
        if points_to_identity(first):
            if "normalTexture" in glb_material:
                raise ValueError(f"{name}: identitynormal candidate already has a normalTexture")
            candidates.append((index, glb_material, first))

    if not candidates:
        raise ValueError("no rendered materials use block5/514620 as first normal semantic")

    png = identity_png()
    while len(binbuf) % 4:
        binbuf.append(0)
    image_offset = len(binbuf)
    binbuf.extend(png)

    buffer_views = js.setdefault("bufferViews", [])
    images = js.setdefault("images", [])
    samplers = js.setdefault("samplers", [])
    textures = js.setdefault("textures", [])

    buffer_views.append({
        "buffer": 0,
        "byteOffset": image_offset,
        "byteLength": len(png),
        "name": "T6_$identitynormalmap_PNG",
    })
    buffer_view_index = len(buffer_views) - 1
    images.append({
        "name": EXPECTED_NAME,
        "bufferView": buffer_view_index,
        "mimeType": "image/png",
        "extras": {
            "T6": {
                "source": "mp_nuketown_2020.expanded.bin",
                "sourceSha256": EXPECTED_SOURCE_SHA,
                "identityResolution": "loader-address-proof",
                "block": EXPECTED_BLOCK,
                "virtualOffset": EXPECTED_OFFSET,
                "embeddedPixelRGBA": list(EXPECTED_RGBA),
                "semantic": SEMANTIC_NORMAL,
                "proofManifest": proof_path.name,
            }
        },
    })
    image_index = len(images) - 1
    samplers.append({
        "magFilter": 9729,
        "minFilter": 9987,
        "wrapS": 10497,
        "wrapT": 10497,
    })
    sampler_index = len(samplers) - 1
    textures.append({
        "name": EXPECTED_NAME,
        "sampler": sampler_index,
        "source": image_index,
    })
    texture_index = len(textures) - 1

    promoted = []
    for material_index, glb_material, source_texture in candidates:
        glb_material["normalTexture"] = {"index": texture_index, "texCoord": 0, "scale": 1.0}
        glb_material.setdefault("extras", {}).setdefault("T6", {}).setdefault("realTextureBindings", []).append({
            "kind": "normal",
            "image": EXPECTED_NAME,
            "semantic": SEMANTIC_NORMAL,
            "samplerState": source_texture.get("samplerState"),
            "sourceContainer": "mp_nuketown_2020.expanded.bin",
            "identityResolution": "loader-address-proof:block5/514620",
            "proofManifest": proof_path.name,
        })
        promoted.append({
            "materialIndex": material_index,
            "material": glb_material.get("name"),
            "samplerState": source_texture.get("samplerState"),
        })

    t6 = js.setdefault("extras", {}).setdefault("T6", {})
    prior = t6.get("realTexturePartialV4") or {}
    before_normal = prior.get("normalMaterialBindings")
    if before_normal is None:
        before_normal = sum(1 for m in glb_materials if "normalTexture" in m) - len(promoted)
    before_unique = prior.get("uniqueEmbeddedImages")
    if before_unique is None:
        before_unique = max(0, len(images) - 1)
    t6["realTexturePartialV5"] = {
        **prior,
        "normalMaterialBindings": before_normal + len(promoted),
        "uniqueEmbeddedImages": before_unique + 1,
        "identityNormalPromotions": len(promoted),
        "identityNormalImage": EXPECTED_NAME,
        "identityNormalBlock": EXPECTED_BLOCK,
        "identityNormalVirtualOffset": EXPECTED_OFFSET,
        "identityNormalProofManifest": proof_path.name,
        "proofBoundary": "v4 IPAK bindings plus one retail-proven inline FastFile image: block5/514620 is admitted only by the closed loader-destination replay and only where it is the first retained semantic-5 texture entry.",
    }

    write_glb(out, js, binbuf)
    check_js, check_bin = read_glb(out)
    if check_js["buffers"][0]["byteLength"] != len(check_bin):
        raise ValueError("output GLB buffer byteLength mismatch")
    final_normal_count = sum(1 for m in check_js.get("materials", []) if "normalTexture" in m)
    if final_normal_count != before_normal + len(promoted):
        raise ValueError(f"normal binding count drift: {final_normal_count}")

    manifest = {
        "format": "t6-nuketown-ipak-partial-real-texture-export-v5-identitynormal",
        "inputGlb": {
            "file": input_glb.name,
            "sha256": sha_file(input_glb),
            "bytes": input_glb.stat().st_size,
        },
        "materialCatalog": {
            "file": materials_path.name,
            "sha256": sha_file(materials_path),
            "materialCount": len(materials),
        },
        "identityProof": {
            "file": proof_path.name,
            "sha256": sha_file(proof_path),
            "sourceFastFileSha256": EXPECTED_SOURCE_SHA,
            "block": EXPECTED_BLOCK,
            "virtualOffset": EXPECTED_OFFSET,
            "image": EXPECTED_NAME,
            "embeddedPixelRGBA": list(EXPECTED_RGBA),
        },
        "outputGlb": {
            "file": out.name,
            "sha256": sha_file(out),
            "bytes": out.stat().st_size,
        },
        "summary": {
            "normalBoundMaterialsBefore": before_normal,
            "identityNormalPromotions": len(promoted),
            "normalBoundMaterialsAfter": final_normal_count,
            "uniqueEmbeddedImagesBefore": before_unique,
            "uniqueEmbeddedImagesAfter": before_unique + 1,
            "candidateMaterialReferences": len(promoted),
        },
        "promotedMaterials": promoted,
        "proofBoundary": "No IPAK identity is invented for $identitynormalmap. Its 1x1 normal pixel comes from the pinned expanded FastFile proof, and a material is promoted only when its first retained semantic-5 texture pointer is exactly block5/514620.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", type=Path, required=True)
    ap.add_argument("--materials", type=Path, required=True)
    ap.add_argument("--proof", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()
    manifest = build(args.glb, args.materials, args.proof, args.out, args.manifest)
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))
    print(json.dumps(manifest["outputGlb"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
