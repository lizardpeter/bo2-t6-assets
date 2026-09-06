#!/usr/bin/env python3
"""Strict exact T6 character material binding compiler.

For generic decoded MaterialTextureDef manifests this remains a strict frontend to
binding-plan v1 and validates every packed Material* by either runtime-loader or
serialized-XFile replay.

SEAL6 has a later, stronger retained proof chain whose final image inventory is
`t6-seal6-smg-texture-keys-v4`: all 44 MaterialTextureDef uses are already joined
to exact retail image identities.  Older builders still pass the predecessor v2
inventory in --materials.  When that input is detected, this frontend consumes
v4 directly, cross-checks the independently retained LOD0 visualization proof,
exact stream-key set, strict serialized surface-owner replay and normalized LOD
bounds, and emits the same binding-plan-v1 interoperability schema.  It never
fabricates slot hashes/sampler bytes that are absent from the resolved inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "t6_character_material_binding_plan_v1.py"
REPLAY_PATH = HERE / "t6_material_pointer_replay_v1.py"
SERIALIZED_REPLAY_PATH = HERE / "t6_serialized_xfile_pointer_replay_v1.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = _load_module("t6_character_material_binding_plan_v1", BASE_PATH)
replay = _load_module("t6_material_pointer_replay_v1", REPLAY_PATH)
serialized_replay = _load_module("t6_serialized_xfile_pointer_replay_v1", SERIALIZED_REPLAY_PATH)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def u32(v) -> int:
    return int(v, 0) if isinstance(v, str) else int(v)


def norm_mat(s: str) -> str:
    return s[1:] if s.startswith(",") else s


def adapt_surface_assignment_doc(doc: dict, *, allow_synthetic: bool = False) -> dict:
    if doc.get("format") != "t6-xmodel-surface-material-assignments-v1":
        return doc
    rows = doc.get("assignments")
    if not isinstance(rows, list):
        raise RuntimeError("surface assignment manifest lacks assignments[]")
    expected = int((doc.get("summary") or {}).get("surfaces", len(rows)))
    if len(rows) != expected:
        raise RuntimeError(f"surface assignment row count {len(rows)} != expected {expected}")
    if [int(r["surfaceIndex"]) for r in rows] != list(range(expected)):
        raise RuntimeError("surface assignment indices are not exact contiguous 0..N-1")

    legacy = []
    inline_count = runtime_count = serialized_count = backrefs = 0
    for r in rows:
        token = replay.u32(r["handleRaw"])
        derived = None
        if r.get("handleKind") == "inline-following":
            if token not in replay.INLINE_SENTINELS:
                raise RuntimeError(f"surface {r['surfaceIndex']}: bad inline token 0x{token:08x}")
            evidence = "exact-inline-retail-material"
            inline_count += 1
        elif "serializedReplay" in r:
            result = serialized_replay.validate_serialized_material_replay(r)
            if not result.exact:
                raise RuntimeError(f"surface {r['surfaceIndex']}: non-exact serialized Material replay: {result.reason}")
            evidence = "exact-packed-virtual-material-owner-serialized-xfile-replay"
            serialized_count += 1
            proof = r.get("serializedReplay") or {}
            backrefs += int(bool(proof.get("sameOwnerBackreference", False)))
            derived = {"mode":"serialized-xfile","blockIndex":result.block_index,"resolvedTargetPointerSlotVirtual":result.block_offset,"ownerModel":result.owner_model,"ownerSlotIndex":result.owner_slot_index,"ownerMaterialRawStart":result.owner_material_raw_start}
        else:
            result = replay.validate_packed_loader_replay(r, allow_synthetic=allow_synthetic)
            if not result.exact:
                raise RuntimeError(f"surface {r['surfaceIndex']}: non-exact runtime Material replay: {result.reason}")
            evidence = "exact-packed-virtual-material-owner-loader-replay"
            runtime_count += 1
            proof = r.get("loaderReplay") or {}
            backrefs += int(bool(proof.get("sameOwnerBackreference", False)))
            derived = {"mode":"runtime-loader","decodedPointer":result.decoded_pointer,"resolvedTargetPointerSlotVirtual":result.target_pointer_slot_virtual,"objectVirtual":result.object_virtual}
        out = {"surfaceIndex":int(r["surfaceIndex"]),"lod":int(r["lodIndex"]),"lodLocalSurfaceIndex":int(r["lodLocalSurfaceIndex"]),"materialName":r["material"],"materialPointerRaw":r["handleRaw"],"evidence":evidence}
        if derived is not None:
            out["pointerReplay"] = derived
        legacy.append(out)
    packed = runtime_count + serialized_count
    return {"format":"t6-surface-proof-v2-adapted-for-binding-v1","source":doc.get("source"),"bodyMaterials":{"surfaceAssignments":legacy},"adapterProof":{"inputFormat":doc["format"],"inputRows":len(rows),"allSurfaceIndicesContiguous":True,"noIdentityInferencePerformed":True,"inlineSentinelRows":inline_count,"packedRowsExact":packed,"packedRowsExactByRuntimeLoaderReplay":runtime_count,"packedRowsExactBySerializedXFileReplay":serialized_count,"packedRowsSameOwnerBackreferences":backrefs,"runtimeObfuscatedTokensGuessed":0,"serializedTokensGuessed":0}}


def load_with_surface_v2(path: Path):
    return adapt_surface_assignment_doc(load(path))


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materials", type=Path, required=True)
    ap.add_argument("--surface-proof", type=Path, required=True)
    ap.add_argument("--mesh", type=Path, required=True)
    ap.add_argument("--exact-keys", type=Path, required=True)
    ap.add_argument("--header-alias-proof", type=Path, required=True)
    ap.add_argument("--image-run-proof", type=Path, required=True)
    ap.add_argument("--material-alias-proof", type=Path, required=True)
    ap.add_argument("--import-resolution", type=Path, required=True)
    ap.add_argument("--shared-identity-proof", type=Path, required=True)
    ap.add_argument("--lod", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    return ap.parse_args()


def compile_seal6(a: argparse.Namespace) -> int:
    legacy = load(a.materials)
    if legacy.get("format") != "t6-seal6-smg-texture-keys-v2":
        raise RuntimeError("SEAL6 compatibility path selected for unexpected material inventory")
    resolved_path = a.materials.with_name("seal6_smg_texture_keys_v4.json")
    lod0_path = a.materials.with_name("seal6_smg_lod0_material_binding_proof_v2.json")
    resolved = load(resolved_path)
    lod0 = load(lod0_path)
    mesh = load(a.mesh)
    exact_doc = load(a.exact_keys)
    shared = load(a.shared_identity_proof)
    surface = adapt_surface_assignment_doc(load(a.surface_proof))

    if resolved.get("format") != "t6-seal6-smg-texture-keys-v4":
        raise RuntimeError("resolved SEAL6 texture inventory is not v4")
    rs = resolved.get("summary") or {}
    if int(rs.get("bodyMaterials", -1)) != 13 or int(rs.get("materialTextureSlots", -1)) != 44 or int(rs.get("unknownImageIdentities", -1)) != 0:
        raise RuntimeError("resolved SEAL6 material/image closure canary mismatch")
    if lod0.get("format") != "t6-seal6-smg-lod0-material-binding-proof-v2" or not (lod0.get("summary") or {}).get("nativeIdentityClosure"):
        raise RuntimeError("LOD0 exact material binding proof is not closed")
    if mesh.get("format") != "t6-xmodel-mesh-normalized-v1":
        raise RuntimeError(f"unsupported mesh format {mesh.get('format')!r}")
    lodrow = next((x for x in mesh.get("xmodel", {}).get("lods", []) if int(x.get("index", -1)) == a.lod), None)
    if lodrow is None:
        raise RuntimeError(f"LOD{a.lod} absent from mesh")
    lod_start = int(lodrow["surfIndex"]); lod_count = int(lodrow["numSurfs"]); lod_end = lod_start + lod_count

    exact = {}
    for r in exact_doc.get("exactBaseIpakKeys", exact_doc.get("exactStreamKeyImages", [])):
        name = r.get("image") or r.get("name")
        exact[name] = {"nameHash":u32(r.get("nameHash", r.get("nameHashHex"))),"dataHash":u32(r.get("dataHash", r.get("dataHashHex"))) & 0x1fffffff,"repository":r.get("repository"),"width":r.get("width"),"height":r.get("height")}
    if len(exact) != 42:
        raise RuntimeError(f"expected 42 exact stream keys, got {len(exact)}")

    slots_by_mat: dict[str, dict[int, dict]] = {}
    for r in resolved.get("exactBaseIpakKeys", []):
        image = r["image"]
        key = exact.get(image)
        if key is None:
            raise RuntimeError(f"{image}: resolved material image lacks exact stream key")
        for use in r.get("uses", []):
            if not isinstance(use, str):
                raise RuntimeError("resolved SEAL6 use is not canonical material:slot:semantic text")
            material, slot_s, semantic = use.rsplit(":", 2)
            material = norm_mat(material); slot_i = int(slot_s)
            row = {"index":slot_i,"semanticName":semantic,"image":image,"identityEvidence":"exact-resolved-MaterialTextureDef-use-v4","exactStreamKey":key}
            prev = slots_by_mat.setdefault(material, {}).get(slot_i)
            if prev is not None and (prev["image"] != image or prev["semanticName"] != semantic):
                raise RuntimeError(f"{material} slot {slot_i}: conflicting exact resolved uses")
            slots_by_mat[material][slot_i] = row

    alias = shared.get("alias") or {}
    later = shared.get("laterAlias") or alias.get("requiredLaterUse")
    identity = shared.get("resolvedIdentity") or shared.get("exactImageIdentity")
    if not isinstance(later, dict) or not isinstance(identity, str):
        raise RuntimeError("shared radiant identity proof schema missing")
    smat = norm_mat(later["material"]); sidx = int(later["slotIndex"])
    slots_by_mat.setdefault(smat, {})[sidx] = {"index":sidx,"semanticName":"radiantDiffuseMap","image":identity.lstrip(","),"identityEvidence":"exact-shared-radiant-alias-proof","exactStreamKey":None}

    slot_count = sum(len(v) for v in slots_by_mat.values())
    if slot_count != 44 or len(slots_by_mat) != 13:
        raise RuntimeError(f"resolved native use table expected 44 slots / 13 materials; got {slot_count} / {len(slots_by_mat)}")

    lod0_visual = {}
    for r in lod0.get("surfaceBindings", []):
        m = norm_mat(r["material"])
        pair = (r["baseColor"], r["normal"], bool(r.get("shaderApproximation", False)))
        if m in lod0_visual and lod0_visual[m] != pair:
            raise RuntimeError(f"LOD0 proof gives conflicting visualization pairs for {m}")
        lod0_visual[m] = pair

    material_rows = []
    for material in sorted(slots_by_mat):
        slots = [slots_by_mat[material][i] for i in sorted(slots_by_mat[material])]
        colors = [s for s in slots if s["semanticName"] == "colorMap" and s["exactStreamKey"]]
        normals = [s for s in slots if s["semanticName"] == "normalMap" and s["exactStreamKey"]]
        if material in lod0_visual:
            bc_name, nm_name, shader_approx = lod0_visual[material]
            bc = next((s for s in colors if s["image"] == bc_name), None)
            nm = next((s for s in normals if s["image"] == nm_name), None)
            if bc is None or nm is None:
                raise RuntimeError(f"{material}: LOD0 exact visualization proof does not match resolved v4 uses")
            bc_mode = "exact-retained-lod0-material-binding-proof-v2"
            nm_mode = "exact-retained-lod0-material-binding-proof-v2"
        else:
            if len(colors) != 1 or len(normals) != 1:
                raise RuntimeError(f"{material}: non-LOD0 material requires unique exact color/normal uses, got {len(colors)}/{len(normals)}")
            bc, nm = colors[0], normals[0]
            shader_approx = False
            bc_mode = nm_mode = "unique-exact-resolved-MaterialTextureDef-use-v4"
        material_rows.append({"material":material,"sourceMaterialName":material,"textureCount":len(slots),"slots":slots,"nativeSlotStructuralFields":"retained in upstream byte-decoded proof manifests; not synthesized by this adapter","gltfVisualization":{"baseColor":{"image":bc["image"],"mode":bc_mode,"slotIndex":bc["index"],"exactStreamKey":bc["exactStreamKey"]},"normal":{"image":nm["image"],"mode":nm_mode,"slotIndex":nm["index"],"exactStreamKey":nm["exactStreamKey"]},"shaderApproximation":shader_approx}})

    bymat = {m["material"]:m for m in material_rows}
    srows = (surface.get("bodyMaterials") or {}).get("surfaceAssignments")
    if not isinstance(srows, list) or len(srows) < lod_end:
        raise RuntimeError("strict surface proof is incomplete")
    surfaces = []
    for r in srows:
        si = int(r["surfaceIndex"])
        if not (lod_start <= si < lod_end):
            continue
        mat = norm_mat(r["materialName"])
        if mat not in bymat:
            raise RuntimeError(f"surface {si}: exact material {mat} absent from resolved inventory")
        surfaces.append({"surfaceIndex":si,"lod":a.lod,"material":mat,"materialPointerRaw":r.get("materialPointerRaw"),"materialIdentityEvidence":r.get("evidence"),"pointerReplay":r.get("pointerReplay"),"gltfVisualization":bymat[mat]["gltfVisualization"]})
    if [r["surfaceIndex"] for r in surfaces] != list(range(lod_start, lod_end)):
        raise RuntimeError("LOD surface assignments are incomplete or out of order")
    used = sorted({r["material"] for r in surfaces})
    missing = [m for m in used if not bymat[m]["gltfVisualization"]["baseColor"].get("exactStreamKey") or not bymat[m]["gltfVisualization"]["normal"].get("exactStreamKey")]
    if missing:
        raise RuntimeError(f"LOD{a.lod}: exact PBR visualization stream-key closure failed: {missing}")

    source_paths = [a.materials,resolved_path,lod0_path,a.surface_proof,a.mesh,a.exact_keys,a.header_alias_proof,a.image_run_proof,a.material_alias_proof,a.import_resolution,a.shared_identity_proof]
    doc = {"format":"t6-character-material-binding-plan-v1","authority":"exact resolved SEAL6 MaterialTextureDef v4 image-use inventory + exact LOD0 visualization proof + exact serialized XModel Material pointer replay + normalized retail LOD boundaries + exact stream keys; no slot structural fields are fabricated","sourceManifests":[{"path":str(p),"sha256":sha(p)} for p in source_paths],"summary":{"materialTextureSlots":44,"identityResolvedSlots":44,"exactStreamKeySlots":43,"materials":13,"lod":a.lod,"lodSurfIndex":lod_start,"lodSurfaces":len(surfaces),"lodUniqueMaterials":len(used),"visualBindingsMissingExactStreamKey":0,"nativeIdentityClosure":True,"visualPbrTextureClosure":True},"materials":material_rows,"surfaceBindings":surfaces,"missingVisualBindings":[],"proofBoundary":"All native material/image identities and selected glTF color/normal images are exact retail-derived evidence. This adapter deliberately omits MaterialTextureDef structural fields not present in the resolved v4 inventory rather than inferring them; upstream byte-decoded manifests remain authoritative for those fields. The cornea PBR mapping remains explicitly visualization-only."}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    return 0


def main() -> int:
    material_arg = None
    for i, x in enumerate(sys.argv[:-1]):
        if x == "--materials":
            material_arg = Path(sys.argv[i+1]); break
    if material_arg is not None and load(material_arg).get("format") == "t6-seal6-smg-texture-keys-v2":
        return compile_seal6(_args())
    base.load = load_with_surface_v2
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
