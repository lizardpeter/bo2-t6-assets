#!/usr/bin/env python3
"""Join exact Nuketown generated final-output input identities into a compact runtime-input census.

This is deliberately narrower than the full replay contract: it needs no guessed
runtime values and no material-texture disambiguation. It answers, for each exact
material/TechniqueSet owner, which final-output cbuffer and texture inputs are:
- static material-owned sources;
- exact T6 dynamic code constants/samplers;
- still unresolved by source identity.

Every dynamic identity must already be proven by the corrected v2 OAT namespace
binding and pinned T6 enum/accessor tables.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

FINAL='t6-generated-slot4-final-output-symbolic-v3'
CB='t6-generated-final-output-cbuffer-signature-v2'
CC='t6-generated-final-output-code-constant-identity-v2'
TEX='t6-generated-final-output-texture-resource-binding-v2'
CS='t6-generated-final-output-code-sampler-identity-v2'
FMT='t6-nuketown-generated-final-output-runtime-input-census-v1'

def jhash(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def idx(rows,key,label):
    out={}
    for r in rows:
        k=str(r.get(key) or '')
        if not k or k in out: raise RuntimeError(f'invalid/duplicate {label} {k!r}')
        out[k]=r
    return out

def assignment(rows,tech,label):
    xs=[r for r in rows if str(r.get('techniqueSet') or '')==tech]
    if len(xs)!=1: raise RuntimeError(f'{label}: TechniqueSet {tech!r} assignment count {len(xs)}')
    return xs[0]

def code_const(shader,symbol,tech):
    xs=[r for r in shader.get('assignments',[]) if str(r.get('symbol') or '')==symbol and str(r.get('techniqueSet') or '')==tech]
    if len(xs)>1: raise RuntimeError(f'{symbol}/{tech}: duplicate code-constant identities')
    return xs[0] if xs else None

def build(final,cb,cc,tex,cs):
    for d,f,l in ((final,FINAL,'final'),(cb,CB,'cbuffer'),(cc,CC,'code constants'),(tex,TEX,'textures'),(cs,CS,'code samplers')):
        if d.get('format')!=f: raise RuntimeError(f'{l} format drift: {d.get("format")!r}')
    final_shaders=idx(final.get('shaders',[]),'sha256','final shader')
    cb_shaders=idx(cb.get('shaders',[]),'sha256','cbuffer shader')
    cc_shaders=idx(cc.get('shaders',[]),'sha256','code-constant shader')
    tex_shaders=idx(tex.get('shaders',[]),'sha256','texture shader')
    cs_shaders=idx(cs.get('shaders',[]),'sha256','code-sampler shader')
    expected=set(final_shaders)
    for label,d in (('cbuffer',cb_shaders),('code-constant',cc_shaders),('texture',tex_shaders),('code-sampler',cs_shaders)):
        if set(d)!=expected: raise RuntimeError(f'{label} shader identity set differs from final DAG')
    owners=idx(final.get('materials',[]),'material','final material')
    rows=[]; dyn_c=collections.Counter(); dyn_s=collections.Counter(); unresolved=collections.Counter()
    unique_c={};unique_s={}
    for material,owner in sorted(owners.items()):
        sha=str(owner.get('pixelShaderSha256') or ''); tech=str(owner.get('techniqueSet') or '')
        if sha not in expected or not tech: raise RuntimeError(f'{material}: invalid owner identity')
        cb_inputs=[]
        for item in cb_shaders[sha].get('usedCbufferSymbols',[]):
            symbol=str(item.get('symbol') or ''); a=assignment(item.get('techniqueAssignments',[]),tech,f'{material}/{symbol}')
            code=code_const(cc_shaders[sha],symbol,tech)
            cls=str(a.get('sourceClass') or '')
            if code is not None:
                kind='t6CodeConstantDynamic'
                ident={k:code.get(k) for k in ('accessor','resolvedEnumSymbol','resolvedEnumValue','resolvedEnumValueHex','updateFrequency','arrayIndex','bindingMode','sourceNamespace')}
                key=(str(ident['accessor']),int(ident['resolvedEnumValue']),str(ident.get('arrayIndex')))
                dyn_c[key]+=1; unique_c[key]=ident
            elif cls=='material':
                kind='materialConstant'
                ident=None
            else:
                kind='unresolvedCbufferSource';ident=None;unresolved['cbuffer']+=1
            cb_inputs.append({'symbol':symbol,'sourceClass':cls,'sourceExpression':a.get('sourceExpression'),'kind':kind,'dynamicIdentity':ident})
        tex_inputs=[]
        csrow=cs_shaders[sha]
        for resource in csrow.get('resources',[]):
            name=str(resource.get('resource') or ''); a=assignment(resource.get('techniqueAssignments',[]),tech,f'{material}/{name}')
            code=a.get('codeSamplerIdentity'); cls=str(a.get('sourceClass') or '')
            if isinstance(code,dict):
                kind='t6CodeSamplerDynamic'
                ident={k:code.get(k) for k in ('accessor','enumSymbol','enumValue','enumValueHex','updateFrequency','techFlags','customSamplerIndex')}
                key=(str(ident['accessor']),int(ident['enumValue']))
                dyn_s[key]+=1; unique_s[key]=ident
            elif cls=='material':
                kind='materialTexture';ident=None
            else:
                kind='unresolvedTextureSource';ident=None;unresolved['texture']+=1
            tex_inputs.append({'resource':name,'sourceClass':cls,'sourceExpression':a.get('sourceExpression'),'bindingMode':a.get('bindingMode'),'kind':kind,'dynamicIdentity':ident})
        rows.append({'material':material,'techniqueSet':tech,'pixelShaderSha256':sha,'cbufferInputs':cb_inputs,'textureInputs':tex_inputs})
    dyn_const=[{**unique_c[k],'materialInputOccurrenceCount':dyn_c[k]} for k in sorted(unique_c)]
    dyn_sampler=[{**unique_s[k],'materialInputOccurrenceCount':dyn_s[k]} for k in sorted(unique_s)]
    summary={
      'programCount':len(expected),'materialCount':len(rows),
      'cbufferInputOccurrenceCount':sum(len(r['cbufferInputs']) for r in rows),
      'textureInputOccurrenceCount':sum(len(r['textureInputs']) for r in rows),
      'dynamicCodeConstantOccurrenceCount':sum(dyn_c.values()),
      'uniqueDynamicCodeConstantSlotCount':len(dyn_const),
      'dynamicCodeSamplerOccurrenceCount':sum(dyn_s.values()),
      'uniqueDynamicCodeSamplerSlotCount':len(dyn_sampler),
      'materialConstantOccurrenceCount':sum(x['kind']=='materialConstant' for r in rows for x in r['cbufferInputs']),
      'materialTextureOccurrenceCount':sum(x['kind']=='materialTexture' for r in rows for x in r['textureInputs']),
      'unresolvedCbufferSourceOccurrenceCount':unresolved['cbuffer'],
      'unresolvedTextureSourceOccurrenceCount':unresolved['texture'],
    }
    return {'format':FMT,'summary':summary,'dynamicCodeConstants':dyn_const,'dynamicCodeSamplers':dyn_sampler,'materials':rows,'rowsSha256':jhash(rows),'proofBoundary':'Exact join over the canonical 120 generated Nuketown material owners and 34 exact slot-4 pixel-shader DAGs. Dynamic code inputs are promoted only from corrected current-OAT namespace evidence plus pinned T6 source-table enum/accessor identities. Material-owned inputs are classified only as material-owned here; their values/images are a separate proof. Any source not closed by those identities remains explicit unresolved evidence. Runtime values/resources and physical lighting meanings are not inferred.'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--final',type=Path,required=True);p.add_argument('--cbuffer',type=Path,required=True)
    p.add_argument('--code-constants',type=Path,required=True);p.add_argument('--textures',type=Path,required=True)
    p.add_argument('--code-samplers',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    d=build(*[json.loads(x.read_text()) for x in (a.final,a.cbuffer,a.code_constants,a.textures,a.code_samplers)])
    if d['summary']['programCount']!=34 or d['summary']['materialCount']!=120: raise SystemExit(f'Nuketown population drift: {d["summary"]}')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
    print(json.dumps(d['summary'],indent=2,sort_keys=True))
if __name__=='__main__':main()
