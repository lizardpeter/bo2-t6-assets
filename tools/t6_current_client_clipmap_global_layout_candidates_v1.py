#!/usr/bin/env python3
"""Locate current-client global clipMap layout candidates by exact field offsets.

This is a structural locator, not a symbol assignment. It scans absolute x86
memory operands and asks whether many referenced addresses can be explained by
one base plus independently fixed T6 PC32 clipMap_t offsets. Candidates are
ranked by distinct matched fields; the three discriminating landmarks
numSubModels(+0x90), cmodels(+0x94), and mapEnts(+0xA8) are retained explicitly.

No candidate is called 'cm' or used as semantic proof until a later projector
validates the consumer dataflow.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86 import X86_OP_MEM

SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
FORMAT="t6-current-client-clipmap-global-layout-candidates-v1"
FIELDS={
  0:"name",4:"isInUse",8:"info.planeCount",12:"info.planes",
  80:"pInfo",84:"numStaticModels",88:"staticModelList",92:"numNodes",96:"nodes",
  100:"numLeafs",104:"leafs",108:"vertCount",112:"verts",116:"triCount",120:"triIndices",
  124:"triEdgeIsWalkable",128:"partitionCount",132:"partitions",136:"aabbTreeCount",140:"aabbTrees",
  144:"numSubModels",148:"cmodels",152:"numClusters",156:"clusterBytes",160:"visibility",164:"vised",
  168:"mapEnts",172:"box_brush",252:"originalDynEntCount",254:"dynEntCount0",256:"dynEntCount1",
  258:"dynEntCount2",260:"dynEntCount3",264:"dynEntDefList0",268:"dynEntDefList1",
  272:"dynEntPoseList0",276:"dynEntPoseList1",280:"dynEntClientList0",284:"dynEntClientList1",
  288:"dynEntServerList0",292:"dynEntServerList1",296:"dynEntCollList0",300:"dynEntCollList1",
  304:"dynEntCollList2",308:"dynEntCollList3",312:"num_constraints",316:"constraints",
  320:"max_ropes",324:"ropes",328:"checksum"
}
LANDMARKS={144:"numSubModels",148:"cmodels",168:"mapEnts"}

class E(RuntimeError):pass
def req(c,m):
    if not c:raise E(m)
def pe(raw):
    p=struct.unpack_from("<I",raw,0x3c)[0];req(raw[p:p+4]==b"PE\0\0","bad PE")
    coff=p+4;n=struct.unpack_from("<H",raw,coff+2)[0];optsz=struct.unpack_from("<H",raw,coff+16)[0]
    opt=coff+20;ib=struct.unpack_from("<I",raw,opt+28)[0];size_img=struct.unpack_from("<I",raw,opt+56)[0];so=opt+optsz;secs=[]
    for i in range(n):
      q=so+i*40;name=raw[q:q+8].split(b"\0",1)[0].decode("ascii","replace")
      vs,rva,rs,ro=struct.unpack_from("<IIII",raw,q+8);ch=struct.unpack_from("<I",raw,q+36)[0]
      secs.append({"name":name,"va":ib+rva,"virtualSize":vs,"rawSize":rs,"rawOffset":ro,"exec":bool(ch&0x20000000)})
    return ib,size_img,secs
def row(i):return {"address":f"0x{i.address:08x}","bytes":i.bytes.hex(),"mnemonic":i.mnemonic,"opStr":i.op_str}
def in_image(base,ib,size):return ib<=base<ib+size
def main():
    ap=argparse.ArgumentParser();ap.add_argument("exe",type=Path);ap.add_argument("--revision",required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    raw=a.exe.read_bytes();dg=hashlib.sha256(raw).hexdigest();req(dg==SHA,f"SHA drift {dg}")
    ib,size_img,secs=pe(raw);md=Cs(CS_ARCH_X86,CS_MODE_32);md.detail=True;md.skipdata=True
    refs=[];section_ins={}
    for s in secs:
      if not s["exec"]:continue
      blob=raw[s["rawOffset"]:s["rawOffset"]+s["rawSize"]];ins=list(md.disasm(blob,s["va"]));section_ins[s["name"]]=ins
      for n,i in enumerate(ins):
        if i.id==0:continue
        for op in i.operands:
          if op.type!=X86_OP_MEM or op.mem.base!=0 or op.mem.index!=0:continue
          addr=int(op.mem.disp)&0xffffffff
          if not in_image(addr,ib,size_img):continue
          refs.append({"absoluteVa":addr,"section":s["name"],"instructionIndex":n,"instruction":row(i)})
    by_abs=collections.defaultdict(list)
    for r in refs:by_abs[r["absoluteVa"]].append(r)
    cand=collections.defaultdict(set)
    for absva in by_abs:
      for off in FIELDS:
        base=absva-off
        if in_image(base,ib,size_img):cand[base].add(off)
    scored=[]
    for base,offs in cand.items():
      landmarks=sorted(set(offs)&set(LANDMARKS))
      if len(offs)<5 and len(landmarks)<2:continue
      field_rows=[]
      for off in sorted(offs):
        absva=base+off
        uses=[]
        for r in by_abs.get(absva,[]):
          ins=section_ins[r["section"]];n=r["instructionIndex"]
          uses.append({
            "instruction":r["instruction"],
            "contextBefore":[row(x) for x in ins[max(0,n-5):n]],
            "contextAfter":[row(x) for x in ins[n+1:min(len(ins),n+6)]],
          })
        field_rows.append({"offset":off,"offsetHex":f"0x{off:x}","field":FIELDS[off],
                           "absoluteVa":f"0x{absva:08x}","referenceCount":len(uses),"uses":uses})
      scored.append({
        "baseVa":f"0x{base:08x}","distinctMatchedFieldCount":len(offs),
        "totalAbsoluteReferenceCount":sum(len(by_abs[base+o]) for o in offs),
        "landmarkOffsets":[{"offset":o,"field":LANDMARKS[o]} for o in landmarks],
        "allThreeLandmarksMatched":len(landmarks)==3,
        "fields":field_rows,
      })
    scored.sort(key=lambda x:(not x["allThreeLandmarksMatched"],-x["distinctMatchedFieldCount"],-x["totalAbsoluteReferenceCount"],x["baseVa"]))
    top=scored[:30]
    summary={
      "absoluteImageMemoryOperandCount":len(refs),
      "candidateCountRetained":len(top),
      "allThreeLandmarkCandidateCount":sum(x["allThreeLandmarksMatched"] for x in top),
      "maxDistinctMatchedFieldCount":max((x["distinctMatchedFieldCount"] for x in top),default=0),
      "maxTotalAbsoluteReferenceCount":max((x["totalAbsoluteReferenceCount"] for x in top),default=0),
    }
    doc={"format":FORMAT,"authority":"SHA-classified current-client absolute memory operands + independently fixed T6 PC32 clipMap_t field offsets",
      "client":{"revision":a.revision,"bytes":len(raw),"sha256":dg,"imageBaseHex":f"0x{ib:08x}","imageSize":size_img},
      "fieldOffsets":{str(k):v for k,v in FIELDS.items()},"landmarks":{str(k):v for k,v in LANDMARKS.items()},
      "summary":summary,"candidates":top,
      "proofBoundary":"Structural locator only. A high-scoring base means exact current-client absolute memory references line up with many T6 PC32 clipMap_t offsets, including retained landmarks when present. It does not assign the base to the runtime clipMap, infer field meaning from instruction use, identify CM_EntityString, or establish historical-retail equivalence. Those require a later dataflow projector."}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))
    for x in top[:10]:print(x["baseVa"],x["distinctMatchedFieldCount"],x["totalAbsoluteReferenceCount"],[z["field"] for z in x["landmarkOffsets"]])
if __name__=="__main__":main()
