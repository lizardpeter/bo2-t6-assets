#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import t6_oat_parent_dependency_conflict_census_v1 as conflict


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def material(root: Path, rel: str, techset: str) -> None:
    write(root / "materials" / f"{rel}.json", json.dumps({
        "_game": "t6",
        "_type": "material",
        "name": rel,
        "techniqueSet": techset,
    }))


def techset(root: Path, name: str, technique_name: str, type_name: str = "lit") -> None:
    write(root / "techsets" / f"{name}.techset", f'"{type_name}":\n{technique_name};\n')


def technique(root: Path, name: str, vs: str, ps: str) -> None:
    write(root / "techniques" / f"{name}.tech", f'''{{
stateMap "default";
vertexShader 4.0 "{vs}"
{{
}}
pixelShader 4.0 "{ps}"
{{
}}
}}
''')
    write(root / "shader_bin" / f"vs_{vs}.cso", ("VS:" + vs).encode())
    write(root / "shader_bin" / f"ps_{ps}.cso", ("PS:" + ps).encode())


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        map_root = base / "map"
        patch_root = base / "patch"

        # Two Materials share one duplicate parent TechniqueSet.  The conflict
        # record must retain both material users and both exact child identities.
        material(map_root, "wpc/a", "parent_set")
        material(map_root, "wpc/b", "parent_set")
        techset(map_root, "parent_set", "same_child", "unlit")
        techset(patch_root, "parent_set", "same_child", "unlit")
        technique(map_root, "same_child", "map_vs", "map_ps")
        technique(patch_root, "same_child", "patch_vs", "patch_ps")

        result = conflict.build(map_root, [map_root, patch_root])
        s = result["summary"]
        assert result["authoritativeWinnerSelection"] is False
        assert s["ordinaryNativeMaterialCount"] == 2
        assert s["divergentParentOwnedChildConflictCount"] == 1
        assert s["missingParentOwnedChildConflictCount"] == 0
        assert s["unresolvedConflictCount"] == 1
        assert s["winnerSelectedCount"] == 0
        row = result["conflicts"][0]
        assert row["kind"] == "divergent-parent-owned-child"
        assert row["techniqueSet"] == "parent_set"
        assert row["technique"] == "same_child"
        assert row["declaredTechniqueTypes"] == ["unlit"]
        assert row["materials"] == ["wpc/a", "wpc/b"]
        assert row["distinctParsedPassStageIdentityCount"] == 2
        assert len(row["ownerChildren"]) == 2
        assert all(x["present"] for x in row["ownerChildren"])
        identities = {x["parsedPassStageIdentitySha256"] for x in row["ownerChildren"]}
        assert len(identities) == 2
        assert row["resolution"] == "unresolved-no-winner-selected"

        # A parent duplicate missing its declared same-root child is retained as
        # a different unresolved conflict instead of silently borrowing another root.
        miss_map = base / "miss_map"
        miss_patch = base / "miss_patch"
        material(miss_map, "wpc/m", "missing_set")
        techset(miss_map, "missing_set", "missing_child")
        techset(miss_patch, "missing_set", "missing_child")
        technique(miss_map, "missing_child", "vs", "ps")
        missing = conflict.build(miss_map, [miss_map, miss_patch])
        ms = missing["summary"]
        assert ms["divergentParentOwnedChildConflictCount"] == 0
        assert ms["missingParentOwnedChildConflictCount"] == 1
        mrow = missing["conflicts"][0]
        assert mrow["kind"] == "missing-parent-owned-child"
        assert mrow["missingParentOwners"] == [str(miss_patch.resolve())]
        assert mrow["resolution"] == "unresolved-no-winner-selected"

        # Identical parent-owned children produce no unresolved conflict.
        ok_map = base / "ok_map"
        ok_patch = base / "ok_patch"
        material(ok_map, "wpc/ok", "ok_set")
        techset(ok_map, "ok_set", "ok_child")
        techset(ok_patch, "ok_set", "ok_child")
        technique(ok_map, "ok_child", "same_vs", "same_ps")
        technique(ok_patch, "ok_child", "same_vs", "same_ps")
        ok = conflict.build(ok_map, [ok_map, ok_patch])
        assert ok["summary"]["unresolvedConflictCount"] == 0
        assert ok["conflicts"] == []

    print("PASS: parent-owned conflict census records exact unresolved dependencies without selecting winners")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
