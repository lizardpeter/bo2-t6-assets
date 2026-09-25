import json
import urllib.request
from pathlib import Path

OUT = Path("bootstrap_raw")
OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
URLS = {
    "main2.swf": "https://play.webkinz.com/SWF/main2.swf?v=v390_249",
    "Webkinz.swf": "https://play.webkinz.com/Webkinz.swf?v=v390_249",
}
rows = []
for name, url in URLS.items():
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        (OUT/name).write_bytes(body)
        rows.append({
            "name": name,
            "url": url,
            "status": getattr(r, "status", 200),
            "content_type": r.headers.get("Content-Type", ""),
            "bytes": len(body),
            "signature": body[:3].decode("latin1", "ignore"),
        })
(OUT/"fetch.json").write_text(json.dumps(rows, indent=2))
print(json.dumps(rows, indent=2))
