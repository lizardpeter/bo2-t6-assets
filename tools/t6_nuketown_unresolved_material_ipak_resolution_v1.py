#!/usr/bin/env python3
"""Resolve exact traced unresolved Material GfxImages against retail IPAKs."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from t6_ipak_http_range_v2 import open_ipak

def sha(b): return hashlib.sha256(b).hexdigest()
def iwi(raw):
    if len(raw)<12 or raw[:4]!=b'IWi\x1b': raise ValueError('not IWI27')
    w,h,d=struct.unpack_from('<3H',raw,6); return {'format':raw[4],'flags':raw[5],'width':w,'height':h,'depth':d}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--payload',type=Path,required=True);ap.add_argument('--trace',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('urls',nargs='+');a=ap.parse_args()
    payload=json.loads(a.payload.read_text()); trace=json.loads(a.trace.read_text())
    if payload.get('format')!='t6-nuketown-production-texture-payload-coverage-v1': raise SystemExit('payload format drift')
    if trace.get('format') not in {'t6-nuketown-gfximage-packed-identity-trace-v1','t6-nuketown-gfximage-packed-identity-trace-v2'}:
        raise SystemExit('trace format drift')
    unresolved=set(payload['unresolvedProductionImages'])
    by={x['name']:x for x in trace['rows']}
    trace_conflicts={x['name']:x for x in trace.get('conflicts',[])}
    overlap=set(by)&set(trace_conflicts)
    if overlap: raise SystemExit(f'trace stable/conflict overlap: {sorted(overlap)}')
    conflict_names=sorted(unresolved & set(trace_conflicts))
    missing=sorted(unresolved-set(by)-set(trace_conflicts))
    targets=[by[x] for x in sorted(unresolved&set(by))]
    ipaks=[open_ipak(u) for u in a.urls]; rows=[]; cache={}
    for t in targets:
        nh=t['nameHash']&0xffffffff; dh=t['dataHash']&0x1fffffff; exact=[]
        for p in ipaks:
            e=p.entry_exact(nh,dh)
            if e is not None: exact.append((p,e))
        # Native OAT supplies both lookup keys. Do not degrade an absent exact pair
        # to dataHash-only ownership: CRC29 payload identity is not image ownership.
        ex=[]
        for p,e in exact:
            key=(p.url,e)
            if key not in cache:
                raw=p.extract_entry(e); cache[key]=(raw,iwi(raw))
            raw,ident=cache[key]; ex.append({'container':p.url,'entry':{'dataHash':e[0],'nameHash':e[1],'offset':e[2],'rawSize':e[3]},'bytes':len(raw),'sha256':sha(raw),'iwi':ident})
        status='missing'; selected=None; reason='no supplied IPAK contains traced exact (nameHash,dataHash) pair'
        if ex:
            shas={x['sha256'] for x in ex}; dims={(x['iwi']['width'],x['iwi']['height'],x['iwi']['depth']) for x in ex}; want=(t['width'],t['height'],t['depth'])
            if len(shas)!=1: status='conflict'; reason='byte-different payloads for traced identity'
            elif dims!={want}: status='conflict'; reason=f'IWI dimensions {sorted(dims)} != traced {want}'
            else: status='resolved'; selected=next(iter(shas)); reason=None
        rows.append({'name':t['name'],'nameHash':nh,'dataHash':dh,'tracedDimensions':{'width':t['width'],'height':t['height'],'depth':t['depth']},'status':status,'resolution':'exact-nameHash-dataHash' if status=='resolved' else None,'payloadSha256':selected,'matches':ex,'reason':reason})
    counts={k:sum(x['status']==k for x in rows) for k in ['resolved','missing','conflict']}
    doc={'format':'t6-nuketown-unresolved-material-ipak-resolution-v1','traceFormat':trace['format'],'summary':{'unresolvedMaterialImageCount':len(unresolved),'tracedPackedTargetCount':len(targets),'unresolvedTraceConflictCount':len(conflict_names),'unresolvedNotInPackedTraceCount':len(missing),**counts},'unresolvedTraceConflicts':[trace_conflicts[x] for x in conflict_names],'unresolvedNotInPackedTrace':missing,'rows':rows,'containers':[p.describe() for p in ipaks],'proofBoundary':'Promotion requires the exact native traced GfxImage (nameHash,dataHash) pair, exact pair lookup in a supplied retail IPAK, CRC-validated extraction, byte-identical payload across every exact-pair match, and exact traced dimensions. Cross-root native tuple conflicts and IPAK byte/dimension conflicts are retained as unresolved evidence instead of being guessed through. dataHash-only fallback, filename/hash approximation, nearest-match behavior, and visual substitution are not admitted.'}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');print(json.dumps(doc['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
