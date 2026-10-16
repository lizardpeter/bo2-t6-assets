from __future__ import annotations
import asyncio, aiohttp, csv, json, re
from pathlib import Path
from urllib.parse import urlsplit
from collections import Counter, defaultdict

ROOT = "https://assets.webkinz.com/swf/item/"
ROOM_TYPES = {2,3,6,7,26,30,8,23,29,19}
DIR = {1:"sw",2:"nw",3:"ne",4:"se"}

src_candidates = list(Path("work/items-source").rglob("DoAction.as"))
if not src_candidates:
    raise SystemExit("items DoAction.as not found")
src = max(src_candidates, key=lambda p:p.stat().st_size)
text = src.read_text(errors="ignore")

items=[]
for m in re.finditer(r'itemObject\.ITM(\d+)\s*=\s*\{([^}]*)\};', text):
    d=dict(re.findall(r'(\w+):"([^"]*)"', m.group(2)))
    try:
        iid=int(m.group(1)); typ=int(d.get("itemType_DbId","-1")); views=int(d.get("views","0"))
    except ValueError:
        continue
    if typ in ROOM_TYPES:
        items.append({"id":iid,"type":typ,"views":views,"name":d.get("name",""),"export":d.get("export",""),"status":d.get("status","")})

def filenames(item):
    typ=item["type"]; views=item["views"]
    if typ == 7:
        return [f"{s}.{ext}" for s in ("large","medium","small") for ext in ("png","xml")]
    if typ == 6:
        dirs=("sw","se")
    elif views == 4:
        dirs=("sw","nw","ne","se")
    elif views <= 1:
        dirs=("sw",)
    else:
        dirs=("sw","se")
    return [f"{d}.{ext}" for d in dirs for ext in ("png","xml")]

candidates=[]
for item in items:
    for fn in filenames(item):
        candidates.append((f'{ROOT}{item["id"]}/{fn}', item["id"], item["type"], item["views"], fn, item["name"]))

# Also test the three generic item formulas defined by PathSettings for room items.
generic=[]
for item in items:
    for fn in ("icon.png","item.swf","character.swf"):
        generic.append((f'{ROOT}{item["id"]}/{fn}', item["id"], item["type"], item["views"], fn, item["name"]))

Path("out").mkdir(exist_ok=True)
with open("out/room-items.tsv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f,delimiter="\t")
    w.writerow(["id","type","views","name","export","status"])
    for x in items: w.writerow([x["id"],x["type"],x["views"],x["name"],x["export"],x["status"]])

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
timeout=aiohttp.ClientTimeout(total=12,connect=6,sock_read=7)

async def probe_one(session, row, sem):
    url,iid,typ,views,fn,name=row
    async with sem:
        try:
            async with session.head(url,allow_redirects=True,timeout=timeout) as r:
                status=r.status
                ctype=(r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                clen=r.headers.get("Content-Length") or ""
                final=str(r.url)
            # nginx/assets host supports HEAD, but keep a fallback if needed.
            if status in (403,405,501):
                async with session.get(url,headers={"Range":"bytes=0-0"},allow_redirects=True,timeout=timeout) as r:
                    await r.content.read(1)
                    status=r.status
                    ctype=(r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                    clen=r.headers.get("Content-Length") or ""
                    final=str(r.url)
            valid = status in (200,206) and (
                (fn.endswith(".png") and ctype=="image/png") or
                (fn.endswith(".xml") and ctype in ("text/xml","application/xml","text/plain","application/octet-stream")) or
                (fn.endswith(".swf") and ctype in ("application/x-shockwave-flash","application/octet-stream"))
            )
            return (url,iid,typ,views,fn,name,status,ctype,clen,final,valid)
        except Exception as e:
            return (url,iid,typ,views,fn,name,0,type(e).__name__,"",url,False)

async def probe_all(rows, limit=18):
    conn=aiohttp.TCPConnector(limit=limit,limit_per_host=limit,ttl_dns_cache=300,enable_cleanup_closed=True)
    sem=asyncio.Semaphore(limit)
    out=[]
    async with aiohttp.ClientSession(headers={"User-Agent":UA},connector=conn) as s:
        tasks=[asyncio.create_task(probe_one(s,row,sem)) for row in rows]
        n=0
        for fut in asyncio.as_completed(tasks):
            out.append(await fut); n+=1
            if n%10000==0: print("probed",n,flush=True)
    return out

async def main():
    # Renderer-requested files first.
    render_rows=await probe_all(candidates,18)
    generic_rows=await probe_all(generic,18)
    return render_rows,generic_rows

render_rows,generic_rows=asyncio.run(main())

header=["url","item_id","type","views","filename","name","status","content_type","content_length","final_url","valid"]

def save_tsv(path, rows):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,delimiter="\t"); w.writerow(header); w.writerows(rows)

render_ok=[r for r in render_rows if r[-1]]
render_bad=[r for r in render_rows if not r[-1]]
generic_ok=[r for r in generic_rows if r[-1]]
generic_bad=[r for r in generic_rows if not r[-1]]
save_tsv("out/render-success.tsv",render_ok)
save_tsv("out/render-failures.tsv",render_bad)
save_tsv("out/generic-success.tsv",generic_ok)
save_tsv("out/generic-failures.tsv",generic_bad)
Path("out/render-success-urls.txt").write_text("\n".join(sorted(r[0] for r in render_ok))+"\n")
Path("out/generic-success-urls.txt").write_text("\n".join(sorted(r[0] for r in generic_ok))+"\n")

# Coverage per item.
expected=defaultdict(int); found=defaultdict(int)
for r in render_rows: expected[r[1]]+=1
for r in render_ok: found[r[1]]+=1
full=[iid for iid,n in expected.items() if found[iid]==n]
partial=[iid for iid,n in expected.items() if 0<found[iid]<n]
zero=[iid for iid,n in expected.items() if found[iid]==0]
Path("out/items-full-render-coverage.txt").write_text("\n".join(map(str,sorted(full)))+"\n")
Path("out/items-partial-render-coverage.txt").write_text("\n".join(map(str,sorted(partial)))+"\n")
Path("out/items-zero-render-coverage.txt").write_text("\n".join(map(str,sorted(zero)))+"\n")

summary={
  "version":"v390_249",
  "room_item_records":len(items),
  "renderer_candidates":len(render_rows),
  "renderer_valid":len(render_ok),
  "renderer_invalid_or_missing":len(render_bad),
  "generic_candidates":len(generic_rows),
  "generic_valid":len(generic_ok),
  "generic_invalid_or_missing":len(generic_bad),
  "items_full_renderer_coverage":len(full),
  "items_partial_renderer_coverage":len(partial),
  "items_zero_renderer_coverage":len(zero),
  "valid_render_by_type":dict(Counter(str(r[2]) for r in render_ok)),
  "valid_render_by_filename":dict(Counter(r[4] for r in render_ok)),
  "valid_generic_by_filename":dict(Counter(r[4] for r in generic_ok)),
  "status_render":dict(Counter(str(r[6]) for r in render_rows)),
  "status_generic":dict(Counter(str(r[6]) for r in generic_rows)),
}
Path("out/summary.json").write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
