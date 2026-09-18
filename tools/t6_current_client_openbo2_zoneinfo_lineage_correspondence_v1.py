#!/usr/bin/env python3
"""Fail-closed current-client <-> pinned OpenBO2 zone-info lineage correspondence.

This does NOT promote OpenBO2 source names into historical retail authority. It
only records an unusually specific structural/control-flow correspondence between
independently persisted current-client byte proofs and one pinned public source
lineage.
"""
from __future__ import annotations
import argparse,hashlib,json,re,urllib.request
from pathlib import Path

OPENBO2_COMMIT="a64812d21946baf710cec7fa26b98ad0d193903b"
DB_PATH="src/code/src_noserver/database/db_registry.cpp"
DB_BLOB="4232e88270f809d07b5522c9e09ff68376cc1b06"
TYPES_PATH="src/code/src_noserver/all_types.h"
TYPES_BLOB="f1f1a4560134175f867d29fa1653231e79937277"
CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

XZONE_SNIPPET="""struct XZoneInfo
{
  const char *name;
  int allocFlags;
  int freeFlags;
};"""
COMPARE_SNIPPET="""char DB_CompareLoadXZoneInfos(const XZoneInfo *zone0, const XZoneInfo *zone1)
{
	if (zone0->name)
	{
		if (zone0->allocFlags >= 0x400000 || zone1->allocFlags >= 0x400000)
		{
			return  zone0->allocFlags > zone1->allocFlags;
		}
		else
		{
			return zone0->allocFlags < zone1->allocFlags;
		}
	}
}"""

def git_blob_sha(raw:bytes)->str:
 return hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()

def fetch(path:str)->bytes:
 url=f"https://raw.githubusercontent.com/builtbyxeno/OpenBO2/{OPENBO2_COMMIT}/{path}"
 req=urllib.request.Request(url,headers={"User-Agent":"bo2-t6-assets-lineage-proof/1"})
 with urllib.request.urlopen(req,timeout=120) as r:return r.read()

def load_json(p:Path):
 raw=p.read_bytes();return json.loads(raw),raw

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--classifier-proof",type=Path,required=True)
 ap.add_argument("--secondary-proof",type=Path,required=True)
 ap.add_argument("--argfield-proof",type=Path,required=True)
 ap.add_argument("--out",type=Path,required=True)
 a=ap.parse_args()
 cp,cr=load_json(a.classifier_proof);sp,sr=load_json(a.secondary_proof);apf,ar=load_json(a.argfield_proof)
 for name,d in [("classifier",cp),("secondary",sp),("argfield",apf)]:
  if d.get("client",{}).get("sha256")!=CLIENT:raise SystemExit(f"{name}: wrong client identity")
 if cp.get("format")!="t6-current-client-zone-classifier-semantics-v1":raise SystemExit("classifier format drift")
 if sp.get("format")!="t6-current-client-zone-secondary-mask-semantics-v1":raise SystemExit("secondary format drift")
 if apf.get("format")!="t6-current-client-zone-sink-argfield-proof-v1":raise SystemExit("argfield format drift")
 if not cp["proven"]["plus4IsCurrentClientRecordOrderingKey"]:raise SystemExit("classifier ordering not proven")
 if not cp["proven"]["plus4Threshold0x00400000ChangesOrderingDirection"]:raise SystemExit("threshold ordering not proven")
 if not sp["proven"]["plus8IsCurrentClientMutableSecondaryControlMask"]:raise SystemExit("secondary +8 semantics not proven")
 if apf["proven"]["incomingRowPointerEntryStackOffset"]!=4 or apf["proven"]["incomingRowCountEntryStackOffset"]!=8:raise SystemExit("sink ABI drift")

 db=fetch(DB_PATH);types=fetch(TYPES_PATH)
 if git_blob_sha(db)!=DB_BLOB:raise SystemExit("OpenBO2 db_registry blob drift")
 if git_blob_sha(types)!=TYPES_BLOB:raise SystemExit("OpenBO2 all_types blob drift")
 dbt=db.decode("utf-8");tt=types.decode("utf-8")
 if tt.count(XZONE_SNIPPET)!=1:raise SystemExit("expected exact XZoneInfo snippet once")
 if dbt.count(COMPARE_SNIPPET)!=1:raise SystemExit("expected exact comparator snippet once")

 out={
  "format":"t6-current-client-openbo2-zoneinfo-lineage-correspondence-v1",
  "authority":"comparative lineage correspondence only; not historical-retail authority",
  "currentClient":{
   "sha256":CLIENT,
   "proofs":{
    "classifier":{"path":str(a.classifier_proof),"bytes":len(cr),"sha256":hashlib.sha256(cr).hexdigest()},
    "secondaryMask":{"path":str(a.secondary_proof),"bytes":len(sr),"sha256":hashlib.sha256(sr).hexdigest()},
    "argfield":{"path":str(a.argfield_proof),"bytes":len(ar),"sha256":hashlib.sha256(ar).hexdigest()},
   },
   "independentFacts":{
    "rowStrideBytes":12,
    "nameOffset":0,
    "orderingClassifierOffset":4,
    "secondaryControlMaskOffset":8,
    "orderingThreshold":"0x00400000",
    "orderingBelowThreshold":"ascending",
    "orderingOtherwise":"descending",
   }
  },
  "openBO2":{
   "repository":"builtbyxeno/OpenBO2",
   "commit":OPENBO2_COMMIT,
   "files":{
    DB_PATH:{"gitBlobSha1":DB_BLOB,"bytes":len(db)},
    TYPES_PATH:{"gitBlobSha1":TYPES_BLOB,"bytes":len(types)},
   },
   "sourceFacts":{
    "XZoneInfo":{"sizeOnPC32Bytes":12,"nameOffset":0,"allocFlagsOffset":4,"freeFlagsOffset":8},
    "DB_CompareLoadXZoneInfos":{
     "threshold":"0x00400000",
     "belowThreshold":"zone0.allocFlags < zone1.allocFlags",
     "otherwise":"zone0.allocFlags > zone1.allocFlags",
    },
   }
  },
  "correspondence":{
   "pc32RecordGeometryExactMatch":True,
   "offset0NameRoleMatch":True,
   "offset4ComparatorRoleAndThresholdExactMatch":True,
   "offset4ComparatorDirectionExactMatch":True,
   "offset8PositionMatchesSourceFreeFlagsPosition":True,
   "offset8CurrentClientControlMaskBehaviorIsIndependentlyProven":True,
   "strength":"specific structural plus comparator-control-flow correspondence",
  },
  "nonPromotions":[
   "current-client +4 is not promoted to historical-retail allocFlags authority",
   "current-client +8 is not promoted to historical-retail freeFlags authority",
   "0x007fdf00 is not asserted to be the historical-retail DB_CompareLoadXZoneInfos function",
   "OpenBO2 DB_GetZonePriority/DB_OverrideAsset are not imported as current-client or historical-retail winner rules",
   "no Technique winner is selected",
  ],
  "proofBoundary":"Current-client facts are independently byte-proven; OpenBO2 source is independently pinned by commit and Git blob hashes. Their correspondence is recorded because the 12-byte layout and the complete +4 comparator threshold/direction coincide. Correspondence is not identity proof and cannot substitute for historical-retail executable/runtime ownership evidence."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest(),"correspondence":out["correspondence"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
