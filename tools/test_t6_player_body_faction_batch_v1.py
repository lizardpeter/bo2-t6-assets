#!/usr/bin/env python3
import hashlib, importlib.util, json, tempfile
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent; TOOL=HERE/"t6_player_body_faction_batch_v1.py"
s=importlib.util.spec_from_file_location("batch",TOOL)
if s is None or s.loader is None: raise RuntimeError("cannot import batch")
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
class Targets:
    @staticmethod
    def build(seed):
        models=[{"name":"bodyA","faction":"A","bodyClass":"smg","nameEvidence":"fixture"},{"name":"bodyB","faction":"B","bodyClass":"lmg","nameEvidence":"fixture"},{"name":"bodyC","faction":"C","bodyClass":"sniper","nameEvidence":"fixture"}]
        return {"format":"t6-player-body-target-census-v1","models":models,"summary":{"candidateBodies":3}}
class Raw:
    fail_bad=False
    @classmethod
    def parse_front(cls,data):
        if cls.fail_bad and data==b"BAD": raise ValueError("corrupt expanded")
        return {"block_sizes":[{"bytes":100} for _ in range(8)]}
class Probe:
    ambiguous=False
    @classmethod
    def probe_name(cls,data,target,raw,blocks):
        n=target["name"]
        if cls.ambiguous and data==b"S2" and n=="bodyA": return {"status":"ambiguous_inline_xmodel","name":n,"candidateCount":2}
        exact=(data==b"S1" and n in ("bodyA","bodyB")) or (data==b"S2" and n=="bodyB")
        if exact:return {"status":"exact_inline_xmodel","name":n,"fixedRecordSha256":hashlib.sha256(data+n.encode()).hexdigest()}
        return {"status":"not_inline_locatable","name":n}
class Closer:
    calls=[]
    @classmethod
    def close_body(cls,*,name,zone_name,fastfile,expanded,raw_parser_path,out_dir):
        cls.calls.append((name,zone_name,expanded.read_bytes()))
        out_dir.mkdir(parents=True,exist_ok=True); p=out_dir/"player_body_retail_proof_v3.json"; p.write_text(json.dumps({"name":name})+"\n")
        raw=p.read_bytes(); art={"path":str(p),"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
        return {"status":"closed","blockerStage":None,"blocker":None,"meshPath":"fixture","summary":{"bones":10},"retailProof":art}
class Registry:
    @staticmethod
    def build(candidates,proofs): return {"format":"t6-player-body-identity-registry-v1","summary":{"retailProvenBodies":len(proofs),"unresolvedCandidates":len(candidates["models"])-len(proofs)},"proofPaths":[str(p) for p in proofs]}
mods=SimpleNamespace(targets=Targets,raw=Raw,probe=Probe,closer=Closer,registry=Registry)
with tempfile.TemporaryDirectory() as d:
    td=Path(d); seed=td/"seed.json"; seed.write_text("{}\n")
    s1=td/"faction_seals_mp.expanded"; s1.write_bytes(b"S1")
    dupdir=td/"copy"; dupdir.mkdir(); s1dup=dupdir/"faction_seals_mp.expanded"; s1dup.write_bytes(b"S1")
    s2=td/"faction_fbi_mp.expanded"; s2.write_bytes(b"S2")
    ff1=td/"faction_seals_mp.ff"; ff1.write_bytes(b"FF1"); ff2=td/"faction_fbi_mp.ff"; ff2.write_bytes(b"FF2")
    Closer.calls=[]; Raw.fail_bad=False; Probe.ambiguous=False
    out=m.run_batch(seed_path=seed,expanded_paths=[s1,s1dup,s2],fastfile_paths=[ff1,ff2],raw_parser_path=td/"raw.py",out_dir=td/"out",modules=mods)
    assert out["summary"]["uniqueExpandedStreams"]==2
    rows={r["name"]:r for r in out["bodies"]}
    assert rows["bodyA"]["status"]=="closed-retail-proof"
    assert rows["bodyB"]["status"]=="blocked-multiple-distinct-retail-streams"
    assert rows["bodyC"]["status"]=="unresolved-no-inline-definition"
    assert Closer.calls==[("bodyA","faction_seals_mp",b"S1")]
    assert out["summary"]["registryRetailProven"]==1 and out["summary"]["registryUnresolved"]==2
    src=[r for r in out["sources"] if r["zoneName"]=="faction_seals_mp"][0]; assert len(src["duplicates"])==1

    # One unread stream blocks all promotion, including an otherwise unique exact hit.
    bad=td/"faction_pla_mp.expanded"; bad.write_bytes(b"BAD"); ffbad=td/"faction_pla_mp.ff"; ffbad.write_bytes(b"FFBAD")
    Closer.calls=[]; Raw.fail_bad=True
    out=m.run_batch(seed_path=seed,expanded_paths=[s1,bad],fastfile_paths=[ff1,ffbad],raw_parser_path=td/"raw.py",out_dir=td/"err",modules=mods)
    assert out["summary"]["sourceErrors"]==1 and Closer.calls==[]
    assert all(r["status"]=="blocked-source-corpus-errors" for r in out["bodies"])
    assert out["summary"]["registryRetailProven"]==0
    Raw.fail_bad=False

    # Ambiguity in any stream blocks that body even if another stream has one exact hit.
    Closer.calls=[]; Probe.ambiguous=True
    out=m.run_batch(seed_path=seed,expanded_paths=[s1,s2],fastfile_paths=[ff1,ff2],raw_parser_path=td/"raw.py",out_dir=td/"amb",modules=mods)
    rows={r["name"]:r for r in out["bodies"]}
    assert rows["bodyA"]["status"]=="blocked-ambiguous-inline-xmodel"
    assert "bodyA" not in [c[0] for c in Closer.calls]
    Probe.ambiguous=False

    # Two different fastfile hashes for one zone are not silently selected.
    alt=td/"alt"; alt.mkdir(); ff1b=alt/"faction_seals_mp.ff"; ff1b.write_bytes(b"DIFFERENT")
    Closer.calls=[]
    out=m.run_batch(seed_path=seed,expanded_paths=[s1],fastfile_paths=[ff1,ff1b],raw_parser_path=td/"raw.py",out_dir=td/"ffamb",modules=mods)
    rows={r["name"]:r for r in out["bodies"]}; assert rows["bodyA"]["status"]=="blocked-ambiguous-fastfile" and Closer.calls==[]

print("PASS t6_player_body_faction_batch_v1")
