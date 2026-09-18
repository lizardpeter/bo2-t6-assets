#!/usr/bin/env python3
"""Regression for fail-closed MP XAnim corpus aggregation."""
from __future__ import annotations
import json,subprocess,sys,tempfile
from pathlib import Path

def zone(path,name,sha,bytes_,expected,identified,closed,quat_const,quat_keyed):
    path.write_text(json.dumps({
      "format":"t6-mp-xanim-delta-branch-zone-census-v1","zone":name,
      "retailFastFile":{"bytes":bytes_,"sha256":sha},
      "expanded":{"file":name+".expanded","bytes":123,"sha256":"e"*64},
      "xassetCount":20,"expectedXAnimCount":expected,"structuralRecordCount":identified,
      "emptyPlaceholderCount":1,"countClosesExactly":closed,"inlineNames":identified,"packedNames":0,"overlaps":0,
      "branches":{"transKeyed":2,"transConstant":1,"quat2Keyed":3,"quat2Constant":4,"quatKeyed":quat_keyed,"quatConstant":quat_const},
      "constantFullQuat":[],"dynamicFullQuatCount":quat_keyed,"dynamicFullQuatExamples":[]
    }))

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); proofs=root/"proofs"; proofs.mkdir()
        maps=[
          {"zone":"a","path":"zone/all/a.ff","bytes":100,"sha256":"a"*64},
          {"zone":"b","path":"zone/all/b.ff","bytes":200,"sha256":"b"*64},
          {"zone":"c","path":"zone/all/c.ff","bytes":300,"sha256":"c"*64},
        ]
        targets=root/"targets.json"; targets.write_text(json.dumps({"format":"t6-retail-mp-world-format-targets-v1","maps":maps}))
        zone(proofs/"a.json","a","a"*64,100,10,10,True,0,1)
        zone(proofs/"b.json","b","b"*64,200,12,11,False,9,7)
        out=root/"out.json"
        script=Path(__file__).with_name("t6_mp_xanim_delta_branch_corpus_v1.py")
        subprocess.run([sys.executable,str(script),"--targets",str(targets),"--proof-dir",str(proofs),"--out",str(out)],check=True)
        d=json.loads(out.read_text()); s=d["summary"]
        assert s["targetMapCount"]==3 and s["mapsScanned"]==2
        assert s["mapsCountClosed"]==1 and s["mapsPartial"]==1 and s["mapsUnscanned"]==1
        assert s["exactCountXAnimRecords"]==10
        assert s["constantFullQuatObservedInExactCountMaps"]==0
        assert s["dynamicFullQuatObservedInExactCountMaps"]==1
        assert s["exactCountBranchTotals"]["quatConstant"]==0
        assert d["unscannedMaps"]==["c"]
        assert d["partialMaps"]==[{"zone":"b","expected":12,"identified":11}]
    print("PASS t6_mp_xanim_delta_branch_corpus_v1")
    return 0
if __name__=="__main__": raise SystemExit(main())
