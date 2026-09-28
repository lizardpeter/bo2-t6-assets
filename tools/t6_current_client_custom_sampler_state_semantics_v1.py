#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CLIENT=ROOT/"proof/current_client/T6_CURRENT_CLIENT_GAMETIME_STATE_OFFSET_XREFS_V1.json"
BINDINGS=ROOT/"manifests/render/T6_NUKETOWN_SPECIAL_RENDER_CLOSURE_V1.json"
OUT=ROOT/"proof/current_client/T6_CURRENT_CLIENT_CUSTOM_SAMPLER_STATE_SEMANTICS_V1.json"
SHA="770318175f0161aa7a1ff0f9a5530336836a99e72900d7608a63973e56004adf"
TARGETS={
 "lightmapSamplerSecondary":dict(register=13,state=0x62,state_va="0x007439c3",push_va="0x007439d9",call_va="0x007439dc",cache_offset="0x44"),
 "reflectionProbeSampler":dict(register=15,state=0x72,state_va="0x00743b80",push_va="0x00743b96",call_va="0x00743b99",cache_offset="0x4c"),
}
def imap(row):
 rows=list(row.get("contextBefore",[]))+[row["instruction"]]+list(row.get("contextAfter",[]))
 return {x["address"].lower():x for x in rows}
def exact_sequence(doc,t):
 for row in doc["xrefs"]:
  m=imap(row); s=m.get(t["state_va"]); p=m.get(t["push_va"]); c=m.get(t["call_va"])
  if not (s and p and c): continue
  if s["mnemonic"]!="mov" or s["opStr"]!=f"eax, 0x{t['state']:x}": continue
  if p["mnemonic"]!="push" or p["opStr"]!=f"0x{t['register']:x}": continue
  if c["mnemonic"]!="call" or c["opStr"]!="0x740500": continue
  cache=[x for x in m.values() if t["cache_offset"] in x.get("opStr","").lower() and x["mnemonic"] in {"cmp","mov"}]
  if len(cache)<2: continue
  return dict(stateInstruction=s,stateCacheInstructions=sorted(cache,key=lambda x:int(x["address"],16)),samplerRegisterInstruction=p,bindCallInstruction=c)
 raise RuntimeError(f"missing exact sequence {t}")
def decode(raw):
 return dict(filter={0:"disabled",1:"nearest",2:"linear",3:"aniso2x",4:"aniso4x",5:"compare"}[raw&7],
             mipMap={0:"disabled",1:"nearest",2:"linear"}[(raw>>3)&3],
             clampU=bool(raw&0x20),clampV=bool(raw&0x40),clampW=bool(raw&0x80))
def main():
 client=json.loads(CLIENT.read_text())
 if client["client"]["sha256"].lower()!=SHA: raise RuntimeError("current-client SHA drift")
 closure=json.loads(BINDINGS.read_text())
 binds={r["textureName"]:r for r in closure["runtimeTextureBindings"] if r.get("textureName") in TARGETS}
 if set(binds)!=set(TARGETS): raise RuntimeError("runtime sampler binding denominator drift")
 rows=[]
 for name,t in TARGETS.items():
  if int(binds[name]["samplerRegister"])!=t["register"]: raise RuntimeError(f"{name} register drift")
  rows.append(dict(accessor=name,samplerRegister=t["register"],packedStateByte=t["state"],
                   packedStateByteHex=f"0x{t['state']:02x}",decodedState=decode(t["state"]),
                   retailBinding=binds[name],currentClientEvidence=exact_sequence(client,t)))
 out=dict(format="t6-current-client-custom-sampler-state-semantics-v1",
          authority="SHA-pinned current T6 client machine code joined to independent retail shader sampler-register closure",
          client=client["client"],samplers=rows,
          summary=dict(samplerCount=2,secondaryLightmapStateByte=0x62,reflectionProbeStateByte=0x72),
          proofBoundary="Closes packed state byte and sampler register for lightmapSamplerSecondary and reflectionProbeSampler only. Packed-byte bit meanings are independently pinned by the T6 sampler-state layout. No other code sampler or resource semantics are inferred.")
 OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print(json.dumps(out["summary"],sort_keys=True))
if __name__=="__main__": main()
