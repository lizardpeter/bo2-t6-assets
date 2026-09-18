#!/usr/bin/env python3
"""Regression for exact typed Nuketown dynamic-XAsset reference join."""
from __future__ import annotations
import json,subprocess,sys,tempfile
from pathlib import Path

def binding(path, rows):
    path.write_text(json.dumps({
      "format":"t6-oat-all-xasset-ordinal-name-binding-v1",
      "expandedSha256":"a"*64,
      "xassetCount":len(rows),
      "rows":[
        {"assetTypeName":t,"nativeResolvedName":n,"xassetIndex":i,
         "rawXAssetPointer":f"0x{i+1:08X}","tableSourceOffset":100+i*8}
        for i,(t,n) in enumerate(rows)
      ]
    }))

def main():
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        census={
          "format":"t6-mapents-model-animation-census-v1","map":"mp_test",
          "relevantEntities":[
            {"entityIndex":1,"model":"model_a","destructibledef":"dest_a",
             "pairs":[["model","model_a"],["destructibledef","dest_a"],["fxanim_fx_1","fx_a"],["fxanim_fx_1_tag","tag"]]},
            {"entityIndex":2,"model":"model_b","destructibledef":None,
             "pairs":[["model","model_b"]]},
            {"entityIndex":3,"model":"*17","destructibledef":None,
             "pairs":[["model","*17"]]},
          ]
        }
        mp=d/"mapents.json"; mp.write_text(json.dumps(census))
        b1=d/"r1.json"; binding(b1,[("XMODEL","model_a"),("DESTRUCTIBLEDEF","dest_a"),("FX","fx_a"),("FX","model_b")])
        b2=d/"r2.json"; binding(b2,[("XMODEL","model_a")])
        out=d/"out.json"
        script=Path(__file__).with_name("t6_nuketown_dynamic_xasset_reference_closure_v1.py")
        subprocess.run([sys.executable,str(script),"--mapents",str(mp),"--binding","map",str(b1),"--binding","patch",str(b2),"--out",str(out)],check=True)
        x=json.loads(out.read_text()); s=x["summary"]
        assert s["referenceIdentityCount"]==5
        assert s["resolved"]==3 and s["absentFromSuppliedRoots"]==1
        assert s["inlineBrushModelTokenCount"]==1
        assert s["byKind"]["model"]=={
          "referenceIdentityCount":3,
          "resolved":1,
          "absentFromSuppliedRoots":1,
          "inlineBrushModelTokenCount":1,
        }
        by={(r["expectedAssetType"],r["name"]):r for r in x["rows"]}
        assert len(by[("XMODEL","model_a")]["matches"])==2
        assert by[("XMODEL","model_b")]["status"]=="absent-from-supplied-roots"
        assert by[("XMODEL","model_b")]["sameNameOtherAssetTypes"]==["FX"]
        assert by[("XMODEL","*17")]["status"]=="inline-brush-model-token"
        assert by[("XMODEL","*17")]["inlineBrushModelIndex"]==17
        assert by[("XMODEL","*17")]["matches"]==[]
        assert by[("FX","fx_a")]["sourceKeys"]==["fxanim_fx_1"]
        assert "fxanim_fx_1_tag" not in by[("FX","fx_a")]["sourceKeys"]
    print("PASS t6_nuketown_dynamic_xasset_reference_closure_v1")
    return 0
if __name__=="__main__": raise SystemExit(main())
