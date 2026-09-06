#!/usr/bin/env python3
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "t6_player_body_retail_proof_v1.py"
REGISTRY = HERE / "t6_player_body_identity_registry_v1.py"


def loadmod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = loadmod(TOOL, "bodyproof")
registry = loadmod(REGISTRY, "bodyregistry")


def dump(path: Path, obj):
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


def h(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(td: Path):
    ff = td / "faction_test_mp.ff"
    ff.write_bytes(b"FASTFILE-fixture")
    exp = td / "faction_test_mp.expanded"
    exp.write_bytes(b"expanded-retail-fixture")
    es = h(exp)
    name = "c_test_mp_unit_smg_fb"
    start = 1234
    probe = {
        "format": "t6-xmodel-target-probe-v1",
        "source": {"bytes": exp.stat().st_size, "sha256": es},
        "targets": [{
            "status": "exact_inline_xmodel", "name": name, "rawStructOffset": start,
            "fixedRecordSha256": "1" * 64, "fixedPlusNameSha256": "2" * 64,
            "numBones": 3, "numRootBones": 1, "numSurfs": 1, "numLods": 1,
            "radius": 7.0, "mins": [-1, -2, 0], "maxs": [1, 2, 7],
            "lods": [{"index": 0, "dist": 100.0, "numSurfs": 1, "surfIndex": 0}],
            "pointers": {"boneNames": {"kind": "following"}},
        }],
    }
    skeleton = {
        "format": "t6-xmodel-skeleton-normalized-v2",
        "source": {"expandedSha256": es, "xmodelFixedStart": start},
        "identity": {"name": name, "xassetIndex": 9},
        "skeletonSource": {"mode": "inline_owned"},
        "skeleton": {
            "numBones": 3, "numRootBones": 1,
            "bones": [{"name": "tag_origin"}, {"name": "j_spine"}, {"name": "j_head"}],
            "allocationTailAllZero": True,
        },
        "validation": {"allBoneNamesResolved": True, "hierarchyValid": True},
    }
    mesh = {
        "format": "t6-xmodel-mesh-normalized-v1", "expandedSha256": es,
        "identity": {"name": name}, "source": {"assetFixedStart": start},
        "xmodel": {"numBones": 3, "numRootBones": 1, "numSurfs": 1, "numLods": 1},
        "surfaces": [{
            "vertCount": 3, "triCount": 1,
            "vertices": [{}, {}, {}], "triangles": [[0, 1, 2]],
        }],
        "validation": {"allLocalTriangleIndicesInRange": True},
    }
    pp = td / "probe.json"; sp = td / "skeleton.json"; mp = td / "mesh.json"
    dump(pp, probe); dump(sp, skeleton); dump(mp, mesh)
    return name, ff, exp, pp, sp, mp


with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    name, ff, exp, pp, sp, mp = fixture(td)
    out = m.build(name=name, zone_name="faction_test_mp", fastfile_path=ff, expanded_path=exp,
                  probe_path=pp, skeleton_path=sp, mesh_path=mp)
    assert out["status"]["fullBodyGeometryRetailProven"] is True
    assert out["status"]["fullBodySkeletonRetailProven"] is True
    assert out["fullBody"]["bones"] == 3 and out["fullBody"]["surfaces"] == 1
    assert out["fullBody"]["mesh"]["vertices"] == 3 and out["fullBody"]["mesh"]["triangles"] == 1
    assert out["fullBody"]["skeleton"]["xassetIndex"] == 9
    assert out["sourceFastfile"]["sha256"] == h(ff)

    promoted = td / "promoted.json"
    dump(promoted, out)
    rr = registry.proof_row(promoted, out)
    assert rr["name"] == name and rr["bones"] == 3 and rr["surfaces"] == 1
    assert rr["skeletonNormalizedJsonSha256"] == out["fullBody"]["skeleton"]["normalizedJsonSha256"]

    bad = json.loads(pp.read_text()); bad["source"]["sha256"] = "0" * 64; dump(pp, bad)
    try:
        m.build(name=name, zone_name="faction_test_mp", fastfile_path=ff, expanded_path=exp,
                probe_path=pp, skeleton_path=sp, mesh_path=mp)
    except ValueError as e:
        assert "expanded sha256 mismatch" in str(e)
    else:
        raise AssertionError("bad expanded hash promoted")

    name, ff, exp, pp, sp, mp = fixture(td)
    bad = json.loads(sp.read_text()); bad["validation"]["hierarchyValid"] = False; dump(sp, bad)
    try:
        m.build(name=name, zone_name="faction_test_mp", fastfile_path=ff, expanded_path=exp,
                probe_path=pp, skeleton_path=sp, mesh_path=mp)
    except ValueError as e:
        assert "hierarchy" in str(e)
    else:
        raise AssertionError("bad skeleton promoted")

    name, ff, exp, pp, sp, mp = fixture(td)
    bad = json.loads(mp.read_text()); bad["identity"]["name"] = "other"; dump(mp, bad)
    try:
        m.build(name=name, zone_name="faction_test_mp", fastfile_path=ff, expanded_path=exp,
                probe_path=pp, skeleton_path=sp, mesh_path=mp)
    except ValueError as e:
        assert "mesh identity mismatch" in str(e)
    else:
        raise AssertionError("wrong mesh promoted")

    name, ff, exp, pp, sp, mp = fixture(td)
    bad = json.loads(mp.read_text()); bad["surfaces"][0]["vertices"].pop(); dump(mp, bad)
    try:
        m.build(name=name, zone_name="faction_test_mp", fastfile_path=ff, expanded_path=exp,
                probe_path=pp, skeleton_path=sp, mesh_path=mp)
    except ValueError as e:
        assert "geometry cardinality mismatch" in str(e)
    else:
        raise AssertionError("truncated mesh promoted")

print("PASS t6_player_body_retail_proof_v1")
