#!/usr/bin/env python3
"""Project current-client duplicate payload/zone exchange on flag=1 replay.

Consumes exact relink and transfer-helper proofs. The transfer helper is not source-named;
we prove argument roles and byte-transfer direction from its body.
"""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path

def collect(relink,helper):
    m={}
    for rg in relink["ranges"]:
        for r in rg["instructions"]:m[r["address"]]=r
    for r in helper["helper"]["instructions"]:m[r["address"]]=r
    for r in helper["helper"]["overlapInstructions"]:m[r["address"]]=r
    return m

def req(m,a,mn,op=None):
    r=m.get(a)
    if r is None:raise SystemExit(f"missing {a}")
    if r["mnemonic"]!=mn or (op is not None and r["opStr"]!=op):raise SystemExit(f"drift {a}: {(r['mnemonic'],r['opStr'])}")
    return r

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--relink",type=Path,required=True);ap.add_argument("--helper",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    rel=json.loads(a.relink.read_text()); h=json.loads(a.helper.read_text())
    if rel.get("format")!="t6-current-client-linked-record-relink-swap-probe-v1":raise SystemExit("wrong relink")
    if h.get("format")!="t6-current-client-relink-payload-helper-probe-v1":raise SystemExit("wrong helper")
    m=collect(rel,h)
    helperAbi=[
      req(m,"0x00a72bf5","mov","esi, dword ptr [ebp + 0xc]"),
      req(m,"0x00a72bf8","mov","ecx, dword ptr [ebp + 0x10]"),
      req(m,"0x00a72bfb","mov","edi, dword ptr [ebp + 8]"),
      req(m,"0x00a72c02","add","eax, esi"),
      req(m,"0x00a72c04","cmp","edi, esi"),
      req(m,"0x00a72c08","cmp","edi, eax"),
      req(m,"0x00a72c0a","jb","0xa72db0"),
      req(m,"0x00a72c47","movsd","dword ptr es:[edi], dword ptr [esi]") if False else req(m,"0x00a72c47","rep movsd","dword ptr es:[edi], dword ptr [esi]"),
      req(m,"0x00a72db0","lea","esi, [ecx + esi - 4]"),
      req(m,"0x00a72db4","lea","edi, [ecx + edi - 4]"),
      req(m,"0x00a72dcb","std",""),
      req(m,"0x00a72dcc","rep movsd","dword ptr es:[edi], dword ptr [esi]"),
      req(m,"0x00a72dce","cld",""),
    ]
    # Same-type duplicate gate before scalar/replay handling.
    duplicateGate=[
      req(m,"0x007fd8eb","mov","edi, dword ptr [esi]"),
      req(m,"0x007fd930","cmp","dword ptr [ebx], edi"),
    ]
    calls=[
      # old-head payload -> temporary stack buffer
      *[req(m,"0x007fd55d","call","0x6b8640"),req(m,"0x007fd562","push","eax"),req(m,"0x007fd563","mov","eax, dword ptr [edi + 4]"),req(m,"0x007fd566","push","eax"),req(m,"0x007fd567","push","ebx"),req(m,"0x007fd568","call","0xa72bf0")],
      # incoming payload -> old-head payload storage
      *[req(m,"0x007fd570","call","0x6b8640"),req(m,"0x007fd575","mov","edx, dword ptr [esi + 4]"),req(m,"0x007fd578","push","eax"),req(m,"0x007fd579","mov","eax, dword ptr [edi + 4]"),req(m,"0x007fd57c","push","edx"),req(m,"0x007fd57d","push","eax"),req(m,"0x007fd57e","call","0xa72bf0")],
      # temporary old-head bytes -> incoming payload storage
      *[req(m,"0x007fd587","call","0x6b8640"),req(m,"0x007fd58c","mov","edx, dword ptr [esi + 4]"),req(m,"0x007fd58f","push","eax"),req(m,"0x007fd590","push","ebx"),req(m,"0x007fd591","push","edx"),req(m,"0x007fd592","call","0xa72bf0")],
    ]
    replaySwap=[
      req(m,"0x007fdc0f","mov","ax, word ptr [ebx + 0xc]"),
      req(m,"0x007fdc1e","mov","word ptr [esi + 0xc], ax"),
      req(m,"0x007fdc24","mov","word ptr [ebx + 0xc], cx"),
      req(m,"0x007fdc28","call","0x7fd520"),
      req(m,"0x007fdc2d","mov","al, byte ptr [ebx + 8]"),
      req(m,"0x007fdc30","mov","dl, byte ptr [esi + 8]"),
      req(m,"0x007fdc34","mov","byte ptr [ebx + 8], dl"),
      req(m,"0x007fdc37","mov","byte ptr [esi + 8], al"),
    ]
    out={
      "format":"t6-current-client-linked-record-payload-exchange-v1",
      "authority":"Persisted exact SHA-classified current-client proofs only",
      "client":rel["client"],
      "transferHelper":{
        "entry":"0x00a72bf0",
        "abi":{"arg1":"destination","arg2":"source","arg3":"byte count"},
        "forwardEvidence":"arg registers become EDI(destination), ESI(source), ECX(count); body uses rep movsd ESI->EDI",
        "overlapEvidence":"when destination is inside source..source+count, explicit target 0x00a72db0 adjusts to end and uses std; rep movsd; cld",
        "sourceSymbolNamePromoted":False,
        "exactInstructions":helperAbi,
      },
      "duplicateGate":{"incomingRecord":"ESI","existingRecord":"EBX","typeDwordEqualBeforeReplayPath":True,"exactInstructions":duplicateGate},
      "threeTransferCycle":{
        "existingPayloadToTemporary":True,
        "incomingPayloadToExistingStorage":True,
        "temporaryOldPayloadToIncomingStorage":True,
        "sizeFunction":"0x006b8640",
        "sameTypeGateMeansBothLogicalDuplicatesUseSameTypeSelector":True,
        "exactInstructions":calls,
      },
      "flag1RelinkAndZoneExchange":{
        "existingSecondaryLinkBecomesIncomingRecord":True,
        "incomingSecondaryLinkReceivesOldExistingNext":True,
        "payloadTransferCycleCalled":True,
        "zoneIndexByte8Exchanged":True,
        "exactInstructions":replaySwap,
      },
      "proven":{
        "transferHelperArg1DestinationArg2SourceArg3Count":True,
        "transferHelperCopiesForwardViaMovs":True,
        "transferHelperHasExplicitBackwardOverlapCopyPath":True,
        "duplicatePathRequiresEqualTypeDword":True,
        "flag1ReplayRunsThreeTransferCycle":True,
        "flag1ReplayExchangesPayloadContentsBetweenExistingAndIncomingStorage":True,
        "flag1ReplayExchangesZoneIndexByte8":True,
        "incomingLogicalPayloadAndZoneMetadataMoveToExistingHeadStorage":True,
        "oldHeadLogicalPayloadAndZoneMetadataMoveToIncomingLinkedStorage":True,
      },
      "proofBoundary":"The current-client bytes prove directional transfer-helper behavior, the three-transfer cycle, and zone-index exchange. The helper is deliberately not source-named. Tiny-count jump-table internals are not individually source-named; the higher-level exchange statement is grounded in the helper ABI and explicit forward/overlap transfer bodies plus the three calls. Historical-retail equivalence remains separate."
    }
    payload=json.dumps(out,indent=2,sort_keys=True)+"\n";a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(payload)
    print(json.dumps({"sha256":hashlib.sha256(payload.encode()).hexdigest(),**out["proven"]},indent=2,sort_keys=True))
if __name__=="__main__":main()
