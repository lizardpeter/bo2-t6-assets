#!/usr/bin/env python3
from __future__ import annotations
import json
import tempfile
from pathlib import Path
import t6_seal6_native_material_conflict_report_v1 as mod

TARGET='mc/test_material'

def write(root:Path, *, sort_key:int, image:str='img_c'):
    p=root/'materials'/f'{TARGET}.json'; p.parent.mkdir(parents=True,exist_ok=True)
    doc={'_game':'t6','_type':'material','techniqueSet':'mc/test_techset','sortKey':sort_key,
         'textures':[{'semantic':'colorMap','name':'colorMap','image':image,'samplerState':{'filter':'linear'}}]}
    p.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8')

def main()->int:
    with tempfile.TemporaryDirectory() as td:
        a=Path(td)/'a';b=Path(td)/'b';a.mkdir();b.mkdir()
        write(a,sort_key=1);write(b,sort_key=2)
        r=mod.build([('a',a),('b',b)],[TARGET]);m=r['materials'][0]
        assert not m['byteIdenticalAcrossCopies']
        assert m['textureRecordsStructurallyIdenticalAcrossCopies']
        assert m['techniqueSetIdenticalAcrossCopies']
        assert m['topLevelFieldsDifferingAcrossCopies']==['sortKey']
        assert not m['activeRetailClientOwnerResolved']
        write(b,sort_key=2,image='img_other')
        r=mod.build([('a',a),('b',b)],[TARGET]);m=r['materials'][0]
        assert not m['textureRecordsStructurallyIdenticalAcrossCopies']
        assert 'textures' in m['topLevelFieldsDifferingAcrossCopies']
    print('PASS t6_seal6_native_material_conflict_report_v1')
    return 0
if __name__=='__main__': raise SystemExit(main())
