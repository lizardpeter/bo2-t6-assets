#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, hashlib
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
V3=HERE/'t6_nuketown_ipak_partial_texture_export_v3.py'
spec=importlib.util.spec_from_file_location('t6_nuketown_tex_v3',V3)
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
_component_builder=base.build_component_image_anchors
ANCHOR_SOURCES={}

def _catalog(mats):
    packed=set(); inline=[]; seen=set(); byname=defaultdict(list)
    for m in mats:
        for t in m.get('textures',[]):
            im=t.get('image') or {}; p=im.get('pointer') or {}
            if not im.get('inline') and p.get('kind')=='offset' and p.get('block')==5:
                packed.add(p.get('offset'))
            if im.get('inline') and im.get('name') and im.get('start') is not None:
                k=(im['start'],im['name'])
                if k not in seen: seen.add(k); inline.append(k)
    inline.sort()
    for s,n in inline: byname[n].append(s)
    return packed,inline,byname

def _validate_order_rule(direct,packed,inline,byname):
    mapping={v:n for (b,v),n in direct.items() if b==5 and len(set(byname.get(n,[])))==1}
    raw={v:byname[n][0] for v,n in mapping.items()}
    def one_hidden(hidden_set):
        vals=sorted(mapping); rem=set(vals)-set(hidden_set)
        lo=max(v for v in rem if v<min(hidden_set)); hi=min(v for v in rem if v>max(hidden_set))
        known={mapping[v] for v in rem}; vp=sorted(v for v in packed if lo<v<hi and v not in rem)
        ri=[(s,n) for s,n in inline if raw[lo]<s<raw[hi] and n not in known]
        if len(vp)!=len(ri) or not all(h in vp for h in hidden_set): return None
        mp={v:n for v,(s,n) in zip(vp,ri)}
        return all(mp[h]==mapping[h] for h in hidden_set)
    vals=sorted(mapping)
    single_rec=single_ok=0
    for i,v in enumerate(vals):
        if i==0 or i==len(vals)-1: continue
        r=one_hidden([v])
        if r is not None: single_rec+=1; single_ok+=int(r)
    runs={}
    for k in (2,3,4,5):
        rec=ok=0
        for i in range(1,len(vals)-k):
            r=one_hidden(vals[i:i+k])
            if r is not None: rec+=1; ok+=int(r)
        runs[k]={'recoverable':rec,'correct':ok,'wrong':rec-ok}
    result={'singleHidden':{'recoverable':single_rec,'correct':single_ok,'wrong':single_rec-single_ok},
            **{f'hiddenRun{k}':v for k,v in runs.items()}}
    expected={'singleHidden':(80,80,0),'hiddenRun2':(77,77,0),'hiddenRun3':(75,75,0),'hiddenRun4':(73,73,0),'hiddenRun5':(71,71,0)}
    for key,(r,c,w) in expected.items():
        got=result[key]
        if (got['recoverable'],got['correct'],got['wrong'])!=(r,c,w):
            raise ValueError(f'order-rule regression drift {key}: {got}')
    return result

def build_order_image_anchors(mats,direct):
    packed,inline,byname=_catalog(mats)
    validation=_validate_order_rule(direct,packed,inline,byname)
    mapping={v:n for (b,v),n in direct.items() if b==5 and len(set(byname.get(n,[])))==1}
    raw={v:byname[n][0] for v,n in mapping.items()}; initial=len(mapping); rounds=[]
    while True:
        vals=sorted(mapping); known=set(mapping.values()); additions={}; addraw={}; intervals=[]
        for lo,hi in zip(vals,vals[1:]):
            vp=sorted(v for v in packed if lo<v<hi and v not in mapping)
            ri=[(s,n) for s,n in inline if raw[lo]<s<raw[hi] and n not in known]
            if vp and len(vp)==len(ri):
                pairs=[]
                for v,(s,n) in zip(vp,ri): additions[v]=n; addraw[v]=s; pairs.append({'virtualOffset':v,'rawStart':s,'image':n})
                intervals.append({'lowerVirtualOffset':lo,'upperVirtualOffset':hi,'count':len(vp),'pairs':pairs})
        if not additions: break
        rev=defaultdict(list)
        for v,n in {**mapping,**additions}.items(): rev[n].append(v)
        dup={n:vs for n,vs in rev.items() if len(vs)>1}
        if dup: raise ValueError(f'order closure duplicate identity: {list(dup.items())[:3]}')
        mapping.update(additions); raw.update(addraw); rounds.append({'added':len(additions),'intervals':intervals})
    new={(5,v):n for v,n in mapping.items() if (5,v) not in direct}
    proof={'initialUniqueStartDirectAnchors':initial,
           'orderClosureRounds':[{'round':i+1,'added':r['added'],'intervalCount':len(r['intervals'])} for i,r in enumerate(rounds)],
           'newOrderPromotions':len(new),'finalMappedBlock5Pointers':len(mapping),
           'leaveOneOutValidation':validation,
           'newMappings':[{'block':5,'virtualOffset':v,'rawStart':raw[v],'image':n} for (b,v),n in sorted(new.items())]}
    return new,proof

def combined_builder(mats):
    global ANCHOR_SOURCES
    direct,component_proof=_component_builder(mats)
    order,order_proof=build_order_image_anchors(mats,direct)
    anchors=dict(direct); anchors.update(order)
    ANCHOR_SOURCES={k:'component-table-anchor' for k in direct}; ANCHOR_SOURCES.update({k:'serializer-order-closure' for k in order})
    return anchors,{'componentTable':component_proof,'serializerOrder':order_proof,'totalPackedPointerImageAnchors':len(anchors)}

def first_semantic_image(mat,semantic,anchors):
    for t in mat.get('textures',[]):
        if t.get('semantic')!=semantic: continue
        im=t.get('image') or {}
        if im.get('inline') and im.get('name'): return t,im,'inline'
        p=im.get('pointer') or {}; key=(p.get('block'),p.get('offset'))
        n=anchors.get(key) if p.get('kind')=='offset' else None
        if n:
            return t,{'inline':False,'name':n,'resolvedPackedPointer':{'block':key[0],'offset':key[1]}},ANCHOR_SOURCES.get(key,'packed-anchor')
        return t,None,None
    return None,None,None

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build(glb,materials,ipak,out,manifest):
    base.build_component_image_anchors=combined_builder; base.first_semantic_image=first_semantic_image
    m=base.build(glb,materials,ipak,out,manifest)
    js,binbuf=base.read_glb(out)
    t6=js.setdefault('extras',{}).setdefault('T6',{})
    if 'realTexturePartialV3' in t6: t6['realTexturePartialV4']=t6.pop('realTexturePartialV3')
    t6['realTexturePartialV4']['proofBoundary']='Exact first-semantic image only when inline named or exact-resolved by component-table/serializer-order evidence and physically present in the map-specific IPAK.'
    base.write_glb(out,js,binbuf)
    m['format']='t6-nuketown-ipak-partial-real-texture-export-v4'
    m['outputGlb']={'file':out.name,'sha256':sha(out),'bytes':out.stat().st_size}
    m['proofBoundary']='Real image-backed partial export. Packed image identities are promoted only by zero-conflict generated/component semantic-table alignment or the leave-one-out-validated serializer-order closure. IPAK extraction remains hash-selected, LZO/raw decoded, CRC-validated, IWI27 decoded, and conservatively bound to TEXCOORD_0.'
    manifest.write_text(json.dumps(m,indent=2,sort_keys=True)+'\n')
    return m

def main():
    a=argparse.ArgumentParser(); a.add_argument('--glb',type=Path,required=True); a.add_argument('--materials',type=Path,required=True); a.add_argument('--ipak',type=Path,required=True); a.add_argument('--out',type=Path,required=True); a.add_argument('--manifest',type=Path,required=True); q=a.parse_args()
    m=build(q.glb,q.materials,q.ipak,q.out,q.manifest); print(json.dumps(m['summary'],indent=2)); print(m['outputGlb'])
if __name__=='__main__': main()
