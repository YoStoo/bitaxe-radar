"""IndexNow pings (Bing, Yandex, Seznam, Naver... share submissions via api.indexnow.org).

  python3 scripts/indexnow.py all                      # submit every URL in the live sitemap
  python3 scripts/indexnow.py diff OLD.xml NEW.xml     # print new / content-changed URLs, space-separated
  python3 scripts/indexnow.py submit URL [URL ...]     # submit these URLs

"Changed" means a new URL, or a page whose lastmod is a plain date (hand-written content) that moved.
Pages stamped with the 6-hourly data timestamp are skipped by diff, so routine price runs don't re-ping everything.
The key file is site/<key>.txt (public by design, it proves we own the host).
"""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HOST = "bitaxeradar.com"
SITE = Path(__file__).resolve().parent.parent / "site"
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def key():
    ks = [p.stem for p in SITE.glob("*.txt") if len(p.stem) == 32 and p.read_text().strip() == p.stem]
    assert len(ks) == 1, f"expected one IndexNow key file in site/, found {ks}"
    return ks[0]


def entries(xml_text):
    return {u.find(NS + "loc").text: (u.findtext(NS + "lastmod") or "") for u in ET.fromstring(xml_text).iter(NS + "url")}


def diff(old, new):
    return [u for u, lm in new.items() if u not in old or ("T" not in lm and old[u] != lm)]


def submit(urls):
    urls = [u for u in urls if u.startswith(f"https://{HOST}/")][:10000]
    if not urls:
        print("indexnow: nothing to submit"); return 0
    k = key()
    body = json.dumps({"host": HOST, "key": k, "keyLocation": f"https://{HOST}/{k}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "bitaxe-radar-indexnow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    print(f"indexnow: submitted {len(urls)} URLs -> HTTP {status}")
    return status


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "all":
        with urllib.request.urlopen(f"https://{HOST}/sitemap.xml", timeout=30) as r:
            st = submit(list(entries(r.read()).keys()))
    elif cmd == "diff":
        old = Path(sys.argv[2])
        print(" ".join(diff(entries(old.read_bytes()) if old.exists() and old.stat().st_size else {}, entries(Path(sys.argv[3]).read_bytes())))
               if old.exists() and old.stat().st_size else "")   # no old sitemap -> don't flood
        st = 200
    else:
        st = submit(sys.argv[2:])
    sys.exit(0 if st in (200, 202) else 1)
