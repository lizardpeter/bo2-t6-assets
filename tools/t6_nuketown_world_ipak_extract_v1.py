#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
import zlib
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
REC_PATH=HERE/'t6_nuketown_ipak_streamhash_texture_recovery_v1.py'
BASE_PATH=HERE/'t6_nuketown_ipak_partial_texture_export_v2.py'
rspec=importlib.util.spec_from_file_location('t6_stream_recovery',REC_PATH)
rec=importlib.util.module_from_spec(rspec); rspec.loader.exec_module(rec)
bspec=importlib.util.spec_from_file_location('t6_texture_base',BASE_PATH)
base=importlib.util.module_from_spec(bspec); bspec.loader.exec_module(base)

ADMISSIBLE={'exact-pair','unique-data-hash'}


def sha256(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def load_canonical(path:Path)->dict:
    return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))


def safe_name(name:str)->str:
    s=re.sub(r'[^A-Za-z0-9_.-]+','_',name).strip('._')
    return s or 'image'


def image_semantics(doc:dict)->dict[str,list[int]]:
    out=defaultdict(set)
    for m in doc['materials']:
        for t in m.get('textures',[]):
            out[t['image']].add(int(t['semantic']))
    return {k:sorted(v) for k,v in out.items()}


def build(manifest_path:Path,census_path:Path,ipak_path:Path,out_dir:Path,source_label:str,expected:int|None)->dict:
    doc=load_canonical(manifest_path)
    census=json.loads(census_path.read_text())
    sems=image_semantics(doc)
    image_meta={x['image']:x for x in doc['images']}
    candidates=[r for r in census['rows'] if r['state'] in ADMISSIBLE]
    if expected is not None and len(candidates)!=expected:
        raise ValueError(f'admissible census rows {len(candidates)} != expected {expected}')

    data,data_sec,entries,by_data,by_name,lzo=rec.read_ipak(ipak_path)
    entry_set=set(entries)
    out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    for index,row in enumerate(candidates):
        name=row['image']; chosen=tuple(int(x) for x in row['chosenEntry'])
        if chosen not in entry_set:
            raise ValueError(f'{name}: chosen census entry absent from pinned IPAK index')
        dh,nh,rel,raw_size=chosen
        if dh!=int(row['dataHash29']):
            raise ValueError(f'{name}: chosen dataHash {dh:#x} != retained {int(row["dataHash29"]):#x}')
        if row['state']=='exact-pair' and nh!=int(row['nameHash']):
            raise ValueError(f'{name}: exact-pair chosen nameHash mismatch')
        if row['state']=='unique-data-hash' and len(by_data[dh])!=1:
            raise ValueError(f'{name}: dataHash no longer unique')

        iwi=rec.extract_entry(data,data_sec,chosen,lzo)
        fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
        expected_dims=(int(row['width']),int(row['height']),int(row['depth']))
        if (w,h,d)!=expected_dims:
            raise ValueError(f'{name}: IWI dimensions {(w,h,d)} != retained {expected_dims}')
        meta=image_meta[name]
        if (w,h,d)!=(int(meta['width']),int(meta['height']),int(meta['depth'])):
            raise ValueError(f'{name}: IWI dimensions disagree with canonical GfxImage')

        stem=f'{index:03d}_{safe_name(name)}'
        iwi_name=stem+'.iwi'; iwi_bytes=bytes(iwi); (out_dir/iwi_name).write_bytes(iwi_bytes)
        semantic_set=sems.get(name,[])
        variants=[]
        roles=[]
        if 5 in semantic_set: roles.append(('normal',True))
        if any(s!=5 for s in semantic_set) or not roles: roles.append(('colorlike',False))
        for role,is_normal in roles:
            png,pmeta=base.iwi_top_png(iwi_bytes,normal_semantic=is_normal)
            png_name=f'{stem}.{role}.png'
            (out_dir/png_name).write_bytes(png)
            variants.append({'role':role,'normalSemanticDecode':is_normal,'file':png_name,'bytes':len(png),'sha256':sha256(png),'decodeMeta':pmeta})

        rows.append({
            'image':name,
            'state':row['state'],
            'retainedNameHash':int(row['nameHash']),
            'retainedDataHash29':int(row['dataHash29']),
            'ipakEntry':list(chosen),
            'semanticSet':semantic_set,
            'dimensions':[w,h,d],
            'format':fmt,
            'flags':flags,
            'gamma':gamma,
            'iwiFile':iwi_name,
            'iwiBytes':len(iwi_bytes),
            'iwiSha256':sha256(iwi_bytes),
            'crc29Validated':(zlib.crc32(iwi_bytes)&0x1fffffff)==dh,
            'dimensionsValidated':True,
            'pngVariants':variants,
        })
        if not rows[-1]['crc29Validated']:
            raise ValueError(f'{name}: post-extraction CRC29 validation failed')

    report={
        'format':'t6-nuketown-live-world-ipak-texture-extraction-v1',
        'sourceLabel':source_label,
        'sourceIpak':{'file':ipak_path.name,'bytes':ipak_path.stat().st_size,'sha256':hashlib.sha256(ipak_path.read_bytes()).hexdigest(),'indexEntryCount':len(entries)},
        'canonicalManifest':manifest_path.name,
        'census':census_path.name,
        'summary':{
            'admissibleRows':len(candidates),
            'validatedPayloads':len(rows),
            'exactPairPayloads':sum(r['state']=='exact-pair' for r in rows),
            'uniqueDataHashPayloads':sum(r['state']=='unique-data-hash' for r in rows),
            'normalSemanticImages':sum(5 in r['semanticSet'] for r in rows),
            'colorlikeSemanticImages':sum(any(s!=5 for s in r['semanticSet']) for r in rows),
            'pngVariantCount':sum(len(r['pngVariants']) for r in rows),
        },
        'rows':rows,
        'proofBoundary':'Every output payload originates from a census-admissible entry in the pinned retail IPAK. The chosen dataHash must equal the retained live streamedPart CRC29; extraction recomputes CRC29 over decompressed IWI bytes; IWI27 must parse; and width/height/depth must exactly equal the canonical live GfxImage. PNGs are derived only after these checks. No filename similarity or name-hash-only row is admitted.',
    }
    (out_dir/'TEXTURE_EXTRACTION_V1.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--census',type=Path,required=True)
    ap.add_argument('--ipak',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--source-label',required=True)
    ap.add_argument('--expected',type=int)
    a=ap.parse_args()
    r=build(a.manifest,a.census,a.ipak,a.out_dir,a.source_label,a.expected)
    print(json.dumps(r['summary'],indent=2,sort_keys=True))

if __name__=='__main__':
    main()
