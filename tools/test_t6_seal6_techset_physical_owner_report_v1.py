#!/usr/bin/env python3
from __future__ import annotations
import tempfile
from pathlib import Path
import t6_seal6_techset_physical_owner_report_v1 as mod

TS='mc/test_ts'

def touch(root:Path):
    p=root/'techsets'/f'{TS}.techset';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture\n')

def rec(label,root,sig,parent='a'*64,binding='b'*64):
    return {'rootLabel':label,'root':str(root),'relativeFile':f'techsets/{TS}.techset','bytes':10,'sha256':parent,'bindingStructureSha256':binding,'fullParentChildSignatureSha256':sig,'bindings':[{'technique':'pimp_test','types':['lit'],'parsedPassStageIdentitySha256':sig,'passCount':1,'techniqueFile':{},'passes':[]}]}

def main()->int:
    with tempfile.TemporaryDirectory() as td:
        a=Path(td)/'a';b=Path(td)/'b';a.mkdir();b.mkdir();touch(a);touch(b)
        real=mod._owner_record
        mod._owner_record=lambda label,root,techset: rec(label,root,'c'*64)
        try:r=mod.build([('a',a),('b',b)],[TS])
        finally:mod._owner_record=real
        row=r['techniqueSets'][0]
        assert row['physicalOwnerCount']==2
        assert row['parentChildShaderSignatureInvariantAcrossOwners'] is True
        assert row['activeRetailClientOwnerResolved'] is True
        assert r['summary']['unresolvedRetailClientOwnerTechniqueSets']==0

        def divergent(label,root,techset):
            return rec(label,root,('c' if label=='a' else 'd')*64,parent=('a' if label=='a' else 'e')*64)
        mod._owner_record=divergent
        try:r=mod.build([('a',a),('b',b)],[TS])
        finally:mod._owner_record=real
        row=r['techniqueSets'][0]
        assert row['parentChildShaderSignatureInvariantAcrossOwners'] is False
        assert row['activeRetailClientOwnerResolved'] is False
        assert r['summary']['divergentParentChildSignatureTechniqueSets']==1
        assert r['summary']['unresolvedRetailClientOwnerTechniqueSets']==1
    print('PASS t6_seal6_techset_physical_owner_report_v1')
    return 0
if __name__=='__main__':raise SystemExit(main())
