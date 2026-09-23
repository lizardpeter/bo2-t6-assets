#!/usr/bin/env python3
"""Fail-closed current-client provider semantics for CONST_SRC_CODE_GAMETIME.

This projector composes three independently retained proofs:
  1. exact six-caller source-record setup for the 0x76F7E0 copy routine;
  2. exact byte copy source+4 -> renderState+0x1A2C (T);
  3. exact transform T -> gameTime[0..3] and version increment.

The provider is closed as a current-client dataflow contract without inventing a
human semantic name, unit, cadence, or historical-retail equivalence for source+4.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

FORMAT="t6-current-client-gametime-provider-semantics-v1"
CALL_FMT="t6-current-client-gametime-source-object-callers-v1"
COPY_FMT="t6-current-client-gametime-state-copy-probe-v1"
XFORM_FMT="t6-current-client-gametime-transform-semantics-v1"
CLIENT_SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p:Path)->dict:return json.loads(p.read_text())
def req(c,m):
    if not c: raise SystemExit(m)

def ins_map(caller):
    rows=caller.get("contextBefore",[])+[caller["call"]]+caller.get("contextAfter",[])
    return {r["address"]:r for r in rows}

EXPECTED={
 "0x00732479":{"source":("0x00732468","8d8780010000","lea","eax, [edi + 0x180]"),
               "state":("0x0073246e","ba006ba303","mov","edx, 0x3a36b00"),
               "sourceKind":"scene-record+0x180","sourceBaseRegister":"edi","stateKind":"global-render-state"},
 "0x00732c00":{"source":("0x00732bf5","8d8780010000","lea","eax, [edi + 0x180]"),
               "state":("0x00732bfb","ba006ba303","mov","edx, 0x3a36b00"),
               "sourceKind":"scene-record+0x180","sourceBaseRegister":"edi","stateKind":"global-render-state"},
 "0x00733164":{"source":("0x00733159","8d8780010000","lea","eax, [edi + 0x180]"),
               "state":("0x0073315f","ba006ba303","mov","edx, 0x3a36b00"),
               "sourceKind":"scene-record+0x180","sourceBaseRegister":"edi","stateKind":"global-render-state"},
 "0x00733729":{"source":("0x0073371e","8d8580010000","lea","eax, [ebp + 0x180]"),
               "state":("0x00733724","ba006ba303","mov","edx, 0x3a36b00"),
               "sourceKind":"scene-record+0x180","sourceBaseRegister":"ebp","stateKind":"global-render-state"},
 "0x00745c41":{"source":("0x00745c39","83c004","add","eax, 4"),
               "state":("0x00745c3c","ba006ba303","mov","edx, 0x3a36b00"),
               "sourceKind":"command-record+4","sourceBaseRegister":"eax-from-[esi]","stateKind":"global-render-state"},
 "0x00773f89":{"source":("0x00773f79","8d8380010000","lea","eax, [ebx + 0x180]"),
               "state":("0x00773f7f","8bd7","mov","edx, edi"),
               "sourceKind":"scene-record+0x180","sourceBaseRegister":"ebx","stateKind":"caller-supplied-render-state"},
}

def check_instruction(rows,spec,label):
    addr,b,mn,op=spec
    r=rows.get(addr);req(r is not None,f"{label}: instruction {addr} missing")
    req(r["bytes"]==b and r["mnemonic"]==mn and r["opStr"]==op,
        f"{label}: instruction drift at {addr}: {r}")
    return r

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--callers",type=Path,required=True)
    ap.add_argument("--copy",type=Path,required=True)
    ap.add_argument("--transform",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    calls=load(a.callers);copy=load(a.copy);xf=load(a.transform)
    req(calls.get("format")==CALL_FMT,"caller format drift")
    req(copy.get("format")==COPY_FMT,"copy format drift")
    req(xf.get("format")==XFORM_FMT,"transform format drift")
    for d,n in ((calls,"callers"),(copy,"copy"),(xf,"transform")):
        req(d.get("client",{}).get("sha256")==CLIENT_SHA,f"{n}: client SHA drift")

    req(calls.get("summary",{}).get("callerCount")==6,"expected six exact copy callers")
    by={c["call"]["address"]:c for c in calls["callers"]}
    req(set(by)==set(EXPECTED),f"caller set drift: {sorted(by)}")
    classified=[]
    for addr,spec in EXPECTED.items():
        c=by[addr];rows=ins_map(c)
        check_instruction(rows,spec["source"],addr+" source")
        check_instruction(rows,spec["state"],addr+" state")
        req(c["call"]["opStr"]=="0x76f7e0",f"{addr}: call target drift")
        classified.append({
          "callVa":addr,"sourceKind":spec["sourceKind"],"sourceBaseRegister":spec["sourceBaseRegister"],
          "stateKind":spec["stateKind"],"sourceSetupVa":spec["source"][0],"stateSetupVa":spec["state"][0],
        })

    cs=copy["copySemantics"]
    req(cs.get("inputBaseRegister")=="eax","copy input register drift")
    req(cs.get("sourceStateBaseRegister")=="edx","copy state register drift")
    gt=cs.get("gameTimeScalarT",{})
    req(gt.get("inputOffset")==4 and gt.get("stateOffset")==0x1A2C,"gameTime copy lane drift")
    req(copy.get("summary",{}).get("gameTimeFieldIndirectWriteClosed") is True,"copy closure absent")
    ri=xf.get("runtimeInput",{})
    req(ri.get("accessor")=="gameTime" and int(ri.get("enumValue",-1))==25,"runtime identity drift")
    req(xf.get("summary",{}).get("currentClientTransformClosed") is True,"transform closure absent")
    lanes=xf.get("transform",{}).get("lanes",[])
    req([(x["lane"],x["expression"]) for x in lanes]==[
      (0,"sin(theta)"),(1,"cos(theta)"),(2,"f"),(3,"T")],"transform lane drift")

    doc={
      "format":FORMAT,
      "authority":"SHA-classified current-client exact caller setup + byte-copy dataflow + exact gameTime transform",
      "client":xf["client"],
      "runtimeInput":{
        "accessor":"gameTime","enumSymbol":"CONST_SRC_CODE_GAMETIME","enumValue":25,
        "retainedSpecialOccurrences":int(ri.get("totalOccurrences",363)),"sourceClass":"constant",
        "valueVas":ri["valueVas"],"versionVa":ri["versionVa"],
      },
      "sourceRecordContract":{
        "copyRoutineVa":"0x0076f7e0","copyRoutineInputRegister":"eax","renderStateRegister":"edx",
        "sourceRecordBytes":20,"scalarTSourceOffset":4,"scalarTRenderStateOffset":0x1A2C,
        "callers":classified,
        "callerCount":len(classified),
        "physicalSemanticName":"unresolved","physicalUnits":"unresolved","updateCadence":"unresolved",
      },
      "providerTransform":xf["transform"],
      "sources":{
        "callers":{"path":str(a.callers),"sha256":sha(a.callers),"format":calls["format"]},
        "stateCopy":{"path":str(a.copy),"sha256":sha(a.copy),"format":copy["format"]},
        "transform":{"path":str(a.transform),"sha256":sha(a.transform),"format":xf["format"]},
      },
      "summary":{
        "enumValue":25,"exactCallerCount":6,"sourceRecordContractClosed":True,
        "sourceScalarProviderDataflowClosed":True,"currentClientTransformClosed":True,
        "currentClientProviderClosed":True,"retainedSpecialOccurrenceCount":int(ri.get("totalOccurrences",363)),
        "physicalUnitsClosed":False,"historicalRetailEquivalent":False,
      },
      "proofBoundary":"Closes current-client provider dataflow for gameTime: all six direct copy-routine callers have exact source/state setup, source record lane +4 is copied byte-for-byte to renderState+0x1A2C, and the exact four-lane gameTime transform/version update is proven. The human semantic name, physical units and cadence of source lane +4 remain intentionally unknown; current-client provider closure here means executable dataflow is sufficient to reproduce the input from the same source record, not that those physical semantics or historical-retail equivalence are known."
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
    print(json.dumps(doc["summary"],indent=2,sort_keys=True))
if __name__=="__main__":main()
