#!/usr/bin/env python3
"""并行补爬缺失的 logo（线程池 8 并发）"""
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "assets", "data", "distros.json")
OUT = os.path.join(BASE, "assets", "logos")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
TIMEOUT = 10

with open(DATA, encoding="utf-8") as f:
    distros = json.load(f)["distros"]

have = {f.split(".")[0] for f in os.listdir(OUT)}
missing = [d for d in distros if d["id"] not in have]

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, verify=True)
        return r if r.status_code == 200 else None
    except Exception:
        return None

def good(r):
    if not r or len(r.content) < 100:
        return False
    ct = r.headers.get("Content-Type", "")
    if "svg" in ct or b"<svg" in r.content[:500].lower():
        return True
    if r.content[:4] == b"\x89PNG" or r.content[:2] == b"\xff\xd8" or r.content[:4] == b"GIF8":
        return True
    if "icon" in ct or r.content[:4] == b"\x00\x00\x01\x00":  # ICO
        return True
    return False

def ext_of(r):
    ct = r.headers.get("Content-Type", "").lower()
    if "svg" in ct or b"<svg" in r.content[:500].lower():
        return "svg"
    if "png" in ct or r.content[:4] == b"\x89PNG":
        return "png"
    if "jpeg" in ct or "jpg" in ct or r.content[:2] == b"\xff\xd8":
        return "jpg"
    if "gif" in ct:
        return "gif"
    if "icon" in ct or r.content[:4] == b"\x00\x00\x01\x00":
        return "ico"
    return "bin"

def icons_from_html(html, base):
    out = []
    for m in re.finditer(r'<link[^>]+rel=["\']([^"\']*(?:icon|shortcut)[^"\']*)["\'][^>]*>', html, re.I):
        href = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        if href:
            out.append(urljoin(base, href.group(1)))
    for m in re.finditer(r'<meta[^>]+property=["\']og:image["\'][^>]*>', html, re.I):
        c = re.search(r'content=["\']([^"\']+)["\']', m.group(0))
        if c:
            out.append(urljoin(base, c.group(1)))
    return out

def try_dl(url):
    r = fetch(url)
    return (r.content, ext_of(r)) if good(r) else None

def crawl(d):
    did = d["id"]
    logo = d.get("logo")
    cands = []
    if logo and logo != "auto":
        cands.append(logo)
    page = fetch(d["url"])
    if page:
        cands.extend(icons_from_html(page.text, d["url"]))
    for c in ["/favicon.ico", "/favicon.svg", "/logo.png", "/logo.svg", "/images/logo.png"]:
        cands.append(urljoin(d["url"], c))
    seen = set()
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        r = try_dl(c)
        if r:
            content, ext = r
            path = f"{did}.{ext}"
            with open(os.path.join(OUT, path), "wb") as f:
                f.write(content)
            return (did, True, c)
    return (did, False, d["url"])

ok, fail = [], []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(crawl, d): d["id"] for d in missing}
    for fut in as_completed(futs):
        did, success, src = fut.result()
        (ok if success else fail).append(did)
        print(f"{'OK  ' if success else 'FAIL'} {did} {src}", flush=True)

print(f"\n补爬完成: 成功 {len(ok)} / 失败 {len(fail)}")
if fail:
    print("失败:", ", ".join(fail))

# 更新 logos.json
results = {}
for f in os.listdir(OUT):
    results[f.split(".")[0]] = f
with open(os.path.join(BASE, "assets", "data", "logos.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print(f"logos.json 更新完毕, 共 {len(results)} 个 logo")
