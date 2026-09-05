#!/usr/bin/env python3
from __future__ import annotations

import argparse,base64,hashlib,importlib.util,json,re,zlib
from collections import defaultdict
from pathlib import Path

from t6_ipak_core import HttpRangeSource, IpakEntry, T6Ipak

URL='https://r2.houseofkublai.com/bo2/zone/all/base.ipak'
BASE_BYTES=2614362112
ADMISSIBLE={'exact-pair','unique-data-hash'}
HERE=Path(__file__).resolve().parent
BASE_PATH=HERE/'t6_nuketown_ipak_partial_texture_export_v2.py'
DEC_PATH=HERE/'t6_iwi27_png_v1.py'
spec=importlib.util.spec_from_file_location('t6_texture_base',BASE_PATH)
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
dspec=importlib.util.spec_from_file_location('t6_iwi27_png',DEC_PATH)
dec=importlib.util.module_from_spec(dspec); dspec.loader.exec_module(dec)


def sha256(b:bytes)->str: return hashlib.sha256(b).hexdigest()

def load_canonical(path:Path)->dict:
    return json.loads(zlib.decompress(base64.b64decode(path.read_text().strip())))

def safe_name(name:str)->str:
    s=re.sub(r'[^A-Za-z0-9_.-]+','_',name).strip('._'); return s or 'image'

def image_semantics(doc:dict)->dict[str,list[int]]:
    out=defaultdict(set)
    for m in doc['materials']:
        for t in m.get('textures',[]): out[t['image']].add(int(t['semantic']))
    return {k:sorted(v) for k,v in out.items()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--base-census',type=Path,required=True)
    ap.add_argument('--map-census',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--expected',type=int,default=185)
    a=ap.parse_args()

    doc=load_canonical(a.manifest)
    sems=image_semantics(doc)
    meta={x['image']:x for x in doc['images']}
    bc=json.loads(a.base_census.read_text())
    mc=json.loads(a.map_census.read_text())
    maprows={r['image']:r for r in mc['rows']}
    candidates=[
        r for r in bc['rows']
        if r['state'] in ADMISSIBLE and maprows[r['image']]['state'] not in ADMISSIBLE
    ]
    if len(candidates)!=a.expected:
        raise ValueError(f'base-additional candidates {len(candidates)} != {a.expected}')

    source=HttpRangeSource(
        URL,
        expected_size=BASE_BYTES,
        user_agent='bo2-t6-assets-world-base-extract/2',
        timeout=120,
    )
    ipak=T6Ipak.open(source)
    if ipak.total_size!=BASE_BYTES:
        raise ValueError(f'unexpected base.ipak bytes {ipak.total_size}')
    entryset=set(ipak.entries)

    a.out_dir.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,r in enumerate(candidates):
        name=r['image']
        e=IpakEntry.from_tuple(tuple(int(x) for x in r['chosenEntry']))
        if e not in entryset:
            raise ValueError(f'{name}: census entry absent from live base index')
        if e.data_hash!=int(r['dataHash29']):
            raise ValueError(f'{name}: retained dataHash mismatch')
        if r['state']=='exact-pair':
            if e.name_hash!=int(r['nameHash']):
                raise ValueError(f'{name}: exact pair nameHash mismatch')
            if ipak.exact(int(r['nameHash']),int(r['dataHash29']))!=e:
                raise ValueError(f'{name}: exact pair no longer resolves to retained entry')
        elif r['state']=='unique-data-hash':
            if ipak.unique_data(e.data_hash)!=e:
                raise ValueError(f'{name}: dataHash no longer unique')
        else:
            raise ValueError(f'{name}: inadmissible census state {r["state"]!r}')

        reads_before=len(source.range_reads)
        iwi=ipak.extract(e)
        if len(source.range_reads)!=reads_before+1:
            raise ValueError(f'{name}: expected exactly one payload range read')
        rr=source.range_reads[-1]

        fmt,flags,w,h,d,gamma,sizes=base.parse_iwi27(iwi)
        dims=(int(r['width']),int(r['height']),int(r['depth']))
        if (w,h,d)!=dims:
            raise ValueError(f'{name}: IWI dimensions {(w,h,d)} != retained {dims}')
        im=meta[name]
        if (w,h,d)!=(int(im['width']),int(im['height']),int(im['depth'])):
            raise ValueError(f'{name}: canonical dimension mismatch')

        stem=f'{i:03d}_{safe_name(name)}'
        iwif=stem+'.iwi'
        (a.out_dir/iwif).write_bytes(iwi)
        ss=sems.get(name,[])
        roles=[]
        if 5 in ss: roles.append(('normal',True))
        if any(s!=5 for s in ss) or not roles: roles.append(('colorlike',False))
        variants=[]
        for role,is_normal in roles:
            png,pmeta=dec.iwi_top_png(iwi,normal_semantic=is_normal)
            fn=f'{stem}.{role}.png'
            (a.out_dir/fn).write_bytes(png)
            variants.append({
                'role':role,
                'normalSemanticDecode':is_normal,
                'file':fn,
                'bytes':len(png),
                'sha256':sha256(png),
                'decodeMeta':pmeta,
            })
        rows.append({
            'image':name,
            'state':r['state'],
            'retainedNameHash':int(r['nameHash']),
            'retainedDataHash29':int(r['dataHash29']),
            'ipakEntry':list(e.as_tuple()),
            'contentRange':rr['contentRange'],
            'semanticSet':ss,
            'dimensions':[w,h,d],
            'format':fmt,
            'flags':flags,
            'gamma':gamma,
            'iwiFile':iwif,
            'iwiBytes':len(iwi),
            'iwiSha256':sha256(iwi),
            'crc29Validated':True,
            'dimensionsValidated':True,
            'pngVariants':variants,
        })

    open_reads=source.range_reads[:3]
    if len(open_reads)!=3:
        raise ValueError(f'unexpected IPAK open range count {len(open_reads)}')
    report={
        'format':'t6-nuketown-live-world-base-ipak-texture-extraction-v1',
        'source':{
            'url':URL,
            'bytes':ipak.total_size,
            'indexEntryCount':len(ipak.entries),
            'headContentRange':open_reads[1]['contentRange'],
            'indexContentRange':open_reads[2]['contentRange'],
            'headSha256':sha256(ipak.header_bytes),
            'indexSha256':sha256(ipak.index_bytes),
            'networkBytes':source.network_bytes,
            'rangeReadCount':len(source.range_reads),
            'resolver':'tools/t6_ipak_core.py',
            'resolverPolicy':ipak.provenance()['policy'],
        },
        'summary':{
            'baseAdditionalCandidates':len(candidates),
            'validatedPayloads':len(rows),
            'exactPairPayloads':sum(r['state']=='exact-pair' for r in rows),
            'uniqueDataHashPayloads':sum(r['state']=='unique-data-hash' for r in rows),
            'normalSemanticImages':sum(5 in r['semanticSet'] for r in rows),
            'colorlikeSemanticImages':sum(any(s!=5 for s in r['semanticSet']) for r in rows),
            'pngVariantCount':sum(len(r['pngVariants']) for r in rows),
        },
        'rows':rows,
        'proofBoundary':(
            'Only live images not already covered by the pinned map IPAK are extracted. '
            'Each base.ipak row must remain census-admissible against a freshly range-read '
            'retail base index through the shared T6 IPAK core. Its streamed dataHash must '
            'equal the canonical retained CRC29; decompressed bytes must recompute that CRC29; '
            'IWI27 must parse; retained dimensions must match exactly; BC1, BC2/DXT3, BC3 and '
            'BC5/DXN top mips are decoded only then.'
        ),
    }
    (a.out_dir/'TEXTURE_EXTRACTION_V1.json').write_text(
        json.dumps(report,indent=2,sort_keys=True)+'\n'
    )
    print(json.dumps(report['summary'],indent=2,sort_keys=True))
    print('networkBytes',source.network_bytes)

if __name__=='__main__': main()
