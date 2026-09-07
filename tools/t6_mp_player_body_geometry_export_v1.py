#!/usr/bin/env python3
"""Export the 30 independently proven base-MP player bodies as geometry/skeleton GLBs.

Authority is deliberately narrow:
- body membership, source offsets/hashes, and aggregate geometry/skeleton counts
  come from mp_player_body_faction_corpus_checkpoint_v1.json;
- XAsset identity/xassetIndex comes from the already-closed native identity census;
- mesh and skeleton payloads are decoded from freshly expanded exact faction FFs;
- the existing source-closed skinned exporter supplies bind hierarchy/skin semantics.

Portable visual-material fidelity is NOT claimed here.  In particular, the T6 packed
vertex-color field is not promoted to glTF COLOR_0.  Historical v3/v4 emit COLOR_0;
this exporter removes that semantic and physically compacts the embedded buffer so
those bytes are absent from the authoritative GLB.  No Material/TechniqueSet/image
objects are emitted.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

from t6_mp_player_body_nested_closure_v1 import load_identity_reports
from t6_xmodel_mesh_normalize_v1 import Normalizer
from t6_xmodel_skeleton_normalize_v2 import normalize_skeleton
from t6_xanim_skinned_gltf_export_v4 import export as export_v4, ExportError

FORMAT = "t6-mp-player-body-geometry-export-v1"
BODY_FORMAT = "t6-mp-player-body-faction-corpus-checkpoint-v1"
IDENTITY_FORMAT = "t6-native-xmodel-zone-identity-closure-v2"
XMODEL_FIXED_BYTES = 248
BUFFER_PREFIX = "data:application/octet-stream;base64,"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> dict[str, Any]:
    o = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(o, dict):
        raise ValueError(f"{path}: expected JSON object")
    return o


def normalize3(v: list[float]) -> tuple[float, float, float]:
    n = math.sqrt(sum(float(x) * float(x) for x in v))
    if not math.isfinite(n) or n <= 1e-20:
        raise ExportError(f"invalid normal {v}")
    return tuple(float(x) / n for x in v)


def _sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def source_orientation(mesh_doc: dict, lod: int, max_triangles_per_surface: int = 64) -> dict:
    lm = next((x for x in mesh_doc["xmodel"]["lods"] if int(x["index"]) == lod), None)
    if lm is None:
        raise ExportError(f"LOD{lod} unavailable")
    first, count = int(lm["surfIndex"]), int(lm["numSurfs"])
    selected = mesh_doc["surfaces"][first:first+count]
    dots: list[float] = []
    for s in selected:
        verts = s["vertices"]
        tris = s["triangles"]
        step = max(1, len(tris) // max_triangles_per_surface)
        for tri in tris[::step]:
            i0, i1, i2 = map(int, tri)
            p0, p1, p2 = (verts[i0]["position"], verts[i1]["position"], verts[i2]["position"])
            c = _cross(_sub(p1, p0), _sub(p2, p0))
            ns = tuple(sum(normalize3(verts[i]["normal"])[k] for i in (i0, i1, i2)) for k in range(3))
            cn, nn = _norm(c), _norm(ns)
            if cn < 1e-10 or nn < 1e-10:
                continue
            dots.append(_dot(c, ns) / (cn * nn))
    if not dots:
        raise ExportError(f"LOD{lod}: no nondegenerate triangle/normal samples")
    sd = sorted(dots)
    negative = sum(d < 0 for d in dots)
    return {
        "sampleCount": len(dots),
        "negativeFraction": negative / len(dots),
        "positiveFraction": (len(dots)-negative) / len(dots),
        "medianNormalDot": sd[len(sd)//2],
    }


def reverse_lod_winding(mesh_doc: dict, lod: int) -> tuple[dict, dict]:
    before = source_orientation(mesh_doc, lod)
    if before["negativeFraction"] < 0.98 or before["medianNormalDot"] > -0.5:
        raise ExportError(f"LOD{lod}: source triangle winding is not proven reverse-glTF: {before}")
    out = copy.deepcopy(mesh_doc)
    lm = next(x for x in out["xmodel"]["lods"] if int(x["index"]) == lod)
    first, count = int(lm["surfIndex"]), int(lm["numSurfs"])
    tri_count = 0
    for s in out["surfaces"][first:first+count]:
        s["triangles"] = [[int(t[0]), int(t[2]), int(t[1])] for t in s["triangles"]]
        tri_count += len(s["triangles"])
    after = source_orientation(out, lod)
    if after["positiveFraction"] < 0.98 or after["medianNormalDot"] < 0.5:
        raise ExportError(f"LOD{lod}: winding repair did not align triangles to normals: {after}")
    return out, {"trianglesFlipped": tri_count, "before": before, "after": after}


def compact_without_color(gltf: dict) -> tuple[dict, bytes, dict]:
    """Remove COLOR_0 and rebuild the one embedded buffer from still-used accessors."""
    g = copy.deepcopy(gltf)
    if len(g.get("buffers", [])) != 1:
        raise ExportError("expected exactly one glTF buffer")
    uri = g["buffers"][0].get("uri", "")
    if not uri.startswith(BUFFER_PREFIX):
        raise ExportError("expected embedded base64 glTF buffer")
    old_raw = base64.b64decode(uri[len(BUFFER_PREFIX):])

    removed = 0
    for mesh in g.get("meshes", []):
        for p in mesh.get("primitives", []):
            attrs = p.get("attributes") or {}
            if "COLOR_0" in attrs:
                del attrs["COLOR_0"]
                removed += 1
    if removed == 0:
        raise ExportError("historical exporter emitted no COLOR_0 to remove; review boundary changed")

    if any(k in g for k in ("materials", "textures", "images", "samplers")):
        raise ExportError("geometry-only export unexpectedly contains portable material/image state")
    if g.get("animations"):
        raise ExportError("geometry-only export unexpectedly contains animation")

    used: set[int] = set()
    for mesh in g.get("meshes", []):
        for p in mesh.get("primitives", []):
            for ai in (p.get("attributes") or {}).values():
                used.add(int(ai))
            if "indices" in p:
                used.add(int(p["indices"]))
    for skin in g.get("skins", []):
        if "inverseBindMatrices" in skin:
            used.add(int(skin["inverseBindMatrices"]))
    if not used:
        raise ExportError("no live accessors after COLOR_0 removal")

    old_acc = g.get("accessors", [])
    old_views = g.get("bufferViews", [])
    if any(ai < 0 or ai >= len(old_acc) for ai in used):
        raise ExportError("live accessor index outside accessor table")
    acc_order = sorted(used)
    acc_map = {old: new for new, old in enumerate(acc_order)}
    view_order: list[int] = []
    for ai in acc_order:
        vi = int(old_acc[ai]["bufferView"])
        if vi not in view_order:
            view_order.append(vi)
    if any(vi < 0 or vi >= len(old_views) for vi in view_order):
        raise ExportError("live bufferView index outside bufferView table")
    view_map = {old: new for new, old in enumerate(view_order)}

    new_raw = bytearray()
    new_views = []
    for old_vi in view_order:
        while len(new_raw) % 4:
            new_raw.append(0)
        v = copy.deepcopy(old_views[old_vi])
        off = int(v.get("byteOffset", 0)); size = int(v["byteLength"])
        if off < 0 or size < 0 or off + size > len(old_raw):
            raise ExportError(f"bufferView {old_vi} lies outside embedded buffer")
        new_off = len(new_raw)
        new_raw.extend(old_raw[off:off+size])
        v["buffer"] = 0
        v["byteOffset"] = new_off
        new_views.append(v)

    new_acc = []
    for old_ai in acc_order:
        a = copy.deepcopy(old_acc[old_ai])
        a["bufferView"] = view_map[int(a["bufferView"])]
        new_acc.append(a)

    for mesh in g.get("meshes", []):
        for p in mesh.get("primitives", []):
            attrs = p.get("attributes") or {}
            for sem in list(attrs):
                attrs[sem] = acc_map[int(attrs[sem])]
            if "indices" in p:
                p["indices"] = acc_map[int(p["indices"])]
    for skin in g.get("skins", []):
        if "inverseBindMatrices" in skin:
            skin["inverseBindMatrices"] = acc_map[int(skin["inverseBindMatrices"])]

    g["accessors"] = new_acc
    g["bufferViews"] = new_views
    g["buffers"] = [{"byteLength": len(new_raw)}]
    for mesh in g.get("meshes", []):
        for p in mesh.get("primitives", []):
            if "COLOR_0" in (p.get("attributes") or {}):
                raise ExportError("COLOR_0 survived compaction")
    return g, bytes(new_raw), {
        "colorAttributesRemoved": removed,
        "oldBufferBytes": len(old_raw),
        "newBufferBytes": len(new_raw),
        "removedBufferBytes": len(old_raw)-len(new_raw),
        "liveAccessors": len(new_acc),
        "liveBufferViews": len(new_views),
    }


def glb_bytes(gltf: dict, binbuf: bytes) -> bytes:
    g = copy.deepcopy(gltf)
    while len(binbuf) % 4:
        binbuf += b"\0"
    if len(g.get("buffers", [])) != 1:
        raise ExportError("GLB writer requires one buffer")
    g["buffers"][0] = {"byteLength": len(binbuf)}
    jb = json.dumps(g, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    while len(jb) % 4:
        jb += b" "
    total = 12 + 8 + len(jb) + 8 + len(binbuf)
    return (struct.pack("<4sII", b"glTF", 2, total)
            + struct.pack("<I4s", len(jb), b"JSON") + jb
            + struct.pack("<I4s", len(binbuf), b"BIN\0") + binbuf)


def parse_glb(raw: bytes) -> tuple[dict, bytes]:
    if len(raw) < 20:
        raise ExportError("short GLB")
    magic, version, total = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF" or version != 2 or total != len(raw):
        raise ExportError("invalid GLB2 header")
    off = 12; doc = None; bins = []
    while off < len(raw):
        n, typ = struct.unpack_from("<I4s", raw, off); off += 8
        chunk = raw[off:off+n]; off += n
        if typ == b"JSON":
            doc = json.loads(chunk)
        elif typ == b"BIN\0":
            bins.append(chunk)
    if doc is None or len(bins) != 1:
        raise ExportError("GLB must contain one JSON and one BIN chunk")
    return doc, bins[0]


def export_lod(mesh: dict, skeleton: dict, lod: int) -> tuple[bytes, dict]:
    rewound, winding = reverse_lod_winding(mesh, lod)
    gltf = export_v4(rewound, skeleton, None, lod)
    gltf.setdefault("extras", {}).setdefault("T6", {}).update({
        "authority": "retail geometry/skeleton only",
        "portableMaterialFidelity": "not claimed",
        "vertexColorPolicy": "T6 packed colorRGBA deliberately omitted; not emitted as glTF COLOR_0",
        "triangleWinding": winding,
    })
    compact, binbuf, compact_audit = compact_without_color(gltf)
    raw = glb_bytes(compact, binbuf)
    parsed, parsed_bin = parse_glb(raw)
    if parsed["buffers"][0]["byteLength"] != len(parsed_bin):
        raise ExportError("reparsed GLB buffer length mismatch")
    if any("COLOR_0" in (p.get("attributes") or {}) for m in parsed.get("meshes", []) for p in m.get("primitives", [])):
        raise ExportError("reparsed GLB contains COLOR_0")
    if any(k in parsed for k in ("materials", "textures", "images", "samplers")):
        raise ExportError("reparsed geometry-only GLB contains visual-material state")
    return raw, {"winding": winding, "compaction": compact_audit}


def validate_mesh_skeleton(mesh: dict, skel: dict, expected: dict) -> dict:
    if mesh.get("format") != "t6-xmodel-mesh-normalized-v1":
        raise ExportError("unexpected normalized mesh format")
    if skel.get("format") != "t6-xmodel-skeleton-normalized-v2":
        raise ExportError("unexpected normalized skeleton format")
    name = expected["name"]
    if mesh.get("identity", {}).get("name") != name or skel.get("identity", {}).get("name") != name:
        raise ExportError("normalized identity mismatch")
    xm = mesh["xmodel"]; ss = skel["skeleton"]
    if int(xm["numBones"]) != expected["bones"] or int(ss["numBones"]) != expected["bones"]:
        raise ExportError("bone count mismatch")
    if int(xm["numRootBones"]) != expected["roots"] or int(ss["numRootBones"]) != expected["roots"]:
        raise ExportError("root count mismatch")
    lods = xm.get("lods", [])
    if len(lods) != 4 or [int(x["index"]) for x in lods] != [0,1,2,3]:
        raise ExportError(f"expected exact four LODs, got {lods}")
    surfaces = mesh.get("surfaces", [])
    verts = sum(int(s["vertCount"]) for s in surfaces)
    tris = sum(int(s["triCount"]) for s in surfaces)
    if len(surfaces) != expected["surfaces"] or verts != expected["vertices"] or tris != expected["triangles"]:
        raise ExportError(
            f"aggregate geometry mismatch {len(surfaces)}/{verts}/{tris} != "
            f"{expected['surfaces']}/{expected['vertices']}/{expected['triangles']}"
        )
    if skel.get("validation", {}).get("allBoneNamesResolved") is not True or skel.get("validation", {}).get("hierarchyValid") is not True:
        raise ExportError("skeleton name/hierarchy validation failed")
    lod_rows = []
    covered = []
    for lm in lods:
        first, count = int(lm["surfIndex"]), int(lm["numSurfs"])
        if first < 0 or count <= 0 or first + count > len(surfaces):
            raise ExportError(f"LOD{lm['index']} surface span outside normalized surfaces")
        selected = surfaces[first:first+count]
        covered.extend(range(first, first+count))
        lod_rows.append({
            "lod": int(lm["index"]), "surfIndex": first, "surfaces": count,
            "vertices": sum(int(s["vertCount"]) for s in selected),
            "triangles": sum(int(s["triCount"]) for s in selected),
        })
    if sorted(covered) != list(range(len(surfaces))):
        raise ExportError("four LOD spans do not partition the fixed XSurface set exactly")
    return {"lods": lod_rows, "surfaces": len(surfaces), "vertices": verts, "triangles": tris, "bones": int(ss["numBones"]), "roots": int(ss["numRootBones"])}


def self_test() -> None:
    # Deterministic GLB writer and parser.
    d = {"asset":{"version":"2.0"},"buffers":[{"byteLength":4}],"bufferViews":[],"accessors":[],"meshes":[]}
    a = glb_bytes(d, b"abcd"); b = glb_bytes(d, b"abcd")
    if a != b or parse_glb(a)[1] != b"abcd":
        raise AssertionError("deterministic GLB self-test failed")
    # Synthetic winding sign.
    m = {"xmodel":{"lods":[{"index":0,"surfIndex":0,"numSurfs":1}]},"surfaces":[{
        "vertices":[{"position":[0,0,0],"normal":[0,0,1]},{"position":[0,1,0],"normal":[0,0,1]},{"position":[1,0,0],"normal":[0,0,1]}],
        "triangles":[[0,1,2]]
    }]}
    fixed, proof = reverse_lod_winding(m, 0)
    if proof["before"]["negativeFraction"] != 1.0 or proof["after"]["positiveFraction"] != 1.0 or fixed["surfaces"][0]["triangles"][0] != [0,2,1]:
        raise AssertionError("winding self-test failed")
    print(json.dumps({"selfTest":"pass","format":FORMAT}, indent=2))


def run(a) -> int:
    corpus = load(a.body_corpus)
    if corpus.get("format") != BODY_FORMAT:
        raise ValueError(f"unexpected body corpus format {corpus.get('format')!r}")
    columns, rows, sources = corpus.get("columns"), corpus.get("rows"), corpus.get("sources")
    if not isinstance(columns, list) or not isinstance(rows, list) or not isinstance(sources, dict):
        raise ValueError("body corpus missing columns/rows/sources")
    if len(rows) != 30:
        raise ValueError(f"authoritative corpus must contain exactly 30 bodies, got {len(rows)}")
    col = {name:i for i,name in enumerate(columns)}
    required = ["name","zone","fixedStart","fixedRecordSha256","bones","roots","surfaces","vertices","triangles","corpusSkeletonSha256"]
    if any(x not in col for x in required):
        raise ValueError("body corpus missing required columns")
    reports = load_identity_reports(a.identity_results_root)
    a.out_root.mkdir(parents=True, exist_ok=True)

    wanted = a.only_name
    body_results = []; failures = []
    for rawrow in rows:
        row = {k: rawrow[col[k]] for k in required}
        name, zone = str(row["name"]), str(row["zone"])
        if wanted and name != wanted:
            continue
        expected = {
            "name":name, "bones":int(row["bones"]), "roots":int(row["roots"]), "surfaces":int(row["surfaces"]),
            "vertices":int(row["vertices"]), "triangles":int(row["triangles"]),
        }
        rec: dict[str, Any] = {"name":name,"zone":zone,"fixedStart":int(row["fixedStart"]),"closed":False,"lods":[]}
        try:
            expanded = a.expanded_root / f"{zone}.expanded"
            data = expanded.read_bytes()
            hashes = sources.get(zone)
            if not isinstance(hashes, list) or len(hashes) != 2:
                raise ValueError(f"{zone}: invalid source hash pair")
            observed_expanded = sha256_bytes(data)
            if observed_expanded != str(hashes[1]):
                raise ValueError(f"{zone}: expanded SHA-256 mismatch")
            start = int(row["fixedStart"])
            if sha256_bytes(data[start:start+XMODEL_FIXED_BYTES]) != str(row["fixedRecordSha256"]):
                raise ValueError(f"{name}: fixed XModel record SHA-256 mismatch")
            report = reports.get(f"zone/all/{zone}.ff")
            if report is None or report.get("format") != IDENTITY_FORMAT:
                raise ValueError(f"{zone}: missing/invalid native identity report")
            matches = [x for x in report.get("xmodels",[]) if isinstance(x,dict) and x.get("nativeResolvedName") == name]
            if len(matches) != 1:
                raise ValueError(f"{name}: expected one native identity row, got {len(matches)}")
            ident = matches[0]
            if ident.get("identityClosed") is not True or ident.get("sourceKind") != "native-source-consuming" or int(ident.get("sourceStart",-1)) != start:
                raise ValueError(f"{name}: native identity/start gate failed")
            xasset_index = int(ident["xassetIndex"])

            mesh = Normalizer(data, start).normalize()
            skeleton = normalize_skeleton(data, start, xasset_index=xasset_index, identity_name=name)
            validation = validate_mesh_skeleton(mesh, skeleton, expected)
            rec.update({
                "expandedSha256": observed_expanded,
                "fixedRecordSha256": str(row["fixedRecordSha256"]),
                "xassetIndex": xasset_index,
                "nativeSourceEnd": int(ident["sourceEnd"]),
                "meshOwnedSerializedSha256": mesh["source"]["meshOwnedSerializedSha256"],
                "skeletonSerializedSha256": skeleton["source"]["xmodelSerializedSha256"],
                "corpusSkeletonSha256": str(row["corpusSkeletonSha256"]),
                "validation": validation,
                "skeletonSource": skeleton["skeletonSource"].get("mode"),
            })
            if skeleton["source"]["xmodelSerializedEnd"] != int(ident["sourceEnd"]):
                raise ValueError(f"{name}: skeleton walker endpoint != native sourceEnd")

            body_dir = a.out_root / name
            body_dir.mkdir(parents=True, exist_ok=True)
            for lm in validation["lods"]:
                lod = int(lm["lod"])
                raw_glb, detail = export_lod(mesh, skeleton, lod)
                out = body_dir / f"{name}_lod{lod}.glb"
                out.write_bytes(raw_glb)
                parsed, _ = parse_glb(raw_glb)
                skin_validation = parsed.get("extras",{}).get("T6",{}).get("skinValidation",{})
                if int(skin_validation.get("vertices",-1)) != int(lm["vertices"]) or int(skin_validation.get("triangles",-1)) != int(lm["triangles"]):
                    raise ValueError(f"{name} LOD{lod}: exported skin census != normalized LOD census")
                rec["lods"].append({
                    **lm, "file":str(out.relative_to(a.out_root)), "bytes":len(raw_glb), "sha256":sha256_bytes(raw_glb),
                    "skinValidation":skin_validation, **detail,
                })
            if len(rec["lods"]) != 4:
                raise ValueError(f"{name}: did not emit exactly four LOD GLBs")
            rec["closed"] = True
        except Exception as exc:
            rec["failure"] = repr(exc)
            failures.append({"name":name,"zone":zone,"failure":repr(exc)})
        body_results.append(rec)

    expected_output_bodies = 1 if wanted else 30
    gates = {
        "expectedBodyCount": len(body_results) == expected_output_bodies,
        "allBodiesClosed": len(body_results) == expected_output_bodies and all(x.get("closed") is True for x in body_results),
        "exactFourLodsEach": len(body_results) == expected_output_bodies and all(len(x.get("lods",[])) == 4 for x in body_results),
        "all102BonesOneRoot": len(body_results) == expected_output_bodies and all(x.get("validation",{}).get("bones") == 102 and x.get("validation",{}).get("roots") == 1 for x in body_results),
        "zeroColor0": len(body_results) == expected_output_bodies and all(all(l.get("compaction",{}).get("colorAttributesRemoved",0) == l.get("surfaces") for l in x.get("lods",[])) for x in body_results),
        "zeroPortableMaterialClaims": True,
        "zeroFailures": not failures,
    }
    out = {
        "format":FORMAT,
        "scope":"geometry + four LODs + 102-bone skin/skeleton for proven base-MP player bodies",
        "bodyCorpus":str(a.body_corpus),
        "identitySource":"already-closed native XModel identity reports",
        "bodyCount":len(body_results),
        "glbCount":sum(len(x.get("lods",[])) for x in body_results),
        "bodies":body_results,
        "failures":failures,
        "gates":gates,
        "proofBoundary":[
            "No body is discovered by name pattern or adjacency; membership and fixed source starts come only from the retained 30-body corpus.",
            "Every body rechecks exact expanded FastFile SHA-256, exact 248-byte XModel hash, and closed native identity/sourceStart before decode.",
            "Every LOD is decoded from retail XSurface payloads; indices, skin joints/weights, skeleton names/hierarchy, and native endpoint are fail-closed.",
            "T6 source winding is proved opposite its own vertex normals before index 1/2 is swapped to core glTF CCW convention.",
            "The historical packed vertex color is deliberately not emitted as glTF COLOR_0; its bufferView/accessor bytes are physically removed.",
            "Material, TechniqueSet, shader, texture, animation, and tangent-handedness fidelity are outside this geometry/skeleton artifact and are not claimed.",
        ],
    }
    a.audit.parent.mkdir(parents=True, exist_ok=True)
    a.audit.write_text(json.dumps(out, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"format":FORMAT,"bodyCount":out["bodyCount"],"glbCount":out["glbCount"],"gates":gates,"failures":failures}, indent=2))
    if a.require_closed and not all(gates.values()):
        return 2
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-corpus", type=Path)
    ap.add_argument("--identity-results-root", type=Path)
    ap.add_argument("--expanded-root", type=Path)
    ap.add_argument("--out-root", type=Path)
    ap.add_argument("--audit", type=Path)
    ap.add_argument("--only-name")
    ap.add_argument("--require-closed", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        self_test(); return 0
    missing = [x for x in ("body_corpus","identity_results_root","expanded_root","out_root","audit") if getattr(a,x) is None]
    if missing:
        ap.error("missing required export arguments: " + ", ".join(missing))
    return run(a)


if __name__ == "__main__":
    raise SystemExit(main())
