#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile
from pathlib import Path
import t6_oat_layered_component_texture_recovery_v2 as r

def tex(image, semantic, name=None, mip="nearest", mature=False):
    return {"name": name or semantic, "semantic": semantic, "image": image,
            "samplerState": {"filter":"linear","mipMap":mip,"clampU":False,"clampV":False,"clampW":False},
            "isMatureContent": mature}

def write(root, identity, textures):
    p=root/f"{identity}.json"; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"_game":"t6","_type":"material","_version":1,"techniqueSet":"test","textures":textures}))

def catalog(names):
    return {"format":"t6-world-surface-material-catalog-source-v3-legacy-index-v1","map":"synthetic","materials":[{"index":i,"name":n} for i,n in enumerate(names)]}

def main():
    known=[tex("known_mature_c","colorMap",mature=False)]
    missing_n=[tex("missing_n","normalMap"),tex("missing_c","colorMap")]
    missing_c=[tex("overlay_c","colorMap")]
    g1="*1_2n(wpc/known:wpc/missing_normal)"; g2="*2n_3_3(wpc/missing_normal:wpc/missing_color:wpc/missing_color)"
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); write(root,"wpc/known",known)
        write(root,"generated/_1_2n",r.project(known,0)+r.project(missing_n,1))
        write(root,"generated/_2n_3_3",r.project(missing_n,0)+r.project(missing_c,1)+r.project(missing_c,2))
        d=r.build_recovery(material_root=root,catalog_doc=catalog([g1,g2]),targets=["wpc/missing_normal","wpc/missing_color"])
        assert d["format"]=="t6-oat-layered-component-texture-recovery-v2"
        assert d["summary"]=={"targetCount":2,"recoveredTargetCount":2,"standaloneMissingComponentCount":2,"generatedCatalogMaterialCount":2,"allGeneratedExactReconstructionCount":2,"targetBearingGeneratedMaterialCount":2,"targetGeneratedLayerOccurrenceCount":4}
        rows={x["identity"]:x for x in d["components"]}
        n=rows["wpc/missing_normal"]; c=rows["wpc/missing_color"]
        expected_n=[r.unsuffix_row(x,1)[0] for x in r.project(missing_n,1)]
        expected_c=[r.unsuffix_row(x,1)[0] for x in r.project(missing_c,1)]
        assert n["textures"]==expected_n and c["textures"]==expected_c
        assert n["sourceStandaloneTextureTableRecovered"] is False
        assert all(x["samplerState"]["mipMap"]=="linear" for x in n["textures"]+c["textures"])
        assert r.project(known,0)[0]["isMatureContent"] is True
        assert c["generatedLayerOccurrenceCount"]==2 and c["recoveryEvidence"][0]["unknownLayerPositions"]==[1,2]
        write(root,"wpc/missing_color",missing_c)
        try: r.build_recovery(material_root=root,catalog_doc=catalog([g1,g2]),targets=["wpc/missing_normal","wpc/missing_color"])
        except r.RecoveryError as e: assert "unexpectedly have standalone" in str(e)
        else: raise AssertionError("standalone target was not rejected")
    print("PASS: exact source-defined layered projection, runtime canonical recovery, repeated-layer agreement, and fail-closed standalone rejection")
    return 0
if __name__=="__main__": raise SystemExit(main())
