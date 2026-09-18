#!/usr/bin/env python3
"""Regression for root-aware packed GfxImage identity trace join v2."""
from __future__ import annotations
import json,subprocess,sys,tempfile
from pathlib import Path

LINE="T6_GFXIMAGE_PACKED name={name} nameHash={nh} dataHash={dh} streamedParts=1 width={w} height={h} depth=1\n"

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        manifest=root/"manifest.json"
        manifest.write_text(json.dumps({"roots":[
          {"label":"a","filename":"a.ff","sha256":"a"*64},
          {"label":"b","filename":"b.ff","sha256":"b"*64},
        ]}))
        (root/"a_packed.txt").write_text(
          LINE.format(name="same",nh=1,dh=2,w=64,h=64)+
          LINE.format(name="conflict",nh=3,dh=4,w=32,h=32)
        )
        (root/"b_packed.txt").write_text(
          LINE.format(name="same",nh=1,dh=2,w=64,h=64)+
          LINE.format(name="conflict",nh=3,dh=5,w=32,h=32)
        )
        out=root/"out.json"
        script=Path(__file__).with_name("t6_nuketown_gfximage_packed_identity_trace_join_v2.py")
        subprocess.run([sys.executable,str(script),"--manifest",str(manifest),"--input-dir",str(root),"--out",str(out)],check=True)
        d=json.loads(out.read_text())
        s=d["summary"]
        assert s["occurrenceCount"]==4
        assert s["uniqueNameCount"]==2
        assert s["stableTupleNameCount"]==1
        assert s["conflictingTupleNameCount"]==1
        assert d["rows"]==[{
          "name":"same","nameHash":1,"dataHash":2,"streamedPartCount":1,
          "width":64,"height":64,"depth":1,"roots":["a","b"],"occurrenceCount":2,
        }]
        assert len(d["conflicts"])==1 and d["conflicts"][0]["name"]=="conflict"
        assert {x["dataHash"] for x in d["conflicts"][0]["variants"]}=={4,5}
    print("PASS t6_nuketown_gfximage_packed_identity_trace_join_v2")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
