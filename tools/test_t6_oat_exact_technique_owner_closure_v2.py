#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_exact_technique_owner_closure_v2 as closure

TARGET = "pimp_technique_shadowoverlay_5255c888"


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def census(path: Path, root: Path, *, owner: Path | None = None, type_name: str = "lit") -> None:
    owner = (owner or root).resolve()
    payload = {
        "format": "t6-oat-material-shader-census-v4",
        "proofBoundary": "synthetic v4 test fixture",
        "summary": {
            "unresolvedMaterialCount": 0,
            "divergentParentOwnedDependencyCount": 0,
        },
        "unresolved": [],
        "materials": [{
            "material": "shadowoverlay",
            "materialJsonSha256": "11" * 32,
            "techniqueSet": "trivial_shadowoverlay_14e2e827",
            "techniqueSetOwners": [str(root.resolve())],
            "programs": [{
                "techniqueType": type_name,
                "technique": TARGET,
                "groupKey": "22" * 32,
                "passStageIdentitySha256": "33" * 32,
                "passCount": 1,
                "parentTechniqueSetOwners": [str(root.resolve())],
                "techniqueOwner": str(owner),
            }],
        }],
    }
    write(path, json.dumps(payload))


def fixture(base: Path, target_bytes: bytes = b"target-technique") -> tuple[Path, Path, str]:
    root = base / "zone"
    cpath = base / "census.json"
    write(root / "techniques" / f"{TARGET}.tech", target_bytes)
    write(
        root / "techsets" / "trivial_shadowoverlay_14e2e827.techset",
        f'"lit":\n{TARGET};\n',
    )
    census(cpath, root)
    return root, cpath, sha(target_bytes)


def expect_failure(fn, needle: str) -> None:
    try:
        fn()
    except closure.ClosureError as exc:
        assert needle in str(exc), exc
    else:
        raise AssertionError("expected ClosureError")


def test_positive(base: Path) -> None:
    root, cpath, digest = fixture(base / "positive")
    result = closure.build(cpath, [("zone", root.resolve())], TARGET, len(b"target-technique"), digest)
    assert result["summary"]["authoritative"] is True
    assert result["summary"]["nativeAssociationCount"] == 1
    assert result["summary"]["parentTechniqueSetCount"] == 1
    assert result["summary"]["unresolvedCount"] == 0
    assert result["nativeAssociations"][0]["material"] == "shadowoverlay"


def test_wrong_source_format(base: Path) -> None:
    root, cpath, digest = fixture(base / "wrong_format")
    d = json.loads(cpath.read_text())
    d["format"] = "t6-oat-material-shader-census-v3"
    write(cpath, json.dumps(d))
    expect_failure(
        lambda: closure.build(cpath, [("zone", root.resolve())], TARGET, len(b"target-technique"), digest),
        "unexpected census format",
    )


def test_owner_outside_parent_fails(base: Path) -> None:
    root, cpath, digest = fixture(base / "owner_outside")
    other = base / "owner_outside" / "other"
    other.mkdir(parents=True)
    census(cpath, root, owner=other)
    expect_failure(
        lambda: closure.build(cpath, [("zone", root.resolve())], TARGET, len(b"target-technique"), digest),
        "chooses Technique owner outside parent TechniqueSet owners",
    )


def test_divergent_target_copy_fails(base: Path) -> None:
    root, cpath, digest = fixture(base / "divergent")
    other = base / "divergent" / "other"
    write(other / "techniques" / f"{TARGET}.tech", b"different")
    expect_failure(
        lambda: closure.build(
            cpath,
            [("zone", root.resolve()), ("other", other.resolve())],
            TARGET,
            len(b"target-technique"),
            digest,
        ),
        "divergent physical outputs",
    )


def test_target_identity_mismatch_fails(base: Path) -> None:
    root, cpath, digest = fixture(base / "identity")
    expect_failure(
        lambda: closure.build(cpath, [("zone", root.resolve())], TARGET, 592, digest),
        "target Technique identity mismatch",
    )


def test_parent_type_mismatch_fails(base: Path) -> None:
    root, cpath, digest = fixture(base / "type_mismatch")
    census(cpath, root, type_name="depthPrepass")
    expect_failure(
        lambda: closure.build(cpath, [("zone", root.resolve())], TARGET, len(b"target-technique"), digest),
        "census types",
    )


def test_census_parent_owner_set_must_match_physical(base: Path) -> None:
    root, cpath, digest = fixture(base / "parent_set")
    duplicate = base / "parent_set" / "duplicate"
    write(
        duplicate / "techsets" / "trivial_shadowoverlay_14e2e827.techset",
        f'"lit":\n{TARGET};\n',
    )
    write(duplicate / "techniques" / f"{TARGET}.tech", b"target-technique")
    expect_failure(
        lambda: closure.build(
            cpath,
            [("zone", root.resolve()), ("duplicate", duplicate.resolve())],
            TARGET,
            len(b"target-technique"),
            digest,
        ),
        "v4 provenance owners disagree with physical outputs",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        test_positive(base)
        test_wrong_source_format(base)
        test_owner_outside_parent_fails(base)
        test_divergent_target_copy_fails(base)
        test_target_identity_mismatch_fails(base)
        test_parent_type_mismatch_fails(base)
        test_census_parent_owner_set_must_match_physical(base)
    print("PASS: closure v2 exact target identity and provenance gates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
