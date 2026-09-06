#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
TOOL=HERE/'t6_playeranim_retail_resolver_v2.py'
def main():
    with tempfile.TemporaryDirectory() as td:
        r=Path(td); pa=r/'playeranim.script'; xa=r/'xanim.json'; sk=r/'skel.json'; out=r/'out.json'
        pa.write_text('both pb_sprint_RPG\n',encoding='latin1')
        xa.write_text(json.dumps([{'name':'pb_sprint_rpg','boneNames':['j_mainroot'],'numFrames':5,'frameRate':30.0,'rawStructOffset':123}]))
        sk.write_text(json.dumps({'skeleton':{'bones':[{'name':'j_mainroot'}]}}))
        q=subprocess.run([sys.executable,str(TOOL),'--playeranim',str(pa),'--xanim-json',str(xa),'--skeleton',str(sk),'--out',str(out)],capture_output=True,text=True)
        assert q.returncode==0,(q.stdout,q.stderr)
        d=json.load(open(out)); assert d['summary']['resolvedAnimationNames']==1; assert d['summary']['caseNormalizedAnimationMatches']==1
        x=d['resolved'][0]; assert x['referenceName']=='pb_sprint_RPG'; assert x['resolvedAssetName']=='pb_sprint_rpg'; assert x['caseNormalizedMatch'] is True
    with tempfile.TemporaryDirectory() as td:
        r=Path(td); pa=r/'playeranim.script'; xa=r/'xanim.json'; sk=r/'skel.json'; out=r/'out.json'
        pa.write_text('both pb_sprint_RPG\n',encoding='latin1')
        xa.write_text(json.dumps([{'name':'pb_sprint_rpg','boneNames':['j_mainroot']},{'name':'PB_SPRINT_RPG','boneNames':['j_mainroot']}]))
        sk.write_text(json.dumps({'skeleton':{'bones':[{'name':'j_mainroot'}]}}))
        q=subprocess.run([sys.executable,str(TOOL),'--playeranim',str(pa),'--xanim-json',str(xa),'--skeleton',str(sk),'--out',str(out)],capture_output=True,text=True)
        assert q.returncode!=0
        assert 'ASCII-casefold XAnim identity collisions' in (q.stderr+q.stdout)
    print('t6_playeranim_retail_resolver_v2: PASS')
    return 0
if __name__=='__main__': raise SystemExit(main())
