from __future__ import annotations
import asyncio, aiohttp, csv, json, re, zlib
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlsplit

OUT=Path("out")
OUT.mkdir(exist_ok=True)
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
BASE="https://assets.webkinz.com/swf/item/"
PLAY="https://play.webkinz.com/"
TIMEOUT=aiohttp.ClientTimeout(total=15,connect=6,sock_read=10)

src=max(Path("work/src").rglob("DoAction.as"),key=lambda p:p.stat().st_size)
text=src.read_text(errors="ignore")
ids=[int(x) for x in re.findall(r'itemObject\.ITM(\d+)\s*=',text)]
ids=sorted(set(ids))

abs_rx=re.compile(rb'https?://[^\x00\s"\'<>\\)]+',re.I)
file_rx=re.compile(
    rb'(?i)(?:[A-Za-z0-9_.%+() -]+/)*[A-Za-z0-9_.%+() -]+\.'
    rb'(?:swf|xml|mp3|wav|flv|png|jpg|jpeg|gif|json|js|css|txt|dat|bin)'
    rb'(?:\?[^\x00\s"\'<>\\)]{0,120})?'
)

def swf_uncompress(raw:bytes)->bytes:
    if len(raw)>=8 and raw[:3]==b"CWS":
        try:
            return b"FWS"+raw[3:8]+zlib.decompress(raw[8:])
        except Exception:
            return raw
    return raw

async def head_one(session,url,kind,iid,sem):
    async with sem:
        try:
            async with session.head(url,allow_redirects=True,timeout=TIMEOUT) as r:
                ct=(r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                cl=int(r.headers.get("Content-Length") or 0)
                return (url,kind,iid,r.status,ct,cl,str(r.url))
        except Exception as e:
            return (url,kind,iid,0,type(e).__name__,0,url)

async def head_batch(rows,limit=32):
    conn=aiohttp.TCPConnector(limit=limit,limit_per_host=limit,ttl_dns_cache=300)
    sem=asyncio.Semaphore(limit)
    out=[]
    async with aiohttp.ClientSession(headers={"User-Agent":UA},connector=conn) as s:
        tasks=[asyncio.create_task(head_one(s,*r,sem)) for r in rows]
        for i,f in enumerate(asyncio.as_completed(tasks),1):
            out.append(await f)
            if i%10000==0: print("head",i,flush=True)
    return out

def valid_swf_head(r):
    return r[3] in (200,206) and r[4] in ("application/x-shockwave-flash","application/octet-stream") and r[5]>0

initial=[]
for iid in ids:
    initial.append((f"{BASE}{iid}/item.swf","item_swf",iid))
    initial.append((f"{BASE}{iid}/character.swf","character_swf",iid))
heads=asyncio.run(head_batch(initial))
roots=[r for r in heads if valid_swf_head(r)]

with (OUT/"root-special-swfs.tsv").open("w",newline="",encoding="utf-8") as f:
    w=csv.writer(f,delimiter="\t")
    w.writerow(["url","kind","descriptor_id","status","content_type","content_length","final_url"])
    w.writerows(sorted(roots))

async def get_one(session,row,sem,max_bytes=6_500_000):
    url,kind,iid,*_=row
    async with sem:
        try:
            async with session.get(url,allow_redirects=True,timeout=aiohttp.ClientTimeout(total=30,connect=7,sock_read=20)) as r:
                ct=(r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                cl=int(r.headers.get("Content-Length") or 0)
                if r.status!=200 or cl>max_bytes:
                    return (url,kind,iid,r.status,ct,b"",str(r.url))
                return (url,kind,iid,r.status,ct,await r.read(),str(r.url))
        except Exception as e:
            return (url,kind,iid,0,type(e).__name__,b"",url)

async def get_batch(rows,limit=16):
    conn=aiohttp.TCPConnector(limit=limit,limit_per_host=limit,ttl_dns_cache=300)
    sem=asyncio.Semaphore(limit)
    out=[]
    async with aiohttp.ClientSession(headers={"User-Agent":UA},connector=conn) as s:
        tasks=[asyncio.create_task(get_one(s,r,sem)) for r in rows]
        for i,f in enumerate(asyncio.as_completed(tasks),1):
            out.append(await f)
            if i%1000==0: print("get",i,flush=True)
    return out

def plausible_ref(s:str)->bool:
    if not s or len(s)>500:return False
    if any(ch in s for ch in "{}[]<>"):return False
    if s.count(" ")>8:return False
    low=s.lower()
    return any(low.split("?",1)[0].endswith("."+e) for e in ("swf","xml","mp3","wav","flv","png","jpg","jpeg","gif","json","js","css","txt","dat","bin"))

def resolve_refs(base_url:str,raw:bytes):
    data=swf_uncompress(raw)
    refs=set()
    for m in abs_rx.finditer(data):
        try:
            s=m.group().decode("latin1","ignore").strip()
            if plausible_ref(s):refs.add(s)
        except:pass
    for m in file_rx.finditer(data):
        try:
            s=m.group().decode("latin1","ignore").strip()
        except:continue
        if not plausible_ref(s):continue
        if s.lower().startswith(("http://","https://")):
            refs.add(s); continue
        if s.startswith("/"):
            # Root-relative Classic resources historically live on play; keep an assets-host variant too.
            refs.add(urljoin(PLAY,s))
            refs.add(urljoin("https://assets.webkinz.com/",s))
        else:
            refs.add(urljoin(base_url,s))
    return {u.split("#",1)[0] for u in refs if urlsplit(u).hostname and urlsplit(u).hostname.endswith("webkinz.com")}

root_bodies=asyncio.run(get_batch(roots))
edges=set()
discovered=set()
compression=Counter()
for url,kind,iid,status,ct,raw,final in root_bodies:
    if not raw:continue
    compression[raw[:3].decode("latin1","ignore")]+=1
    for child in resolve_refs(url,raw):
        edges.add((url,child)); discovered.add(child)

all_success=set(r[0] for r in roots)
seen=set(all_success)
rounds=[]
for rnd in range(1,4):
    pending=sorted(discovered-seen)
    if not pending:
        rounds.append({"round":rnd,"attempted":0,"valid":0,"new_refs":0})
        break
    hrows=[(u,"child",0) for u in pending]
    h=asyncio.run(head_batch(hrows,24))
    valid=[]
    for r in h:
        ext=Path(urlsplit(r[0]).path).suffix.lower()
        ct=r[4]
        ok=r[3] in (200,206)
        if ext==".swf":ok=ok and ct in ("application/x-shockwave-flash","application/octet-stream")
        elif ext==".png":ok=ok and ct=="image/png"
        elif ext in (".jpg",".jpeg"):ok=ok and ct=="image/jpeg"
        elif ext in (".xml",".json",".js",".css",".txt"):ok=ok and ct!="text/html"
        if ok:valid.append(r)
        seen.add(r[0])
    newrefs=0
    all_success.update(r[0] for r in valid)
    recursive=[r for r in valid if Path(urlsplit(r[0]).path).suffix.lower() in (".swf",".xml",".json",".js",".css") and r[5] <= 6_500_000]
    bodies=asyncio.run(get_batch(recursive,12)) if recursive else []
    for url,kind,iid,status,ct,raw,final in bodies:
        if not raw:continue
        for child in resolve_refs(url,raw):
            if child not in discovered:newrefs+=1
            discovered.add(child); edges.add((url,child))
    rounds.append({"round":rnd,"attempted":len(pending),"valid":len(valid),"new_refs":newrefs})

(OUT/"special-child-candidates.txt").write_text("\n".join(sorted(discovered))+"\n")
(OUT/"special-child-valid-urls.txt").write_text("\n".join(sorted(all_success-set(r[0] for r in roots)))+"\n")
(OUT/"special-all-valid-urls.txt").write_text("\n".join(sorted(all_success))+"\n")
(OUT/"special-dependency-edges.tsv").write_text("\n".join(f"{a}\t{b}" for a,b in sorted(edges))+"\n")
summary={
    "version":"v390_249",
    "item_records":len(ids),
    "root_item_swfs":sum(1 for r in roots if r[1]=="item_swf"),
    "root_character_swfs":sum(1 for r in roots if r[1]=="character_swf"),
    "root_swf_total_bytes":sum(r[5] for r in roots),
    "compression_signatures":dict(compression),
    "child_candidates":len(discovered),
    "dependency_edges":len(edges),
    "all_valid_urls_including_roots":len(all_success),
    "valid_child_urls":len(all_success-set(r[0] for r in roots)),
    "rounds":rounds,
}
(OUT/"special-summary.json").write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
