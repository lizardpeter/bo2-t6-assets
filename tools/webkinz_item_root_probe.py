import json
import urllib.error
import urllib.request
from pathlib import Path

ROOTS = [
    "https://assets.webkinz.com/swf/items/",
    "https://assets.webkinz.com/SWF/ITEMS/",
    "https://play.webkinz.com/swf/items/",
    "https://play.webkinz.com/SWF/ITEMS/",
]
IDS = [331, 590, 14280, 22241, 29889]
FILES = ["sw.png", "sw.xml", "nw.png", "nw.xml", "ne.png", "ne.xml", "se.png", "se.xml"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"


def probe(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-255"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(256)
            return {
                "url": url,
                "status": getattr(r, "status", 200),
                "content_type": r.headers.get("Content-Type", ""),
                "content_length": r.headers.get("Content-Length", ""),
                "first_bytes_hex": body[:16].hex(),
                "png_signature": body.startswith(b"\x89PNG\r\n\x1a\n"),
                "xml_prefix": body.lstrip().startswith(b"<"),
                "final_url": r.geturl(),
            }
    except urllib.error.HTTPError as e:
        body = e.read(256) if hasattr(e, "read") else b""
        return {
            "url": url,
            "status": e.code,
            "content_type": e.headers.get("Content-Type", "") if e.headers else "",
            "content_length": e.headers.get("Content-Length", "") if e.headers else "",
            "first_bytes_hex": body[:16].hex(),
            "png_signature": body.startswith(b"\x89PNG\r\n\x1a\n"),
            "xml_prefix": body.lstrip().startswith(b"<"),
            "final_url": url,
        }
    except Exception as e:
        return {"url": url, "status": 0, "error": f"{type(e).__name__}:{e}"}


def main() -> None:
    out = Path("out")
    out.mkdir(exist_ok=True)
    rows = [probe(f"{root}{iid}/{name}") for root in ROOTS for iid in IDS for name in FILES]
    valid = [r for r in rows if r.get("png_signature") or r.get("xml_prefix")]

    by_root = {}
    for root in ROOTS:
        subset = [r for r in rows if r["url"].startswith(root)]
        by_root[root] = {
            "total": len(subset),
            "png": sum(1 for r in subset if r.get("png_signature")),
            "xml": sum(1 for r in subset if r.get("xml_prefix")),
            "status200": sum(1 for r in subset if r.get("status") == 200),
            "types": sorted({r.get("content_type", "") for r in subset}),
        }

    (out / "probe.json").write_text(json.dumps(rows, indent=2))
    (out / "valid.json").write_text(json.dumps(valid, indent=2))
    (out / "summary.json").write_text(json.dumps(by_root, indent=2))
    print(json.dumps(by_root, indent=2))


if __name__ == "__main__":
    main()
