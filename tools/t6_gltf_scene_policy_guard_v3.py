#!/usr/bin/env python3
"""Non-regression guard for T6 GLB checkpoints with scene migration support.

This version distinguishes *data loss* from intentional scene reorganization.
Previously proven scene roots may move to another glTF scene (for example,
animation-support XModels moved out of the canonical map scene) as long as they
remain preserved as scene roots somewhere in the document.

Material/texture/geometry coverage floors and structural ceilings remain
fail-closed. v3 baselines may also lock universal full-map integration counts,
retail sky identity, and canonical-scene visibility policy.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

class GuardError(RuntimeError):
    pass

def read_glb(path: Path):
    data = path.read_bytes()
    if len(data) < 20:
        raise GuardError("GLB too short")
    magic, ver, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or ver != 2 or total != len(data):
        raise GuardError("invalid GLB2 header")
    o = 12
    js = None
    bins = []
    while o < total:
        n, t = struct.unpack_from("<I4s", data, o)
        o += 8
        c = data[o:o+n]
        o += n
        if t == b"JSON":
            js = json.loads(c)
        elif t == b"BIN\0":
            bins.append(c)
    if js is None or len(bins) != 1:
        raise GuardError("expected one JSON and one BIN chunk")
    return data, js, bins[0]

def inspect(path: Path):
    data, js, binbuf = read_glb(path)
    mats = js.get("materials", [])
    meshes = js.get("meshes", [])
    nodes = js.get("nodes", [])
    scenes = js.get("scenes", [])
    if not scenes:
        raise GuardError("no scenes")
    active = int(js.get("scene", 0))
    if not 0 <= active < len(scenes):
        raise GuardError("invalid active scene")

    def names_for_roots(roots):
        out = []
        for i in roots:
            if not isinstance(i, int) or not 0 <= i < len(nodes):
                raise GuardError("invalid scene root index")
            out.append(str(nodes[i].get("name") or ""))
        return out

    active_names = names_for_roots(scenes[active].get("nodes", []))
    all_scene_root_names = set()
    for sc in scenes:
        all_scene_root_names.update(names_for_roots(sc.get("nodes", [])))

    used = set()
    generic = 0
    prims = 0
    tris = 0
    bad_mat_refs = 0
    for me in meshes:
        for pr in me.get("primitives", []):
            prims += 1
            mid = pr.get("material")
            if isinstance(mid, int) and 0 <= mid < len(mats):
                used.add(mid)
                if str(mats[mid].get("name") or "").startswith("material_surface_"):
                    generic += 1
            elif mid is not None:
                bad_mat_refs += 1
            ai = pr.get("indices")
            if isinstance(ai, int) and 0 <= ai < len(js.get("accessors", [])):
                tris += int(js["accessors"][ai].get("count", 0)) // 3

    used_names = {str(mats[i].get("name") or "") for i in used}
    base_names = {str(mats[i].get("name") or "") for i in used if (mats[i].get("pbrMetallicRoughness") or {}).get("baseColorTexture") is not None}
    normal_names = {str(mats[i].get("name") or "") for i in used if mats[i].get("normalTexture") is not None}

    images = js.get("images", [])
    textures = js.get("textures", [])
    bvs = js.get("bufferViews", [])
    external = sum(1 for im in images if im.get("uri"))
    invalid_tex = 0
    for t in textures:
        src = t.get("source")
        if not isinstance(src, int) or not 0 <= src < len(images):
            invalid_tex += 1
    invalid_img = 0
    for im in images:
        if im.get("uri"):
            continue
        bv = im.get("bufferView")
        if not isinstance(bv, int) or not 0 <= bv < len(bvs):
            invalid_img += 1
            continue
        v = bvs[bv]
        a = int(v.get("byteOffset", 0))
        z = a + int(v.get("byteLength", 0))
        if a < 0 or z < a or z > len(binbuf):
            invalid_img += 1

    x = (js.get("extras") or {}).get("T6", {})
    full = x.get("fullRetailWorldIntegrationV1") or {}
    sky = x.get("retailSkyboxV1") or {}
    return {
        "file": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "meshCount": len(meshes),
        "sceneCount": len(scenes),
        "sceneRootCount": len(scenes[active].get("nodes", [])),
        "activeSceneName": str(scenes[active].get("name") or ""),
        "activeSceneRootNames": set(active_names),
        "allSceneRootNames": all_scene_root_names,
        "allNodeNames": {str(n.get("name") or "") for n in nodes},
        "usedMaterialCount": len(used),
        "usedMaterialNames": used_names,
        "baseColorBoundUsedMaterialCount": len(base_names),
        "baseColorBoundMaterialNames": base_names,
        "normalBoundUsedMaterialCount": len(normal_names),
        "normalBoundMaterialNames": normal_names,
        "primitiveCount": prims,
        "triangleCount": tris,
        "embeddedImageCount": len(images),
        "genericPrimitiveReferences": generic,
        "badMaterialReferences": bad_mat_refs,
        "externalImageUris": external,
        "invalidTextureSources": invalid_tex,
        "invalidEmbeddedImages": invalid_img,
        "reflectionProxyRemovedCount": (x.get("reflectionProxyFilterV1") or {}).get("reflectionProxyNodesRemovedFromPrimaryScene"),
        "windingFixedTriangleCount": (x.get("triangleWindingFixV1") or {}).get("trianglesFlipped"),
        "retailRenderStateResolvedMaterials": (x.get("retailRenderStateOATV1") or {}).get("materialsResolvedFromRetailState"),
        "fullWorldSurfaceCount": full.get("worldSurfaceCount"),
        "fullWorldVertexCount": full.get("worldVertexCount"),
        "fullWorldTriangleCount": full.get("worldTriangleCount"),
        "staticPlacementCountSerialized": full.get("staticPlacementCountSerialized"),
        "staticPlacementCountPrimary": full.get("staticPlacementCountPrimary"),
        "staticPlacementCountCanonicalVisible": full.get("staticPlacementCountCanonicalVisible"),
        "staticPlacementCountAnimationSupport": full.get("staticPlacementCountAnimationSupport"),
        "staticPlacementCountReflectionProxy": full.get("staticPlacementCountReflectionProxy"),
        "mapEntVisiblePlacementCount": full.get("mapEntVisiblePlacementCount"),
        "retailSkyboxSourceDdsSha256": sky.get("sourceDdsSha256"),
        "retailSkyboxImageName": sky.get("imageName"),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    base = json.loads(a.baseline.read_text())
    c = inspect(a.candidate)
    failures = []

    for k, v in base.get("floors", {}).items():
        if c.get(k) is None or c[k] < v:
            failures.append({"kind": "floor", "field": k, "required": v, "actual": c.get(k)})
    for k, v in base.get("ceilings", {}).items():
        if c.get(k) is None or c[k] > v:
            failures.append({"kind": "ceiling", "field": k, "requiredMax": v, "actual": c.get(k)})

    req = base.get("required", {})
    missing = sorted(set(req.get("sceneRootNames", [])) - c["allSceneRootNames"])
    if missing:
        failures.append({"kind": "required-set-loss", "field": "sceneRootNamesAcrossAllScenes", "missingCount": len(missing), "missing": missing})
    for field in ("usedMaterialNames", "baseColorBoundMaterialNames", "normalBoundMaterialNames"):
        missing = sorted(set(req.get(field, [])) - c[field])
        if missing:
            failures.append({"kind": "required-set-loss", "field": field, "missingCount": len(missing), "missing": missing})

    for k, v in base.get("t6Invariants", {}).items():
        if v is None: continue
        actual = c.get(k)
        if actual is None or actual < v:
            failures.append({"kind": "t6-invariant", "field": k, "requiredMin": v, "actual": actual})

    for k, v in base.get("fullMapInvariants", {}).items():
        if v is None: continue
        actual = c.get(k)
        if isinstance(v, (int, float)):
            if actual is None or actual < v:
                failures.append({"kind": "full-map-invariant", "field": k, "requiredMin": v, "actual": actual})
        elif actual != v:
            failures.append({"kind": "full-map-invariant", "field": k, "required": v, "actual": actual})

    cs = base.get("canonicalScene") or {}
    if cs:
        if cs.get("name") and c["activeSceneName"] != cs["name"]:
            failures.append({"kind": "canonical-scene", "field": "name", "required": cs["name"], "actual": c["activeSceneName"]})
        if cs.get("minRootCount") is not None and c["sceneRootCount"] < cs["minRootCount"]:
            failures.append({"kind": "canonical-scene", "field": "rootCount", "requiredMin": cs["minRootCount"], "actual": c["sceneRootCount"]})
        missing = sorted(set(cs.get("requiredRootNames", [])) - c["activeSceneRootNames"])
        if missing:
            failures.append({"kind": "canonical-scene", "field": "requiredRootNames", "missingCount": len(missing), "missing": missing})
        for needle in cs.get("forbiddenRootSubstrings", []):
            bad = sorted(n for n in c["activeSceneRootNames"] if needle.lower() in n.lower())
            if bad:
                failures.append({"kind": "canonical-scene", "field": "forbiddenRootSubstring", "substring": needle, "count": len(bad), "names": bad})

    if c["badMaterialReferences"]:
        failures.append({"kind": "structural", "field": "badMaterialReferences", "required": 0, "actual": c["badMaterialReferences"]})

    report = {
        "format": "t6-glb-nonregression-report-v3",
        "baseline": str(a.baseline),
        "candidate": {k: (sorted(v) if isinstance(v, set) else v) for k, v in c.items() if not k.endswith("Names")},
        "pass": not failures,
        "failureCount": len(failures),
        "failures": failures,
        "policy": "Previously proven data may move between scenes but may not disappear. Coverage floors, material bindings, full-map invariants, retail sky identity and canonical-scene visibility remain mandatory.",
    }
    if a.report:
        a.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"pass": report["pass"], "failureCount": len(failures), "candidateSha256": c["sha256"], "candidateBytes": c["bytes"]}, indent=2))
    if failures:
        for f in failures[:12]: print(json.dumps(f, sort_keys=True))
        raise SystemExit(2)

if __name__ == "__main__":
    main()
