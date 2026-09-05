#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace

import t6_generated_layered_normal_vs_basis_probe_v2 as probe
import t6_retail_special_shdr_symbolic_v1 as shared
import t6_vertex_output_symbolic_v1 as symbolic


def _symbolic_fixture(reversed_cross: bool = False):
    dag = shared.Dag()
    n = tuple(dag.add("symbol", name=f"N.{c}") for c in "xyz")
    t = tuple(dag.add("symbol", name=f"T.{c}") for c in "xyz")
    h = dag.add("symbol", name="v3.w")
    b = symbolic.cross_times_handedness(
        dag,
        t if reversed_cross else n,
        n if reversed_cross else t,
        h,
    )
    outputs = {}
    for lane in range(3):
        outputs[(0, lane)] = n[lane]  # OSGN TC1
        outputs[(1, lane)] = b[lane]  # OSGN TC2
        outputs[(2, lane)] = t[lane]  # OSGN TC3
    return {"dag": dag, "outputs": outputs, "nodeCount": len(dag.nodes)}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_normal_vs_probe_v2_") as td:
        root = Path(td)
        (root / "shader_bin").mkdir()
        blob = b"DXBC-vs-basis-fixture"
        sha = hashlib.sha256(blob).hexdigest()
        rel = "shader_bin/vs_fixture.cso"
        (root / rel).write_bytes(blob)

        base_doc = {
            "format": "t6-generated-layered-normal-vs-basis-probe-v1",
            "pixelProof": "normal-proof",
            "profiles": [{
                "techniqueSet": "lit_sm_fixture",
                "vertexShaderSha256": sha,
                "vertexShaderFile": rel,
                "directRoleMatches": {
                    "baseIsWorldNormalFromNormal0": True,
                    "xBasisIsWorldTangentFromTangent0": True,
                    "yBasisPhysicalRole": "unpromoted",
                },
            }],
            "summary": {
                "materialOwnerCount": 2,
                "techniqueSetCount": 1,
                "pairedVertexShaderIdentityCount": 1,
                "directBaseNormalTechniqueSetCount": 1,
                "directXBasisTangentTechniqueSetCount": 1,
                "directBaseAndXPairTechniqueSetCount": 1,
                "yBasisPromotedTechniqueSetCount": 0,
                "allPairedVsPayloadsExact": True,
            },
        }
        base = SimpleNamespace()
        base.signature = lambda shader_blob, tag: (
            {0: ("TEXCOORD", 1), 1: ("TEXCOORD", 2), 2: ("TEXCOORD", 3)}
            if tag == b"OSGN"
            else {3: ("TANGENT", 0)}
        )

        old_build = probe.v1.build
        old_load = probe._load
        old_symbolic = probe.symbolic_vertex
        try:
            probe.v1.build = lambda *args, **kwargs: base_doc
            probe._load = lambda path, name: base if "base_v2" in name else object()
            probe.symbolic_vertex = lambda shader_blob, operand, opcode: _symbolic_fixture(False)
            doc = probe.build(
                {"fixture": True},
                oat_root=root,
                paired_vs_probe_path=Path("paired.py"),
                base_verifier_path=Path("base.py"),
                opcode_path=Path("opcode.py"),
                operand_path=Path("operand.py"),
            )
        finally:
            probe.v1.build = old_build
            probe._load = old_load
            probe.symbolic_vertex = old_symbolic

        row = doc["profiles"][0]
        assert row["binormalAlgebra"]["status"] == "exact-binormal"
        assert row["binormalAlgebra"]["comparison"]["uniqueMatch"] == (
            "cross(normal,tangent)*handedness"
        )
        assert row["directRoleMatches"]["yBasisPhysicalRole"] == "worldBinormal"
        assert row["directRoleMatches"]["yBasisExactCrossHandedness"] is True
        summary = doc["summary"]
        assert summary["exactBinormalTechniqueSetCount"] == 1
        assert summary["reversedCrossTechniqueSetCount"] == 0
        assert summary["unresolvedBinormalTechniqueSetCount"] == 0
        assert summary["allThreeBasisRolesExact"] is True

        # Reversed cross is recognized algebraically but deliberately not
        # promoted to the expected T6 world-binormal convention.
        old_build = probe.v1.build
        old_load = probe._load
        old_symbolic = probe.symbolic_vertex
        try:
            probe.v1.build = lambda *args, **kwargs: base_doc
            probe._load = lambda path, name: base if "base_v2" in name else object()
            probe.symbolic_vertex = lambda shader_blob, operand, opcode: _symbolic_fixture(True)
            reversed_doc = probe.build(
                {"fixture": True},
                oat_root=root,
                paired_vs_probe_path=Path("paired.py"),
                base_verifier_path=Path("base.py"),
                opcode_path=Path("opcode.py"),
                operand_path=Path("operand.py"),
            )
        finally:
            probe.v1.build = old_build
            probe._load = old_load
            probe.symbolic_vertex = old_symbolic
        row = reversed_doc["profiles"][0]
        assert row["binormalAlgebra"]["status"] == "reversed-cross"
        assert row["directRoleMatches"]["yBasisPhysicalRole"] == "unpromoted"
        assert reversed_doc["summary"]["allThreeBasisRolesExact"] is False

        # TC1/TC3 direct physical roles remain mandatory even if a symbolic TC2
        # expression happens to match the algebra.
        broken = {
            **base_doc,
            "profiles": [{
                **base_doc["profiles"][0],
                "directRoleMatches": {
                    **base_doc["profiles"][0]["directRoleMatches"],
                    "baseIsWorldNormalFromNormal0": False,
                },
            }],
        }
        old_build = probe.v1.build
        old_load = probe._load
        try:
            probe.v1.build = lambda *args, **kwargs: broken
            probe._load = lambda path, name: base if "base_v2" in name else object()
            try:
                probe.build(
                    {"fixture": True},
                    oat_root=root,
                    paired_vs_probe_path=Path("paired.py"),
                    base_verifier_path=Path("base.py"),
                    opcode_path=Path("opcode.py"),
                    operand_path=Path("operand.py"),
                )
            except probe.LayeredNormalVsProbeV2Error as exc:
                assert "not directly proven world NORMAL0" in str(exc)
            else:
                raise AssertionError("binormal algebra was promoted without direct TC1 normal proof")
        finally:
            probe.v1.build = old_build
            probe._load = old_load

    print("PASS: generated layered-normal VS basis probe v2 exact cross/handedness gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
