import json
import urllib.error
import urllib.request
from pathlib import Path

URLS = {
    "play_root.html": "https://play.webkinz.com/",
    "wconf.js.php": "https://play.webkinz.com/wconf.js.php",
    "hostControlServices.swf": "https://play.webkinz.com/SWF/hostControlServices.swf",
    "webkinzXML.swf": "https://play.webkinz.com/SWF/server/webkinzXML.swf?v=v390_249",
    "as3bridgeService.swf": "https://play.webkinz.com/SWF/server/as3bridgeService.swf?v=v390_249",
    "pet_config.swf": "https://play.webkinz.com/SWF/PETS/config.swf",
    "service.as": "https://play.webkinz.com/service.as",
    "server_packages_services.as": "https://play.webkinz.com/SWF/server/__Packages.com.webkinz.services.as",
    "main.js": "https://play.webkinz.com/main.f0803e1f17ed9e88d9ce.js",
    "runtime.js": "https://play.webkinz.com/runtime.4fd09af43b6bc8d95a03.js",
    "vendor.js": "https://play.webkinz.com/vendor.f9da5857a20f170f68a7.js",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"


def fetch(name: str, url: str, out: Path) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read()
            (out / name).write_bytes(body)
            return {
                "name": name,
                "url": url,
                "status": getattr(r, "status", 200),
                "content_type": r.headers.get("Content-Type", ""),
                "content_length": len(body),
                "final_url": r.geturl(),
                "prefix_hex": body[:16].hex(),
            }
    except urllib.error.HTTPError as e:
        body = e.read()
        (out / name).write_bytes(body)
        return {
            "name": name,
            "url": url,
            "status": e.code,
            "content_type": e.headers.get("Content-Type", "") if e.headers else "",
            "content_length": len(body),
            "final_url": url,
            "prefix_hex": body[:16].hex(),
        }
    except Exception as e:
        return {"name": name, "url": url, "status": 0, "error": f"{type(e).__name__}:{e}"}


def main() -> None:
    out = Path("registry_trace/input")
    out.mkdir(parents=True, exist_ok=True)
    rows = [fetch(name, url, out) for name, url in URLS.items()]
    Path("registry_trace/fetch.json").write_text(json.dumps(rows, indent=2))
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
