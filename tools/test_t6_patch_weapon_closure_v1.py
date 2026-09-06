#!/usr/bin/env python3
import importlib.util
import json
import tempfile
from pathlib import Path

P = Path(__file__).with_name("t6_patch_weapon_closure_v1.py")
spec = importlib.util.spec_from_file_location("closure", P)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def exact_probe(name="fixture_weapon_mp", weaponclass="smg", player_anim="handleclip"):
    return {
        "front": {"assetCount": 1764, "weaponAssetCount": 1},
        "bindings": [{
            "status": "exact-by-single-inline-weapon-cardinality",
            "assetIndex": 100,
            "weaponVariantDef": {
                "internalName": name,
                "internalNameStatus": "exact-packed-front-xstring",
                "rawStructOffset": 1234,
                "rawFixedSha256": "11" * 32,
                "selector": {
                    "status": "exact-direct-weapdef-prefix",
                    "rawOffset": 1950,
                    "rawPrefixSha256": "22" * 32,
                    "weaponClass": weaponclass,
                    "playerAnimType": player_anim,
                    "weaponType": "bullet",
                    "fireType": "Full Auto",
                    "selector": {"weaponclass": weaponclass, "playerAnimType": player_anim},
                },
            },
        }],
    }


# Exact structural closure.
r = mod.evaluate_probe_result(exact_probe())
assert r["status"] == "exact", r
assert r["weapon"] == "fixture_weapon_mp", r
assert r["selector"] == {"weaponclass": "smg", "playerAnimType": "handleclip"}, r
layer = mod.build_selector_layer(r, {"expandedSha256": "aa" * 32, "expandedBytes": 14713756})
assert layer["format"] == "t6-weapon-playeranim-selector-layer-v1", layer
row = layer["weapons"][0]
assert row["weapon"] == "fixture_weapon_mp", row
assert row["selectorStatus"] == "exact", row
assert row["structuralSelectorStatus"] == "exact-direct-weapdef-prefix", row

# Unresolved packed name stays blocked even with an exact selector.
p = exact_probe()
wvd = p["bindings"][0]["weaponVariantDef"]
wvd["internalName"] = None
wvd["internalNameStatus"] = "unresolved-packed-name-pointer"
wvd["packedInternalNameResolution"] = {"status": "later-virtual-allocation"}
r2 = mod.evaluate_probe_result(p)
assert r2["status"] == "blocked", r2
assert r2["blocker"]["code"] == "internal-name-unresolved", r2
assert r2["blocker"]["packedResolution"]["status"] == "later-virtual-allocation", r2

# Multiple exact bindings are never ranked or guessed.
p = exact_probe()
p["bindings"].append(json.loads(json.dumps(p["bindings"][0])))
r3 = mod.evaluate_probe_result(p)
assert r3["status"] == "blocked", r3
assert r3["blocker"]["code"] == "cardinality-binding-not-unique", r3

# Selector must itself be exact.
p = exact_probe()
p["bindings"][0]["weaponVariantDef"]["selector"]["status"] = "unresolved-packed-weapdef-pointer"
r4 = mod.evaluate_probe_result(p)
assert r4["status"] == "blocked", r4
assert r4["blocker"]["code"] == "selector-unresolved", r4

# Retained XAsset / WEAPON cardinalities are mandatory.
p = exact_probe()
p["front"]["assetCount"] = 1763
r5 = mod.evaluate_probe_result(p)
assert r5["status"] == "blocked", r5
assert r5["blocker"]["code"] == "asset-count-mismatch", r5
p = exact_probe()
p["front"]["weaponAssetCount"] = 2
r6 = mod.evaluate_probe_result(p)
assert r6["status"] == "blocked", r6
assert r6["blocker"]["code"] == "weapon-count-mismatch", r6

# Promotion edits only the patch_mp selectorManifest and unknown count.
spec_in = {
    "format": "fixture-precedence-spec",
    "other": {"keep": [1, 2, 3]},
    "layers": [
        {"name": "common_mp", "selectorManifest": "common.json", "unknownWeaponAssetCount": 0, "sourceSha256": "c"},
        {"name": "common_patch_mp", "selectorManifest": "common_patch.json", "unknownWeaponAssetCount": 0, "overrideNamesCsv": "overrides.csv"},
        {"name": "patch_mp", "selectorManifest": None, "unknownWeaponAssetCount": 1, "sourceSha256": "p", "keep": "yes"},
    ],
}
promoted = mod.promote_patch_layer_in_spec(spec_in, "generated/patch.json")
assert spec_in["layers"][2]["unknownWeaponAssetCount"] == 1, "input was mutated"
assert promoted["layers"][0] == spec_in["layers"][0], promoted
assert promoted["layers"][1] == spec_in["layers"][1], promoted
assert promoted["other"] == spec_in["other"], promoted
assert promoted["layers"][2] == {
    "name": "patch_mp",
    "selectorManifest": "generated/patch.json",
    "unknownWeaponAssetCount": 0,
    "sourceSha256": "p",
    "keep": "yes",
}, promoted["layers"][2]

# A noncanonical prior unknown count is rejected rather than silently normalized.
bad_spec = json.loads(json.dumps(spec_in))
bad_spec["layers"][2]["unknownWeaponAssetCount"] = 2
try:
    mod.promote_patch_layer_in_spec(bad_spec, "x.json")
    raise AssertionError("expected unknown count mismatch to fail")
except ValueError as e:
    assert "expected unknownWeaponAssetCount=1" in str(e), e

# Exact artifact verification checks both size and SHA.
with tempfile.TemporaryDirectory() as td:
    path = Path(td) / "x.bin"
    path.write_bytes(b"abc")
    sha = mod.sha256_path(path)
    proof = mod.verify_artifact(path, 3, sha, "fixture")
    assert proof["exact"] is True, proof
    try:
        mod.verify_artifact(path, 4, sha, "fixture")
        raise AssertionError("expected size mismatch")
    except ValueError:
        pass
    try:
        mod.verify_artifact(path, 3, "00" * 32, "fixture")
        raise AssertionError("expected hash mismatch")
    except ValueError:
        pass

print("test_t6_patch_weapon_closure_v1: PASS")
