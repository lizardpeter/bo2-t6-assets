#!/usr/bin/env python3
import hashlib
import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
TOOL = HERE / "t6_player_body_close_v1.py"
PROMOTER = HERE / "t6_player_body_retail_proof_v1.py"


def loadmod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = loadmod(TOOL, "bodyclose")
promoter = loadmod(PROMOTER, "bodypromoter")


def h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Raw:
    @staticmethod
    def parse_front(data):
        return {"block_sizes": [{"bytes": 999} for _ in range(8)]}


class Probe:
    mode = "exact"

    @classmethod
    def probe_name(cls, data, target, raw, blocks):
        if cls.mode == "missing":
            return {"status": "not_inline_locatable", "name": target["name"], "reason": "fixture missing"}
        return {
            "status": "exact_inline_xmodel", "name": target["name"], "rawStructOffset": 100,
            "fixedRecordSha256": "1" * 64, "fixedPlusNameSha256": "2" * 64,
            "numBones": 3, "numRootBones": 1, "numSurfs": 1, "numLods": 1,
            "radius": 9.0, "mins": [-1, -1, 0], "maxs": [1, 1, 9],
            "lods": [{"index": 0, "dist": 100.0, "numSurfs": 1, "surfIndex": 0}],
            "pointers": {},
        }


class Skeleton:
    catalog_mode = "one"

    @staticmethod
    def parse_top_level_xasset_table(data):
        return {"entries": [{}, {}, {}]}

    @classmethod
    def build_xmodel_catalog(cls, data, maxi):
        row = {"name": "c_test_mp_unit_smg_fb", "fixedSourceStart": 100}
        if cls.catalog_mode == "two":
            return {1: row, 2: dict(row)}
        return {1: row}

    @staticmethod
    def normalize_skeleton(data, start, *, xasset_index, identity_name):
        return {
            "format": "t6-xmodel-skeleton-normalized-v2",
            "source": {"expandedSha256": h(data), "xmodelFixedStart": start},
            "identity": {"name": identity_name, "xassetIndex": xasset_index},
            "skeletonSource": {"mode": "inline_owned"},
            "skeleton": {
                "numBones": 3, "numRootBones": 1,
                "bones": [{"name": "tag_origin"}, {"name": "j_spine"}, {"name": "j_head"}],
                "allocationTailAllZero": True,
            },
            "validation": {"allBoneNamesResolved": True, "hierarchyValid": True},
        }


class MeshNormalizer:
    fail = False

    def __init__(self, data, start):
        self.data = data
        self.start = start

    def normalize(self):
        if type(self).fail:
            raise ValueError("packed verts0 unsupported")
        return {
            "format": "t6-xmodel-mesh-normalized-v1",
            "identity": {"name": "c_test_mp_unit_smg_fb"},
            "source": {"assetFixedStart": self.start},
            "xmodel": {"numBones": 3, "numRootBones": 1, "numSurfs": 1, "numLods": 1},
            "surfaces": [{
                "vertCount": 3, "triCount": 1,
                "vertices": [{}, {}, {}], "triangles": [[0, 1, 2]],
            }],
            "validation": {"allLocalTriangleIndicesInRange": True},
        }


class Mesh:
    Normalizer = MeshNormalizer


mods = SimpleNamespace(raw=Raw, probe=Probe, skeleton=Skeleton, mesh=Mesh, promoter=promoter)

with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    ff = td / "f.ff"; exp = td / "f.expanded"
    ff.write_bytes(b"ff"); exp.write_bytes(b"expanded")

    out = m.close_body(name="c_test_mp_unit_smg_fb", zone_name="faction_test_mp", fastfile=ff, expanded=exp,
                       raw_parser_path=td / "unused.py", out_dir=td / "out", modules=mods)
    assert out["status"] == "closed"
    assert out["summary"] == {"xassetIndex": 1, "bones": 3, "rootBones": 1, "surfaces": 1, "vertices": 3, "triangles": 1}
    assert (td / "out" / "player_body_retail_proof_v1.json").exists()

    Probe.mode = "missing"
    out = m.close_body(name="c_test_mp_unit_smg_fb", zone_name="faction_test_mp", fastfile=ff, expanded=exp,
                       raw_parser_path=td / "unused.py", out_dir=td / "missing", modules=mods)
    assert out["status"] == "blocked" and out["blockerStage"] == "xmodel-identity"
    assert not (td / "missing" / "player_body_retail_proof_v1.json").exists()
    Probe.mode = "exact"

    Skeleton.catalog_mode = "two"
    out = m.close_body(name="c_test_mp_unit_smg_fb", zone_name="faction_test_mp", fastfile=ff, expanded=exp,
                       raw_parser_path=td / "unused.py", out_dir=td / "ambig", modules=mods)
    assert out["status"] == "blocked" and out["blockerStage"] == "xasset-index-binding"
    assert "one top-level XAsset" in out["blocker"]
    Skeleton.catalog_mode = "one"

    MeshNormalizer.fail = True
    out = m.close_body(name="c_test_mp_unit_smg_fb", zone_name="faction_test_mp", fastfile=ff, expanded=exp,
                       raw_parser_path=td / "unused.py", out_dir=td / "meshblock", modules=mods)
    assert out["status"] == "blocked" and out["blockerStage"] == "mesh"
    assert "packed verts0" in out["blocker"]
    assert not (td / "meshblock" / "player_body_retail_proof_v1.json").exists()

print("PASS t6_player_body_close_v1")
