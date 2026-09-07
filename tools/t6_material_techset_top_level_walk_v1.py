#!/usr/bin/env python3
"""Exact T6 PC32 top-level Material/MaterialTechniqueSet serialized walker v1.

This closes the source cursor for runs of XAsset types 6 (Material) and 7
(MaterialTechniqueSet), including nested FOLLOWING/INSERT GfxImage, technique,
shader, vertex-declaration and argument allocations. Packed/null references
consume no source bytes.

The implementation follows the same retail serialization order already
validated independently by t6_clipmap_serialized_walker_v3.py and
 t6_retail_special_shader_payload_census_v1.py, but is usable from the top-level
XAsset list so early scattered TechniqueSets can be pinned to exact XAsset
indices instead of inferred from a raw name scan.

Numeric XAsset ids come only from t6_asset_types_v1.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from t6_asset_types_v1 import MATERIAL, TECHNIQUE_SET as TECHSET

FOLLOW=0xFFFFFFFF
INSERT=0xFFFFFFFE
MASK=(1<<29)-1


def dec(raw:int, blocks:tuple[int,...])->dict:
    if raw==0:return {'kind':'null','rawHex':'0x00000000'}
    if raw==FOLLOW:return {'kind':'following','rawHex':'0xFFFFFFFF'}
    if raw==INSERT:return {'kind':'insert','rawHex':'0xFFFFFFFE'}
    e=(raw-1)&0xffffffff;b=e>>29;o=e&MASK
    if b>=8 or o>=blocks[b]:raise ValueError(f'invalid zone pointer 0x{raw:08X}')
    return {'kind':'packed','rawHex':f'0x{raw:08X}','block':b,'offset':o}

def inline(raw:int)->bool:return raw in (FOLLOW,INSERT)

def cstr(d:bytes,p:int)->tuple[str,int]:
    e=d.find(b'\0',p,min(len(d),p+8192))
    if e<0:raise ValueError(f'unterminated string at {p}')
    raw=d[p:e]
    if raw and any(x<32 or x>126 for x in raw):raise ValueError(f'nonprintable string at {p}')
    return raw.decode('latin1'),e+1

class Cursor:
    def __init__(self,d:bytes,p:int,blocks:tuple[int,...]):self.d=d;self.p=p;self.blocks=blocks;self.inlineShaders=[]
    def take(self,n:int)->int:
        s=self.p;self.p+=n
        if self.p>len(self.d):raise ValueError('serialized cursor EOF')
        return s
    def string(self,raw:int):
        if inline(raw):
            s=self.p;v,self.p=cstr(self.d,self.p);return {'value':v,'sourceStart':s,'pointer':dec(raw,self.blocks)}
        return {'value':None,'sourceStart':None,'pointer':dec(raw,self.blocks)}
    def image(self)->dict:
        s=self.take(80);load=struct.unpack_from('<I',self.d,s)[0];namep=struct.unpack_from('<I',self.d,s+72)[0]
        name=self.string(namep);ld=None
        if inline(load):
            ls=self.take(12);resource=struct.unpack_from('<I',self.d,ls)[0];datap=struct.unpack_from('<I',self.d,ls+8)[0];ds=None
            if resource and inline(datap):ds=self.take(resource)
            ld={'fixedStart':ls,'resourceSize':resource,'dataPointer':dec(datap,self.blocks),'dataStart':ds}
        return {'fixedStart':s,'end':self.p,'name':name,'loadDef':ld}
    def shader(self,kind:str)->dict:
        s=self.take(16);namep,runtime,progp,size=struct.unpack_from('<IIII',self.d,s)
        if runtime:raise ValueError(f'{kind} runtime ptr nonzero at {s}')
        name=self.string(namep);program=None
        if size:
            if inline(progp):
                ps=self.take(size);raw=self.d[ps:ps+size]
                if raw[:4]!=b'DXBC':raise ValueError(f'{kind} non-DXBC inline payload at {ps}')
                program={'direct':True,'sourceStart':ps,'bytes':size,'sha256':hashlib.sha256(raw).hexdigest()}
            else:program={'direct':False,'bytes':size,'pointer':dec(progp,self.blocks)}
        elif progp:raise ValueError(f'{kind} zero-size nonnull program')
        r={'fixedStart':s,'end':self.p,'kind':kind,'name':name,'program':program};self.inlineShaders.append(r);return r
    def vdecl(self)->dict:
        s=self.take(116)
        if any(struct.unpack_from('<20I',self.d,s+36)):raise ValueError(f'bad vdecl at {s}')
        return {'fixedStart':s,'end':self.p}
    def args(self,n:int)->dict:
        s=self.take(12*n);vals=[]
        for i in range(n):
            typ,loc,size,buf,u=struct.unpack_from('<HHHHI',self.d,s+12*i)
            if typ>=8:raise ValueError(f'bad MaterialShaderArgument type {typ} at {s+12*i}')
            vals.append({'type':typ,'location':loc,'size':size,'buffer':buf,'u':u})
        literals=[]
        for i,v in enumerate(vals):
            if v['type'] in (1,7) and inline(v['u']):literals.append({'argIndex':i,'sourceStart':self.take(16),'bytes':16})
            elif v['type'] in (1,7):dec(v['u'],self.blocks)
        return {'fixedStart':s,'count':n,'values':vals,'literals':literals,'end':self.p}
    def technique(self)->dict:
        s=self.p;namep=struct.unpack_from('<I',self.d,s)[0];flags,pc=struct.unpack_from('<HH',self.d,s+4)
        if not 1<=pc<=16:raise ValueError(f'bad passCount {pc} at {s}')
        self.take(8+24*pc);passes=[]
        for j in range(pc):
            o=s+8+24*j;vd,vs,ps=struct.unpack_from('<III',self.d,o);pp,po,stable,custom,pre,mt=struct.unpack_from('<6B',self.d,o+12);pad=struct.unpack_from('<H',self.d,o+18)[0];args=struct.unpack_from('<I',self.d,o+20)[0]
            if pad:raise ValueError(f'pass padding nonzero at {o}')
            passes.append({'passIndex':j,'vertexDeclRaw':vd,'vertexShaderRaw':vs,'pixelShaderRaw':ps,'argsRaw':args,'argCount':pp+po+stable,'counts':{'perPrim':pp,'perObj':po,'stable':stable,'customSamplerFlags':custom,'precompiledIndex':pre,'materialType':mt}})
        for pa in passes:
            ch={}
            for fld,kind in [('vertexShaderRaw','vs'),('vertexDeclRaw','vd'),('pixelShaderRaw','ps'),('argsRaw','args')]:
                raw=pa[fld];pr=dec(raw,self.blocks);entry={'pointer':pr}
                if inline(raw):
                    if kind in ('vs','ps'):entry['inline']=self.shader(kind)
                    elif kind=='vd':entry['inline']=self.vdecl()
                    else:
                        if not pa['argCount']:raise ValueError('FOLLOWING args pointer with zero argCount')
                        entry['inline']=self.args(pa['argCount'])
                ch[kind]=entry
            pa['children']=ch
        name=self.string(namep)
        return {'fixedStart':s,'end':self.p,'flags':flags,'passCount':pc,'name':name,'passes':passes}
    def techset(self)->dict:
        s=self.take(152);namep=struct.unpack_from('<I',self.d,s)[0];fmt=self.d[s+4]
        if fmt>8 or self.d[s+5:s+8]!=b'\0\0\0':raise ValueError(f'bad TechniqueSet header at {s}')
        refs=list(struct.unpack_from('<36I',self.d,s+8));name=self.string(namep);tech=[]
        for slot,raw in enumerate(refs):
            p=dec(raw,self.blocks);r={'slot':slot,'pointer':p}
            if inline(raw):r['inlineTechnique']=self.technique()
            tech.append(r)
        return {'fixedStart':s,'end':self.p,'name':name,'worldVertFormat':fmt,'techniqueRefs':tech}
    def material(self)->dict:
        s=self.take(112);d=self.d
        namep=struct.unpack_from('<I',d,s)[0];tc=d[s+84];cc=d[s+85];sc=d[s+86]
        tech,tex,con,state,thermal=struct.unpack_from('<5I',d,s+92)
        if tc>64 or cc>64 or sc>64:raise ValueError(f'implausible Material counts at {s}: {tc}/{cc}/{sc}')
        name=self.string(namep);nestedTech=None
        if inline(tech):nestedTech=self.techset()
        else:dec(tech,self.blocks)
        textures=[]
        if inline(tex):
            ts=self.take(tc*16)
            defs=[]
            for i in range(tc):
                o=ts+16*i;defs.append({'slot':i,'nameHash':struct.unpack_from('<I',d,o)[0],'samplerState':d[o+6],'semantic':d[o+7],'imageRaw':struct.unpack_from('<I',d,o+12)[0]})
            for td in defs:
                p=dec(td['imageRaw'],self.blocks);td['imagePointer']=p
                if inline(td['imageRaw']):td['inlineImage']=self.image()
            textures=defs
        elif tc:raise ValueError(f'Material {s} textureCount={tc} but table not inline')
        if inline(con):self.take(cc*32)
        elif cc:raise ValueError(f'Material {s} constantCount={cc} but table not inline')
        if inline(state):self.take(sc*20)
        elif sc:raise ValueError(f'Material {s} stateBitsCount={sc} but table not inline')
        nestedThermal=None
        if inline(thermal):nestedThermal=self.material()
        else:dec(thermal,self.blocks)
        return {'fixedStart':s,'end':self.p,'name':name,'textureCount':tc,'constantCount':cc,'stateBitsCount':sc,'techniqueSetPointer':dec(tech,self.blocks),'nestedTechniqueSet':nestedTech,'textures':textures,'thermalPointer':dec(thermal,self.blocks),'nestedThermalMaterial':nestedThermal}


def parse_front(d:bytes):
    blocks=struct.unpack_from('<8I',d,8);p=40;sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,p);p+=24
    if ap!=FOLLOW:raise ValueError('XAsset array not FOLLOWING')
    for count,ptr in ((sc,sp),(dc,dp)):
        if count and ptr!=FOLLOW:raise ValueError('script/string array not FOLLOWING')
        if count:
            vals=struct.unpack_from(f'<{count}I',d,p);p+=4*count
            for raw in vals:
                if raw==FOLLOW:_,p=cstr(d,p)
    assets=[]
    for i in range(ac):
        typ,raw=struct.unpack_from('<II',d,p+8*i);assets.append({'xassetIndex':i,'type':typ,'headerRaw':raw})
    return tuple(blocks),assets,p+8*ac


def walk(d:bytes,start_asset:int,end_asset:int,source_start:int)->dict:
    blocks,assets,_=parse_front(d);c=Cursor(d,source_start,blocks);rows=[]
    for q in range(start_asset,end_asset+1):
        a=assets[q]
        if a['headerRaw'] not in (FOLLOW,INSERT):raise ValueError(f'XAsset {q} top-level header is not inline')
        before=c.p
        if a['type']==MATERIAL:r=c.material()
        elif a['type']==TECHSET:r=c.techset()
        else:raise ValueError(f'unsupported top-level XAsset type {a["type"]} at {q}; walker is intentionally fail-closed')
        r.update({'xassetIndex':q,'xassetType':a['type'],'sourceStart':before,'sourceEnd':c.p});rows.append(r)
    return {'format':'t6-material-techset-top-level-walk-v1','startAssetIndex':start_asset,'endAssetIndex':end_asset,'sourceStart':source_start,'sourceEnd':c.p,'rows':rows,'inlineShaderCount':len(c.inlineShaders),'directInlineShaders':[x for x in c.inlineShaders if x.get('program') and x['program'].get('direct')]}


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('expanded',type=Path);ap.add_argument('--start-asset',type=int,required=True);ap.add_argument('--end-asset',type=int,required=True);ap.add_argument('--source-start',type=lambda x:int(x,0),required=True);ap.add_argument('--expect-end',type=lambda x:int(x,0));ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    d=a.expanded.read_bytes();o=walk(d,a.start_asset,a.end_asset,a.source_start);o['expandedSha256']=hashlib.sha256(d).hexdigest()
    if a.expect_end is not None:
        o['expectedEnd']=a.expect_end;o['expectedEndMatches']=o['sourceEnd']==a.expect_end
        if not o['expectedEndMatches']:raise SystemExit(f'end {o["sourceEnd"]} != expected {a.expect_end}')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(o,indent=2,sort_keys=True)+'\n');print(json.dumps({'sourceEnd':o['sourceEnd'],'assetCount':len(o['rows']),'inlineShaderCount':o['inlineShaderCount']},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
