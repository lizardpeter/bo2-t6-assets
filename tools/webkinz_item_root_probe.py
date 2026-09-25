import json
import urllib.error
import urllib.request
from pathlib import Path

ROOTS = [
    "https://assets.webkinz.com/swf/item/",
]
# Known current room-rendered descriptors from v390_249 items.swf.
IDS = {
    181: "Comfy Plush Chair",
    187: "Country Bed",
    178: "Wagon Wheel Table",
    184: "Jungle Wallpaper",
    160: "Blue Flooring",
    201: "Pineapple Lamp",
    297: "Stove",
    511: "Football Fridge",
    8: "Modern Television",
}
FILES = [
    "sw.png","sw.xml","nw.png","nw.xml","ne.png","ne.xml","se.png","se.xml",
    "icon.png","item.swf","character.swf",
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

def probe(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-255"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(256)
            ct=(r.headers.get("Content-Type","") or "").split(";")[0].strip().lower()
            return {
                "url": url,
                "status": getattr(r, "status", 200),
                "content_type": ct,
                "content_length": r.headers.get("Content-Length", ""),
                "first_bytes_hex": body[:16].hex(),
                "png_signature": body.startswith(b"\x89PNG\r\n\x1a\n"),
                "swf_signature": body[:3] in (b"FWS",b"CWS",b"ZWS"),
                "xml_like": ct in ("application/xml","text/xml") or body.lstrip().startswith(b"<?xml") or body.lstrip().startswith(b"<TextureAtlas"),
                "final_url": r.geturl(),
            }
    except urllib.error.HTTPError as e:
        body = e.read(256) if hasattr(e, "read") else b""
        ct=(e.headers.get("Content-Type","") if e.headers else "").split(";")[0].strip().lower()
        return {
            "url": url, "status": e.code, "content_type": ct,
            "content_length": e.headers.get("Content-Length","") if e.headers else "",
            "first_bytes_hex": body[:16].hex(),
            "png_signature": body.startswith(b"\x89PNG\r\n\x1a\n"),
            "swf_signature": body[:3] in (b"FWS",b"CWS",b"ZWS"),
            "xml_like": ct in ("application/xml","text/xml") or body.lstrip().startswith(b"<?xml") or body.lstrip().startswith(b"<TextureAtlas"),
            "final_url": url,
        }
    except Exception as e:
        return {"url":url,"status":0,"error":f"{type(e).__name__}:{e}"}

def main():
    out=Path("out"); out.mkdir(exist_ok=True)
    rows=[]
    for root in ROOTS:
        for iid,name in IDS.items():
            for fn in FILES:
                r=probe(f"{root}{iid}/{fn}")
                r["descriptor_id"]=iid
                r["item_name"]=name
                r["file"]=fn
                rows.append(r)
    valid=[r for r in rows if r.get("png_signature") or r.get("swf_signature") or r.get("xml_like")]
    summary={}
    for iid,name in IDS.items():
        s=[r for r in rows if r["descriptor_id"]==iid]
        v=[r for r in valid if r["descriptor_id"]==iid]
        summary[str(iid)]={"name":name,"valid_count":len(v),"valid_files":[r["file"] for r in v],"statuses":{str(x):sum(1 for r in s if r.get("status")==x) for x in sorted({r.get("status") for r in s})}}
    (out/"probe.json").write_text(json.dumps(rows,indent=2))
    (out/"valid.json").write_text(json.dumps(valid,indent=2))
    (out/"summary.json").write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
