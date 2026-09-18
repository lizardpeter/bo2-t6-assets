#!/usr/bin/env python3
"""Project exact current-client runtime classifier priority-comparison path.

Consumes the persisted runtime-zone-table xref proof only. It proves a masked
classifier -> shared scalar function -> returned-value comparison -> linked
16-byte record relink path, without source-symbol promotion.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-runtime-zone-table-xref-probe-v1"
CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

EXPECTED={
"0x007fdaca":("mov","edx, dword ptr [ecx + 0x1804948]"),
"0x007fdad0":("and","edx, 0x3fffffff"),
"0x007fdad6":("push","edx"),
"0x007fdad7":("call","0x493440"),
"0x007fdadc":("mov","edi, eax"),
"0x007fdae5":("mov","ecx, dword ptr [eax + 0x1804948]"),
"0x007fdaeb":("and","ecx, 0x3fffffff"),
"0x007fdaf1":("push","ecx"),
"0x007fdaf2":("call","0x493440"),
"0x007fdaf7":("add","esp, 8"),
"0x007fdafa":("cmp","edi, eax"),
"0x007fdafc":("jge","0x7fdbf7"),
"0x007fdb02":("cmp","word ptr [ebx + 0xc], 0"),
"0x007fdb07":("lea","edx, [ebx + 0xc]"),
"0x007fdb10":("movzx","ecx, word ptr [edx]"),
"0x007fdb13":("shl","ecx, 4"),
"0x007fdb16":("add","ecx, 0x14342e0"),
"0x007fdb1c":("movzx","eax, byte ptr [ecx + 8]"),
"0x007fdb20":("imul","eax, eax, 0x4c"),
"0x007fdb23":("mov","eax, dword ptr [eax + 0x1804948]"),
"0x007fdb29":("and","eax, 0x3fffffff"),
"0x007fdb2e":("push","eax"),
"0x007fdb2f":("call","0x493440"),
"0x007fdb34":("add","esp, 4"),
"0x007fdb37":("cmp","edi, eax"),
"0x007fdb39":("jge","0x7fdb45"),
"0x007fdb3b":("cmp","word ptr [ecx + 0xc], 0"),
"0x007fdb40":("lea","edx, [ecx + 0xc]"),
"0x007fdb43":("jne","0x7fdb10"),
"0x007fdb45":("mov","cx, word ptr [edx]"),
"0x007fdb48":("mov","word ptr [esi + 0xc], cx"),
"0x007fdb4c":("sub","esi, 0x14342e0"),
"0x007fdb52":("sar","esi, 4"),
"0x007fdb56":("mov","word ptr [edx], si"),
}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--xref-proof",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 raw=a.xref_proof.read_bytes();d=json.loads(raw)
 if d.get("format")!=FORMAT or d.get("client",{}).get("sha256")!=CLIENT:raise SystemExit("unexpected source identity")
 by={}
 for x in d.get("xrefs",[]):
  for row in (x.get("contextBefore") or [])+[x.get("instruction")]+(x.get("contextAfter") or []):
   if row:by.setdefault(row["address"],row)
 selected=[]
 for addr,want in EXPECTED.items():
  row=by.get(addr)
  if row is None:raise SystemExit(f"missing {addr}")
  got=(row.get("mnemonic"),row.get("opStr"))
  if got!=want:raise SystemExit(f"{addr}: drift {got!r} != {want!r}")
  selected.append(row)
 out={
  "format":"t6-current-client-runtime-zone-priority-path-v1",
  "authority":"SHA-classified current Plutonium client only",
  "client":d["client"],
  "source":{"path":str(a.xref_proof),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()},
  "priorityPath":{
   "classifierMaskBeforeScalarFunction":"0x3fffffff",
   "scalarFunction":"0x00493440",
   "firstClassifierSource":"runtime zone table +0x40",
   "secondClassifierSource":"runtime zone table +0x40",
   "returnComparison":"first scalar result compared against second scalar result",
   "decisionBranch":"jge at 0x007fdafc / 0x007fdb39",
  },
  "linkedStructure":{
   "base":"0x014342e0",
   "strideBytes":16,
   "zoneIndexByteOffset":8,
   "linkWordOffset":12,
   "linkEncoding":"16-byte record index stored as uint16",
   "relinkWrites":["0x007fdb48","0x007fdb56"],
  },
  "proven":{
   "runtimeClassifiersAreMaskedBeforeSharedScalarFunction":True,
   "maskIs0x3fffffff":True,
   "sharedScalarFunctionIs0x00493440":True,
   "returnedScalarsControlLinkedInsertionOrder":True,
   "linkedRecordStrideIs16Bytes":True,
   "linkedRecordCarriesRuntimeZoneIndexAtByte8":True,
  },
  "exactInstructions":selected,
  "proofBoundary":"This proves a current-client masked runtime-zone-classifier ordering path and exact linked-record relinking. Function 0x00493440 is intentionally described only as the shared scalar function until its implementation is independently decoded. The 16-byte structure is not yet source-named XAssetEntry. No historical-retail equivalence, DB_GetZonePriority/DB_OverrideAsset source-symbol identity, or Technique winner is promoted."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),**out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
