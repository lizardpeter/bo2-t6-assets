#!/usr/bin/env python3
"""Static regression for the one-command source-derived SEAL6 rebuild."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "t6_rebuild_seal6_full_retail_v1.ps1"

FACTION_RAW = "1a0754a5183eca3b1169610ad61b369768617340d000ef730a0d5c7b9ea97c88"
FACTION_EXPANDED = "21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30"
COMMON_EXPANDED = "fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce"
ANIMS = {
    "pb_stand_alert": (662933, 383, "5b939762cc76bb79674c2fc0d6ffd4c9460acd555ad2368aeaf45b52d80ad8b3"),
    "pb_stand_ads": (655915, 90, "6900419e6ea5cd43fa3cd2c9384e1862cff2c73e86e5df7db8ea4f41ef961c2c"),
    "pb_smg_sprint": (5203838, 46, "4824cc8f8fbda4c303dafd783034a1dc7e56d81dcbaffbaea88fafbf6bef7ac6"),
    "pb_combatrun_forward_loop": (5670677, 50, "091a8ff01a0e0a66fc19632fec483207ae565764c8f7c268208ab2facb92dd36"),
    "pb_standjump_takeoff": (10693310, 27, "53efd36cd2caa35613b255d7dfd29a185347a82f65f72eff5b567396734340b0"),
    "pt_stand_shoot_auto": (7851319, 18, "ee1d1b126359187212f7b249a38cb06a73b9cce2afcbad09d1d235f1ece2a08e"),
}


def main() -> int:
    text = SCRIPT.read_text(encoding="utf-8")
    required = [
        "[Parameter(Mandatory=$true)][string]$FactionSealsFastfile",
        "[Parameter(Mandatory=$true)][string]$CommonMpFastfile",
        "[Parameter(Mandatory=$true)][string]$BaseIpak",
        "[Parameter(Mandatory=$true)][string]$MpIpak",
        "bo2_t6_fastfile.py",
        '"decrypt"',
        "t6_xmodel_skeleton_normalize_v3.py",
        "t6_xmodel_mesh_normalize_v4.py",
        "t6_xanim_normalize_v1.py",
        "t6_build_seal6_smg_textured_animated_all_lods_v3.ps1",
        FACTION_RAW,
        FACTION_EXPANDED,
        COMMON_EXPANDED,
        'TargetAssetStart = "0x45CCF1"',
        "TargetXAssetIndex = 213",
        "topLevelSurfsAliasProven",
        'reuseProof.mode -ne "exact-packed-top-level-XModel.surfs-alias"',
        "Mesh.summary.vertices -ne 21188",
        "Mesh.summary.triangles -ne 21283",
        "assetSerializedSha256",
        "allFlatPoolsExhausted",
        "SEAL6_FULL_RETAIL_BLENDER.zip",
        "t6-seal6-full-retail-rebuild-v1",
    ]
    missing = [x for x in required if x not in text]
    assert not missing, f"raw rebuild script missing required contract tokens: {missing}"

    for name, (start, frames, digest) in ANIMS.items():
        assert name in text
        assert f"start={start}" in text
        assert f"frames={frames}" in text
        assert digest in text

    # The retained common_mp source has conflicting historical raw-container
    # identities, so this build must promote it only after exact expanded-byte
    # verification. A hard-coded raw common SHA here would silently choose one
    # source package and weaken the actual semantic source boundary.
    assert "CommonRawSha256 = Get-Sha256" in text
    assert "Assert-FileIdentity $CommonMpFastfile" not in text
    assert "Assert-FileIdentity $CommonExpanded $CommonExpandedBytes $CommonExpandedSha256" in text

    # Never regress to old model normalizers or single-IPAK packaging.
    assert "t6_xmodel_mesh_normalize_v1.py" not in text
    assert "t6_xmodel_skeleton_normalize_v1.py" not in text
    assert re.search(r"-BaseIpak\s+\$BaseIpak\s+-MpIpak\s+\$MpIpak", text)

    print("PASS: raw-retail SEAL6 rebuild contract v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
