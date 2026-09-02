#!/usr/bin/env python3
"""Regression for mixed direct/raw retail promotion in world vertex registry V2."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import t6_world_vertex_format_registry_v2 as registry


def baseline() -> dict:
    rows = {}
    for fmt, (name, uv, nrm, stride, fields) in registry.SPECS.items():
        proven = fmt in {0, 1, 2, 3, 6}
        rows[str(fmt)] = {
            "format": fmt, "name": name, "uvCount": uv, "normalCount": nrm,
            "vd1Stride": stride, "vd1Fields": fields,
            "retailByteProven": proven,
            "maps": ["mp_nuketown_2020"] if proven else [],
        }
    return {"format":"t6-world-vertex-format-census-v1","formats":rows,"maps":[{"map":"mp_nuketown_2020"}]}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    proof45 = json.loads((root / "manifests/world/T6_RETAIL_WORLD_FORMATS_45_PROOF_V1.json").read_text(encoding="utf-8"))
    proof7 = json.loads((root / "manifests/world/T6_RETAIL_WORLD_FORMAT_7_PROOF_V1.json").read_text(encoding="utf-8"))
    proofs = [("fmt45", proof45), ("fmt7", proof7)]
    out = registry.build_registry(baseline(), proofs, [])
    assert out["coverage"]["exportEnabledFormats"] == [0,1,2,3,4,5,6,7]
    assert out["coverage"]["pendingFormats"] == [8]
    assert out["formats"]["4"]["cleanObservedRawStrides"] == [12]
    assert out["formats"]["5"]["cleanObservedRawStrides"] == [16]
    assert out["formats"]["7"]["cleanObservedRawStrides"] == [16]
    assert out["formats"]["7"]["retailProofMaps"] == ["zm_prison","zm_tomb"]

    raw8 = {"format":"t6-world-vd1-layout-census-v1","map":"mp_format8_fixture","observedRawStrideByFormat":{"8":[20]},"blockers":[]}
    closed = registry.build_registry(baseline(), proofs, [("raw8", raw8)])
    assert closed["coverage"]["allFormatsExportEnabled"] is True
    assert closed["coverage"]["exportEnabledFormats"] == list(range(9))
    assert closed["formats"]["8"]["proofKinds"] == ["unambiguous-retail-vd1-allocation-stride"]
    assert closed["formats"]["8"]["retailProofMaps"] == ["mp_format8_fixture"]

    blocked8 = copy.deepcopy(raw8); blocked8["blockers"] = ["ambiguous allocation"]
    blocked = registry.build_registry(baseline(), proofs, [("blocked8", blocked8)])
    assert blocked["coverage"]["pendingFormats"] == [8]
    assert blocked["formats"]["8"]["rawEvidenceWithBlockers"] == ["blocked8"]

    bad8 = copy.deepcopy(raw8); bad8["observedRawStrideByFormat"]["8"] = [16]
    contradicted = registry.build_registry(baseline(), proofs, [("bad8", bad8)])
    assert contradicted["formats"]["8"]["status"] == "contradicted"
    assert contradicted["formats"]["8"]["exportEnabled"] is False

    bad45 = copy.deepcopy(proof45); bad45["maps"][0]["formats"]["4"]["rawStrides"] = [16]
    try: registry.build_registry(baseline(), [("bad45",bad45),("fmt7",proof7)], [])
    except registry.RegistryError: pass
    else: raise AssertionError("contradictory format-4 direct proof was accepted")

    bad7 = copy.deepcopy(proof7); bad7["maps"][0]["format7"]["rawStrides"] = [20]
    try: registry.build_registry(baseline(), [("fmt45",proof45),("bad7",bad7)], [])
    except registry.RegistryError: pass
    else: raise AssertionError("contradictory format-7 direct proof was accepted")

    print("PASS: T6 world vertex format registry v2")
    return 0

if __name__ == "__main__": raise SystemExit(main())
