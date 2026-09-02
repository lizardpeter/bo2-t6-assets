#!/usr/bin/env python3
"""Count strong inline T6 MaterialTechniqueSet bodies and format-8 hits.

This is a retained-corpus absence census, not a universal T6 absence proof.
It scans only after the serialized XAsset table and only accepts the strict
inline-name MaterialTechniqueSet representation used by the retail world proof
pipeline. It therefore cannot by itself promote format 8 or prove that format
8 is unused in unretained target maps.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, re, struct
from pathlib import Path
FOLLOW=0xffffffff; INSERT=0xfffffffe; MASK=(1<<29)-1
FILES={
 'common_zm':('common_zm.expanded.bin','28ff1b05ca1565f6c90acd473262e0d566fbc22fc2005c6def09fed9555b7527'),
 'code_post_gfx_mp':('extra/code_post_gfx_mp.expanded.bin','a80936d857642cefa5d68c59a539408c3f10c5169ce0af0b6ecae94ffa79c0ab'),
 'code_post_gfx_zm':('extra/code_post_gfx_zm.expanded.bin','c30851590fbc84328785953f92836046fcd622d5cfd0e81738984232994de9dc'),
 'common_patch_mp':('extra/common_patch_mp.expanded.bin','486ac8742cafad195c4e2f997fb55c77ffd49fdbec78ba516a477f78d577420c'),
 'en_code_post_gfx_mp':('extra/en_code_post_gfx_mp(1).expanded.bin','e9e1c4223b5685dd3dc1d47b972ec41a8005cd1d60c4102d5cf8aa9404a306cb'),
 'en_code_post_gfx_zm':('extra/en_code_post_gfx_zm.expanded.bin','9788386fdf779181448c0f857d0fd6c7cf737e4c1d9c1f7f2cbcdf30df709263'),
 'patch_ui_mp':('extra/patch_ui_mp.expanded.bin','4b71d2ca8c62f661fb5386b177ed2816be8540295765d14e2c5873a03d467fd8'),
 'patch_ui_zm':('extra/patch_ui_zm.expanded.bin','7fac3cb492373d5ed074581dd482bbdfb26563849a02365d5e8e4a6233d15a5f'),
 'ui_mp':('extra/ui_mp.expanded.bin','2502b33b8fff182d1f5811f24d27e5af5610491995d756ab54d70a7740719337'),
 'ui_zm':('extra/ui_zm.expanded.bin','ce461e8c7066085d95081f0e3fa408d54e48aa75cd368c4b61a9e7f92bf14d83'),
 'common_mp':('mp/common_mp(2).expanded.bin','fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce'),
 'mp_hijacked':('mp/mp_hijacked.expanded.bin','8bae6fdafd459f3fa6794a093a895c3c12ad3ca3f37ab83170a966884d54d42b'),
 'mp_nuketown_2020':('mp/mp_nuketown_2020.expanded.bin','7e791fb90a085f3bff9e0df895e5a232fa91cc43bcd0027225fe811f7891d505'),
 'mp_raid':('mp/mp_raid.expanded.bin','d3874c5981a01d75b72c9584e0e7d8af6132f28135f1a1ec6c4db2b9ac5037f8'),
 'patch_mp':('mp/patch_mp(2).expanded.bin','1bd82b0e99fcea3a9cb1c2342634f1da0d699b3fdadfa9f7c7fe15595952a7b9'),
 'patch_zm':('patch_zm.expanded.bin','3a5df2757981c0ae5d7963f41f6b621349b2604efd6360f3e7bb0fe145a6c499'),
 'zm_prison':('zm_prison.expanded.bin','e9d334a173d05b2854370822bc2cb16c9d5eb6226254aaf28b726cfedc340487'),
 'zm_tomb':('zm_tomb.expanded.bin','4b4e7cff929304fe58c83a2864dc76ddb8a295b6e6c548b30cb04a514800d219'),
}

def dec(v,blocks):
 if v==0:return 'null'
 if v==FOLLOW:return 'follow'
 if v==INSERT:return 'insert'
 e=(v-1)&0xffffffff;b=e>>29;o=e&MASK
 return 'packed' if b<8 and o<blocks[b] else 'bad'

def ptr_ok(v,blocks):return v in (0,FOLLOW,INSERT) or dec(v,blocks)=='packed'

def front(d):
 blocks=struct.unpack_from('<8I',d,8);p=40
 sc,sp,dc,dp,ac,ap=struct.unpack_from('<6I',d,p);p+=24
 assert (not sc or sp==FOLLOW) and (not dc or dp==FOLLOW) and ap==FOLLOW
 for count in (sc,dc):
  if count:
   ps=struct.unpack_from(f'<{count}I',d,p);p+=4*count
   for x in ps:
    if x==FOLLOW:p=d.index(b'\0',p)+1
 assets=[struct.unpack_from('<II',d,p+8*i) for i in range(ac)]
 return blocks,assets,p+8*ac

def cstr(d,p):
 e=d.find(b'\0',p,min(len(d),p+512))
 if e<=p:return None
 b=d[p:e]
 return b.decode('ascii') if 3<=len(b)<=500 and all(32<=x<=126 for x in b) else None

def scan(d,blocks,start):
 rows=[];off=start;rx=re.compile(r'[A-Za-z0-9_./$@+~:#-]+')
 while True:
  off=d.find(b'\xff\xff\xff\xff',off)
  if off<0:break
  if off+152<len(d) and d[off+4]<=8 and d[off+5:off+8]==b'\0\0\0':
   ps=struct.unpack_from('<36I',d,off+8)
   if any(ps) and all(ptr_ok(x,blocks) for x in ps):
    name=cstr(d,off+152)
    if name and len(name)<=180 and rx.fullmatch(name):rows.append((off,d[off+4],name))
  off+=1
 return rows

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 per=[];total=0;fmt8=[];dist=collections.Counter()
 for zone,(rel,sha) in FILES.items():
  p=a.root/rel;d=p.read_bytes();got=hashlib.sha256(d).hexdigest();assert got==sha,(zone,got)
  blocks,assets,start=front(d);rows=scan(d,blocks,start);c=collections.Counter(fmt for _,fmt,_ in rows);hits=[{'start':o,'name':n} for o,fmt,n in rows if fmt==8]
  total+=len(rows);dist.update(c);fmt8.extend({'zone':zone,**x} for x in hits)
  per.append({'zone':zone,'relativePath':rel,'expandedBytes':len(d),'expandedSha256':sha,'assetCount':len(assets),'scanStartAfterXAssetTable':start,'strongInlineTechniqueSetCount':len(rows),'formatDistribution':{str(k):v for k,v in sorted(c.items())},'format8Hits':hits})
 out={'format':'t6-retail-world-format-8-retained-absence-census-v1','producer':'tools/t6_retail_world_format_8_absence_census_v1.py','xfileCount':len(per),'strongInlineTechniqueSetCount':total,'formatDistribution':{str(k):v for k,v in sorted(dist.items())},'format8StrongInlineHitCount':len(fmt8),'format8StrongInlineHits':fmt8,'xfiles':per,'proofBoundary':{'proven':'Across these 18 exact retained expanded XFiles, the strict post-XAsset-table inline MaterialTechniqueSet classifier finds zero worldVertFormat=8 bodies.','notProven':'This is not an exhaustive absence proof for unretained T6 target maps, packed/non-inline TechniqueSet representations, or the full 31-map MP plus Zombies target corpus. It cannot promote format 8 without a direct material-bound allocation fixture or exhaustive full-target absence proof.'}}
 a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'xfiles':len(per),'strongTechniqueSets':total,'formatDistribution':out['formatDistribution'],'format8Hits':len(fmt8)},indent=2))
if __name__=='__main__':main()
