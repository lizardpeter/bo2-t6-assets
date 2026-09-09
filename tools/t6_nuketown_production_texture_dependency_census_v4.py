#!/usr/bin/env python3
"""Nuketown production texture dependency census v4.

v4 retains the exact v7 Material admission and 81-IWI bridge accounting from v3,
then admits the independently source-closed inline FastFile $identitynormalmap as
a second exact image authority. It never treats that inline image as an IPAK/DDS
hit and it never resolves any other missing identity by name or similarity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from t6_nuketown_production_texture_dependency_census_v1 import load, sha256
from t6_nuketown_production_texture_dependency_census_v2 import CensusError
from t6_nuketown_production_texture_dependency_census_v3 import build as build_v3

FORMAT = "t6-nuketown-production-texture-dependency-census-v4"
IDENTITY_NAME = "$identitynormalmap"
IDENTITY_PROOF_FORMAT = "t6-nuketown-identitynormalmap-block5-proof-v1"
IDENTITY_SOURCE_SHA = "7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505"
IDENTITY_RGBA = [128, 128, 255, 128]


def validate_identity_proof(doc: dict) -> dict:
    if doc.get("format") != IDENTITY_PROOF_FORMAT or doc.get("status") != "closed":
        raise CensusError("identitynormal proof is not the closed v1 proof")
    source = doc.get("source") or {}
    if source.get("sha256") != IDENTITY_SOURCE_SHA or int(source.get("bytes", -1)) != 154653476:
        raise CensusError("identitynormal proof retail source identity drift")
    promotion = doc.get("promotion") or {}
    expected = {
        "block": 5,
        "virtualOffset": 514620,
        "image": IDENTITY_NAME,
        "semantic": 5,
        "textureSlot": 1,
        "xassetIndex": 836,
        "xassetType": "IMAGE",
    }
    for key, value in expected.items():
        if promotion.get(key) != value:
            raise CensusError(f"identitynormal proof drift: {key}={promotion.get(key)!r}, expected {value!r}")
    image = doc.get("identityImage") or {}
    if image.get("name") != IDENTITY_NAME or image.get("loadDefPointer") != "0xFFFFFFFE":
        raise CensusError("identitynormal inline GfxImage identity drift")
    if int(image.get("resourceSize", -1)) != 4:
        raise CensusError("identitynormal inline resource is not the exact 4-byte pixel")
    control = doc.get("alignmentControl") or {}
    if int(control.get("correctSlot1VirtualOffset", -1)) != 514620 or int(control.get("deltaBytes", -1)) != 16:
        raise CensusError("identitynormal loader-alignment control drift")
    return {
        "image": IDENTITY_NAME,
        "authority": "exact-inline-fastfile-gfximage",
        "source": "mp_nuketown_2020.expanded.bin",
        "sourceSha256": IDENTITY_SOURCE_SHA,
        "block": 5,
        "virtualOffset": 514620,
        "xassetIndex": 836,
        "resourceSize": 4,
        "rgba": IDENTITY_RGBA,
    }


def build(material_doc: dict, bridge_doc: dict, identity_proof_doc: dict,
          lightmap_doc: dict | None, reflection_doc: dict | None) -> dict:
    doc = build_v3(material_doc, bridge_doc, lightmap_doc, reflection_doc)
    inline = validate_identity_proof(identity_proof_doc)

    missing = doc.get("missingProductionImages") or []
    matches = [row for row in missing if row.get("image") == IDENTITY_NAME]
    if len(matches) != 1:
        raise CensusError(
            f"expected exactly one bridge-missing {IDENTITY_NAME!r} dependency row, found {len(matches)}"
        )
    identity_missing_row = matches[0]
    uses = identity_missing_row.get("materialUses") or []
    if len(uses) != 87:
        raise CensusError(f"{IDENTITY_NAME}: Material use count {len(uses)}, expected 87")
    if identity_missing_row.get("lightmapUses") or identity_missing_row.get("reflectionProbeUses"):
        raise CensusError(f"{IDENTITY_NAME}: unexpected non-Material production use in current census")

    for row in doc.get("material") or []:
        if row.get("image") == IDENTITY_NAME:
            if row.get("coveredByExact81DdsBridge") is not False or row.get("bridgeDds") is not None:
                raise CensusError("identitynormal unexpectedly appears in exact 81 DDS bridge")
            row["coveredByExactInlineFastFileImage"] = True
            row["inlineFastFileImage"] = inline
            row["coveredByKnownExactSource"] = True
        else:
            row["coveredByExactInlineFastFileImage"] = False
            row["inlineFastFileImage"] = None
            row["coveredByKnownExactSource"] = bool(row.get("coveredByExact81DdsBridge"))

    doc["missingProductionImagesBridgeOnly"] = missing
    doc["missingProductionImages"] = [row for row in missing if row.get("image") != IDENTITY_NAME]
    doc["exactInlineFastFileImages"] = [inline]

    s = doc["summary"]
    if s.get("materialUniqueImageCount") != 423 or s.get("materialCoveredByExact81Count") != 75:
        raise CensusError(f"unexpected v3 bridge-only baseline {s}")
    if s.get("materialMissingFromExact81Count") != 348:
        raise CensusError(f"unexpected v3 bridge-only missing count {s.get('materialMissingFromExact81Count')}")
    s.update({
        "exactInlineFastFileImageCount": 1,
        "materialCoveredByExactInlineFastFileCount": 1,
        "materialCoveredByKnownExactSourceCount": 76,
        "materialMissingFromKnownExactSourceCount": 347,
        "productionCoveredByKnownExactSourceCount": 76,
        "productionMissingFromKnownExactSourceCount": 347,
        "knownExactSourceCoverageRatio": 76 / 423,
    })
    doc["format"] = FORMAT
    doc["previousFormat"] = "t6-nuketown-production-texture-dependency-census-v3"
    doc["proofBoundary"] = (
        doc["proofBoundary"] + " In addition, only $identitynormalmap is admitted from the independent closed block-5/514620 "
        "FastFile GfxImage proof as the exact inline RGBA [128,128,255,128] resource. It remains explicitly separate from the "
        "81-image IPAK/DDS bridge. No other bridge-missing identity is promoted by naming, role, dimensions, or resemblance."
    )
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--material-manifest", type=Path, required=True)
    ap.add_argument("--dds-bridge", type=Path, required=True)
    ap.add_argument("--identitynormal-proof", type=Path, required=True)
    ap.add_argument("--lightmap-catalog", type=Path)
    ap.add_argument("--reflection-catalog", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    material_doc, material_raw = load(args.material_manifest)
    bridge_doc, bridge_raw = load(args.dds_bridge)
    identity_doc, identity_raw = load(args.identitynormal_proof)
    lightmap_doc = lightmap_raw = None
    reflection_doc = reflection_raw = None
    if args.lightmap_catalog:
        lightmap_doc, lightmap_raw = load(args.lightmap_catalog)
    if args.reflection_catalog:
        reflection_doc, reflection_raw = load(args.reflection_catalog)

    doc = build(material_doc, bridge_doc, identity_doc, lightmap_doc, reflection_doc)
    doc["inputs"] = {
        "materialManifest": {"path": str(args.material_manifest), "bytes": len(material_raw), "sha256": sha256(material_raw)},
        "ddsBridge": {"path": str(args.dds_bridge), "bytes": len(bridge_raw), "sha256": sha256(bridge_raw)},
        "identitynormalProof": {"path": str(args.identitynormal_proof), "bytes": len(identity_raw), "sha256": sha256(identity_raw)},
        "lightmapCatalog": None if lightmap_raw is None else {"path": str(args.lightmap_catalog), "bytes": len(lightmap_raw), "sha256": sha256(lightmap_raw)},
        "reflectionCatalog": None if reflection_raw is None else {"path": str(args.reflection_catalog), "bytes": len(reflection_raw), "sha256": sha256(reflection_raw)},
    }
    payload = (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(json.dumps({"out": str(args.out), "bytes": len(payload), "sha256": sha256(payload), **doc["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
