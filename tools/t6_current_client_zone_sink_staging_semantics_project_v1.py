#!/usr/bin/env python3
"""Project exact current-client input-row staging and positional semantics.

Consumes the SHA-gated staging-window proof plus the independently proven sink
argument layout. Promotes only semantics forced by the decoded bytes:
- +0 is used as a pointer to a NUL-terminated byte string;
- +4 is used as an integer/bitmask classifier;
- all 12 input bytes are copied to a local 12-byte staging record;
- +8 remains an unnamed dword copied verbatim into staging.
No historical-retail or source-symbol identity is inferred.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

CLIENT="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
STAGING_FORMAT="t6-current-client-zone-sink-staging-window-probe-v1"
ARG_FORMAT="t6-current-client-zone-sink-argfield-proof-v1"
OUT_FORMAT="t6-current-client-zone-sink-staging-semantics-proof-v1"

EXPECTED={
 "0x00417f2a":("8b842460060000","mov","eax, dword ptr [esp + 0x660]"),
 "0x00417f31":("8b942464060000","mov","edx, dword ptr [esp + 0x664]"),
 "0x00417f40":("8d6c246c","lea","ebp, [esp + 0x6c]"),
 "0x00417f4b":("89442414","mov","dword ptr [esp + 0x14], eax"),
 "0x00417f53":("89542420","mov","dword ptr [esp + 0x20], edx"),
 "0x00417f60":("8b442414","mov","eax, dword ptr [esp + 0x14]"),
 "0x00417f64":("f30f7e00","movq","xmm0, qword ptr [eax]"),
 "0x00417f68":("8b7004","mov","esi, dword ptr [eax + 4]"),
 "0x00417f6b":("8b4008","mov","eax, dword ptr [eax + 8]"),
 "0x00417f7d":("660fd64500","movq","qword ptr [ebp], xmm0"),
 "0x00417f82":("894508","mov","dword ptr [ebp + 8], eax"),
 "0x00417fa3":("f7c68a900402","test","esi, 0x204908a"),
 "0x004180b3":("8b442414","mov","eax, dword ptr [esp + 0x14]"),
 "0x004180b7":("8b4004","mov","eax, dword ptr [eax + 4]"),
 "0x004180ba":("3d00800000","cmp","eax, 0x8000"),
 "0x004180c3":("3d80000000","cmp","eax, 0x80"),
 "0x004180ca":("3d00100000","cmp","eax, 0x1000"),
 "0x004180d6":("3d00000400","cmp","eax, 0x40000"),
 "0x004180e3":("8b4c2414","mov","ecx, dword ptr [esp + 0x14]"),
 "0x004180e7":("8b11","mov","edx, dword ptr [ecx]"),
 "0x004180ef":("52","push","edx"),
 "0x004180f1":("e88a681300","call","0x54e980"),
 "0x0041810a":("8b4c2414","mov","ecx, dword ptr [esp + 0x14]"),
 "0x0041810e":("8b4104","mov","eax, dword ptr [ecx + 4]"),
 "0x0041814c":("8b11","mov","edx, dword ptr [ecx]"),
 "0x0041814e":("8bca","mov","ecx, edx"),
 "0x00418150":("8d7101","lea","esi, [ecx + 1]"),
 "0x00418153":("8a01","mov","al, byte ptr [ecx]"),
 "0x00418155":("41","inc","ecx"),
 "0x00418156":("84c0","test","al, al"),
 "0x00418158":("75f9","jne","0x418153"),
 "0x004181b5":("834424140c","add","dword ptr [esp + 0x14], 0xc"),
 "0x004181ba":("ff4c2420","dec","dword ptr [esp + 0x20]"),
}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--staging",type=Path,required=True);ap.add_argument("--arg-proof",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 sr=a.staging.read_bytes();ar=a.arg_proof.read_bytes();s=json.loads(sr);g=json.loads(ar)
 if s.get("format")!=STAGING_FORMAT or s.get("client",{}).get("sha256")!=CLIENT:raise SystemExit("unexpected staging proof identity")
 if g.get("format")!=ARG_FORMAT or g.get("client",{}).get("sha256")!=CLIENT:raise SystemExit("unexpected arg proof identity")
 if g.get("stackNormalization",{}).get("rowPointerLoad",{}).get("entryEspDisp")!=4 or g.get("stackNormalization",{}).get("rowCountLoad",{}).get("entryEspDisp")!=8:
  raise SystemExit("incoming pointer/count proof not closed")
 by={x["address"]:x for x in s.get("instructions") or []}
 exact=[]
 for addr,exp in EXPECTED.items():
  x=by.get(addr)
  if not x:raise SystemExit(f"missing {addr}")
  got=(x.get("bytes"),x.get("mnemonic"),x.get("opStr"))
  if got!=exp:raise SystemExit(f"{addr}: drift {got!r} != {exp!r}")
  exact.append(x)
 out={
  "format":OUT_FORMAT,
  "client":s["client"],
  "sources":{
   "staging":{"path":str(a.staging),"bytes":len(sr),"sha256":hashlib.sha256(sr).hexdigest()},
   "argProof":{"path":str(a.arg_proof),"bytes":len(ar),"sha256":hashlib.sha256(ar).hexdigest()},
  },
  "exactInstructions":exact,
  "inputRecord":{
   "sizeBytes":12,
   "positionalFields":[
    {
     "offset":0,"widthBytes":4,"promotedSemantic":"pointer_to_nul_terminated_byte_string",
     "proof":[
      "0x004180e3 reloads current input-record pointer",
      "0x004180e7 loads dword at +0",
      "0x0041814c reloads the same +0 dword",
      "0x0041814e moves that dword into ECX",
      "0x00418153/55/56/58 repeatedly load bytes through ECX, increment the pointer, test AL, and loop until byte zero"
     ]
    },
    {
     "offset":4,"widthBytes":4,"promotedSemantic":"integer_bitmask_classifier",
     "proof":[
      "0x00417f68 loads +4 into ESI",
      "0x00417fa3 TESTs ESI with mask 0x0204908a",
      "0x004180b7 reloads +4",
      "0x004180ba/0x004180c3/0x004180ca/0x004180d6 compare it exactly against 0x8000/0x80/0x1000/0x40000"
     ],
     "observedCompositeMask":"0x0204908a",
     "observedEqualityConstants":["0x00008000","0x00000080","0x00001000","0x00040000"]
    },
    {
     "offset":8,"widthBytes":4,"promotedSemantic":None,
     "proof":["0x00417f6b loads +8 and 0x00417f82 copies it to staging +8"]
    }
   ]
  },
  "stagingCopy":{
   "sourcePointerReload":"0x00417f60",
   "destinationBase":"EBP initialized to [ESP+0x6c] at 0x00417f40",
   "copyFirst8Bytes":{"read":"0x00417f64 movq xmm0,qword ptr [eax]","write":"0x00417f7d movq qword ptr [ebp],xmm0"},
   "copyFinal4Bytes":{"read":"0x00417f6b mov eax,[eax+8]","write":"0x00417f82 mov [ebp+8],eax"},
   "exactCopiedBytes":12
  },
  "sourceIteration":{
   "sourcePointerLocal":"[esp+0x14]",
   "sourcePointerIncrement":"0x004181b5 adds 12",
   "remainingCountLocal":"[esp+0x20]",
   "remainingCountDecrement":"0x004181ba"
  },
  "proven":{
   "all12InputRecordBytesCopiedToLocalStaging":True,
   "field0IsNulTerminatedByteStringPointer":True,
   "field4IsIntegerBitmaskClassifier":True,
   "field8CopiedButSemanticUnassigned":True
  },
  "status":"exact_current_client_positional_semantics_only",
  "proofBoundary":"These promotions are limited to behavior forced by exact decoded instructions in the SHA-classified current client. Field +0 is called a NUL-terminated byte-string pointer because the pointed bytes are explicitly scanned to zero. Field +4 is called an integer/bitmask classifier because it is TESTed and compared to exact integer constants. The source-level structure name, allocFlags/freeFlags labels, 0x004174b0 symbol, historical-retail equivalence, priority semantics, and all Technique winners remain unpromoted."
 }
 payload=(json.dumps(out,indent=2,sort_keys=True)+"\n").encode();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(payload)
 print(json.dumps({"outBytes":len(payload),"outSha256":hashlib.sha256(payload).hexdigest(),"proven":out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
