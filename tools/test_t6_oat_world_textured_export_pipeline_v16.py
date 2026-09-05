#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import t6_oat_world_textured_export_pipeline_v16 as pipeline
from t6_generated_shader_recipe_contract_v1 import canonical_layer_program
from t6_glb_parse_v1 import parse_glb
from t6_world_gltf_export_v1 import glb_bytes

PS = "1" * 64
VS = "2" * 64
TECH = "lit_sm_r0c0n0_b1c1n1"


def _record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def recipe() -> dict:
    return {
        "material": "*normal_fixture",
        "techniqueSet": TECH,
        "pixelShaderArchetype": f"sha256:{PS}",
        "vertexShaderArchetype": f"sha256:{VS}",
        "worldVertFormats": [0],
        "layerProgram": canonical_layer_program(TECH),
        "proof": {"kind": "synthetic v16 orchestration"},
        "normalTransformBindingsV1": {
            "secondaryNormalBindings": [{
                "layerIndex": 1,
                "mode": "direct",
                "transformSlot": None,
                "attribute": None,
            }]
        },
        "normalTransformShaderBindingsV1": {
            "secondaryNormalBindings": [{
                "layerIndex": 1,
                "mode": "direct",
                "normalTransformIndex": None,
                "attribute": None,
            }],
            "crossProofAgreement": True,
        },
    }


def basis_proof() -> dict:
    return {
        "format": "t6-generated-layered-normal-vs-basis-probe-v2",
        "profiles": [{
            "techniqueSet": TECH,
            "vertexShaderSha256": VS,
            "pixelShaderSha256": PS,
            "directRoleMatches": {
                "baseIsWorldNormalFromNormal0": True,
                "xBasisIsWorldTangentFromTangent0": True,
                "yBasisExactCrossHandedness": True,
                "yBasisPhysicalRole": "worldBinormal",
            },
            "binormalAlgebra": {
                "status": "exact-binormal",
                "comparison": {"uniqueMatch": "cross(normal,tangent)*handedness"},
            },
        }],
        "summary": {
            "allThreeBasisRolesExact": True,
            "profilesV2Sha256": "3" * 64,
        },
    }


def base_document() -> tuple[dict, bytes]:
    raw = b"ABCD"
    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(raw)}],
        "materials": [{
            "name": "*normal_fixture",
            "extras": {"T6": {"generatedShaderRecipeV1": recipe()}},
        }],
        "extras": {"T6": {"sentinel": "v15-preserved"}},
    }
    return doc, raw


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t6_v16_") as td:
        root = Path(td)
        out = root / "out"
        out.mkdir()
        doc, raw = base_document()
        old_glb = out / "fixture.world_oat_portable_textured_v15.glb"
        old_glb.write_bytes(glb_bytes(doc, raw))
        old_manifest = out / "fixture_v15.json"
        old_manifest.write_text("{}\n", encoding="utf-8")
        proof_path = root / "basis.json"
        proof_path.write_text(json.dumps(basis_proof()), encoding="utf-8")

        original = pipeline.v15.run_oat_textured_pipeline
        try:
            pipeline.v15.run_oat_textured_pipeline = lambda **kwargs: {
                "format": "t6-oat-world-textured-export-pipeline-manifest-v15",
                "map": "fixture",
                "outputs": {"oatPortableTexturedGlb": _record(old_glb)},
                "inputs": {},
                "stats": {},
                "validation": {"v15NormalTransformCrossProofAgreementComplete": True},
                "policies": {"v15Sentinel": "preserved"},
                "manifest": _record(old_manifest),
            }
            result = pipeline.run_oat_textured_pipeline(
                map_name="fixture",
                output_dir=out,
                generated_normal_basis_proof_path=proof_path,
            )
        finally:
            pipeline.v15.run_oat_textured_pipeline = original

        assert result["format"] == pipeline.FORMAT
        assert result["validation"]["v15NormalTransformCrossProofAgreementComplete"] is True
        assert result["validation"]["v16GeneratedNormalBasisProofAttached"] is True
        assert result["validation"]["v16GeneratedNormalBasisPostpassByteIdentical"] is True
        assert result["validation"]["v16SecondaryNormalMaterialCount"] == 1
        assert result["validation"]["v16AttachedNormalBasisCount"] == 1
        assert result["validation"]["v16AllSecondaryNormalMaterialsBasisExact"] is True
        assert result["policies"]["v15Sentinel"] == "preserved"

        final_glb = Path(result["outputs"]["oatPortableTexturedGlb"]["path"])
        assert final_glb.name.endswith("_v16.glb")
        final_doc, final_raw = parse_glb(final_glb.read_bytes())
        assert final_raw == raw
        embedded = final_doc["materials"][0]["extras"]["T6"]["generatedShaderRecipeV1"]
        attachment = embedded["layeredNormalBasisV1"]
        assert attachment["vertexShaderSha256"] == VS
        assert attachment["pixelShaderSha256"] == PS
        assert attachment["directRoleMatches"]["yBasisPhysicalRole"] == "worldBinormal"
        assert final_doc["extras"]["T6"]["sentinel"] == "v15-preserved"
        assert final_doc["extras"]["T6"]["layeredNormalBasisAttachment"]["stats"]["attachedBasisCount"] == 1
        assert result["inputs"]["generatedNormalBasisProof"]["sha256"] == hashlib.sha256(proof_path.read_bytes()).hexdigest()
        assert not old_glb.exists()
        assert not old_manifest.exists()

        persisted = json.loads(Path(result["manifest"]["path"]).read_text(encoding="utf-8"))
        assert persisted["format"] == pipeline.FORMAT
        assert persisted["stats"]["generatedNormalBasisAttachment"]["attachedBasisCount"] == 1

        # Optional means absent proof preserves v15 bytes and records no false closure.
        doc2, raw2 = base_document()
        old2 = out / "fixture2.world_oat_portable_textured_v15.glb"
        old2.write_bytes(glb_bytes(doc2, raw2))
        m2 = out / "fixture2_v15.json"
        m2.write_text("{}\n", encoding="utf-8")
        before = old2.read_bytes()
        try:
            pipeline.v15.run_oat_textured_pipeline = lambda **kwargs: {
                "format": "t6-oat-world-textured-export-pipeline-manifest-v15",
                "map": "fixture2",
                "outputs": {"oatPortableTexturedGlb": _record(old2)},
                "inputs": {}, "stats": {}, "validation": {}, "policies": {},
                "manifest": _record(m2),
            }
            no_proof = pipeline.run_oat_textured_pipeline(map_name="fixture2", output_dir=out)
        finally:
            pipeline.v15.run_oat_textured_pipeline = original
        assert no_proof["validation"]["v16GeneratedNormalBasisProofAttached"] is False
        assert no_proof["validation"]["v16GeneratedNormalBasisPostpassByteIdentical"] is None
        assert Path(no_proof["outputs"]["oatPortableTexturedGlb"]["path"]).read_bytes() == before

    print("PASS: production T6 OAT pipeline v16 layered-normal basis attachment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
