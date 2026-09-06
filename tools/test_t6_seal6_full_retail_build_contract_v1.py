#!/usr/bin/env python3
"""Static fail-closed regressions for the exact SEAL6 full-retail build path."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETAIL = ROOT / "manifests" / "nonmap" / "retail"
WRAPPER = ROOT / "scripts" / "t6_build_seal6_smg_textured_animated_all_lods_v3.ps1"
CONTRACT = RETAIL / "seal6_smg_multi_ipak_resolution_contract_v1.json"
GOLDEN = RETAIL / "seal6_smg_golden_asset_proof_v1.json"

BASE_SHA = "6c3e68f846fd8ae7bc0bc1adfbeff642d5c8e3ecfc4bd9be3a880f452144fa02"
MP_SHA = "f97404b9bf5a4410ecd298e62a5cdbb3f9d5630b226d885310033842930632a5"
OLD_STALE_BASE_SHA = "6c3e68f856f0eafb54aef193b96464b313617f11653f75d1d3fa03f01125fa02"
REFERENCE_GLB_SHA = "c83d2f14d121dc4e6ffad0a11ff6f1517c7e7274ba480cbd528ee45543290008"


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["format"] == "t6-seal6-smg-multi-ipak-resolution-contract-v1"
    assert contract["repositories"]["base.ipak"]["sha256"] == BASE_SHA
    assert contract["repositories"]["mp.ipak"]["sha256"] == MP_SHA
    assert contract["summary"]["requestedTextures"] == 42
    assert contract["summary"]["expectedMaterializedTextures"] == 42
    assert contract["summary"]["expectedUnresolvedTextures"] == 0
    assert contract["summary"]["expectedAmbiguousTextures"] == 0
    assert contract["summary"]["expectedRepositoryCounts"] == {"base.ipak": 40, "mp.ipak": 2}

    mp = contract["mpIpakExceptionsToHistoricalV4RepositoryLabel"]
    assert len(mp) == 2
    assert {row["image"] for row in mp} == {
        "~-gc_usa_milcas_mcknight_head_camo_c",
        "~-gc_usa_mp_seal6_vest_1_c",
    }
    keyed = {row["image"]: (row["derivedFilenameHashHex"], row["dataHashHex"]) for row in mp}
    assert keyed["~-gc_usa_milcas_mcknight_head_camo_c"] == ("0xd5fa4a3b", "0x0e73f12d")
    assert keyed["~-gc_usa_mp_seal6_vest_1_c"] == ("0xe3737726", "0x14c7d31c")
    assert all(row["repository"] == "mp.ipak" for row in mp)

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    sources = {row["id"]: row for row in golden["sources"]}
    assert sources["base-ipak"]["sha256"] == BASE_SHA
    assert sources["mp-ipak"]["sha256"] == MP_SHA
    assert len(sources) == 4
    inv = golden["invariants"]
    assert (inv["surfaces"], inv["vertices"], inv["triangles"]) == (14, 13490, 14968)
    assert (inv["joints"], inv["materials"], inv["fps"]) == (102, 12, 30)
    assert inv["textureResolutionContract"] == {
        "requested": 42, "base.ipak": 40, "mp.ipak": 2, "unresolved": 0, "ambiguous": 0
    }
    output = golden["outputs"][0]
    assert output["sha256"] == REFERENCE_GLB_SHA
    assert output["bytes"] == 1663080

    text = WRAPPER.read_text(encoding="utf-8")
    required = [
        "[string]$BaseIpak",
        "[string]$MpIpak",
        BASE_SHA,
        MP_SHA,
        "t6_ipak_iwi_materialize_v3.py",
        '"--ipak","base.ipak=$BaseIpak"',
        '"--ipak","mp.ipak=$MpIpak"',
        '"--expect-ipak-sha256","base.ipak=$ExpectedBaseIpakSha256"',
        '"--expect-ipak-sha256","mp.ipak=$ExpectedMpIpakSha256"',
        "seal6_smg_multi_ipak_resolution_contract_v1.json",
        "Expected exact repository split base.ipak=40 mp.ipak=2",
        "SEAL6_FULL_RETAIL_BLENDER.zip",
        "serializedSurfaces=42",
        "verticesAcrossSerializedSurfaces=21188",
        "trianglesAcrossSerializedSurfaces=21283",
        "joints=102",
        "benchmarkAnimations=6",
        "exactTexturePayloads=42",
        "baseIpakTextures=40",
        "mpIpakTextures=2",
    ]
    missing = [token for token in required if token not in text]
    assert not missing, f"V3 wrapper missing contract tokens: {missing}"
    assert "t6_ipak_iwi_materialize_v2.py" not in text
    assert OLD_STALE_BASE_SHA not in text
    assert 'header.numframes' in text
    assert 'header.framerate' in text

    print("PASS: SEAL6 full-retail multi-IPAK build contract v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
