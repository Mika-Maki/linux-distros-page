#!/usr/bin/env python3
"""逐个攻坚：403 用完整浏览器头重试，SSL 失败换 http，200 但无 icon 的深挖页面"""
import json, os, re, sys
from urllib.parse import urljoin
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "assets", "logos")

BROWSER = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "no-cache",
}

def fetch(url, timeout=10, headers=None, verify=True):
    try:
        r = requests.get(url, headers=headers or BROWSER, timeout=timeout, allow_redirects=True, verify=verify)
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"    fetch fail {url}: {type(e).__name__} {str(e)[:60]}")
        return None

def good(r):
    if not r or len(r.content) < 100:
        return False
    ct = r.headers.get("Content-Type", "")
    if "svg" in ct or b"<svg" in r.content[:500].lower():
        return True
    if r.content[:4] == b"\x89PNG" or r.content[:2] == b"\xff\xd8" or r.content[:4] == b"GIF8":
        return True
    if "icon" in ct or r.content[:4] == b"\x00\x00\x01\x00":
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

def save(did, r, src):
    content, ext = r.content, ext_of(r)
    if ext == "bin":
        return False
    path = f"{did}.{ext}"
    with open(os.path.join(OUT, path), "wb") as f:
        f.write(content)
    print(f"OK   {did}: {src} -> {path}")
    return True

def crawl(did, url):
    # 1) 浏览器头重试首页
    page = fetch(url)
    if page:
        # 尝试页面里的所有 img/link 引用（深挖）
        html = page.text
        hrefs = []
        for m in re.finditer(r'(?:href|src)=["\']([^"\']+)["\']', html):
            u = urljoin(url, m.group(1))
            if any(k in u.lower() for k in ("logo", "icon", "favicon")):
                hrefs.append(u)
        # 再去重尝试
        for u in hrefs:
            r = fetch(u)
            if r and good(r) and save(did, r, u):
                return
    # 2) 常见路径
    for p in ["/favicon.ico", "/favicon.png", "/logo.png", "/logo.svg", "/images/logo.png", "/img/logo.png", "/assets/img/logo.png", "/static/img/logo.png"]:
        r = fetch(urljoin(url, p))
        if r and good(r) and save(did, r, urljoin(url, p)):
            return
    # 3) http 降级（SSL 失败的）
    if url.startswith("https://"):
        r = fetch(url.replace("https://", "http://"), timeout=8)
        if r:
            for p in ["/favicon.ico", "/logo.png", "/logo.svg"]:
                r2 = fetch(urljoin(r.url, p))
                if r2 and good(r2) and save(did, r2, urljoin(r.url, p)):
                    return
    print(f"FAIL {did}: {url}")

TARGETS = {
    "sparkylinux": "https://sparkylinux.org",
    "slackel": "https://www.slackel.gr",
    "mx-linux": "https://mxlinux.org",
    "kubuntu": "https://kubuntu.org",
    "uos": "https://www.uniontech.com",
    "guix": "https://guix.gnu.org",
    "pclinuxos": "https://www.pclinuxos.com",
    "backbox": "https://www.backbox.org",
    "loongnix": "https://www.loongnix.cn",
    "caine": "https://www.caine-live.net",
    "bedrock-linux": "https://bedrocklinux.org",
    "funtoo": "https://www.funtoo.org",
    "clear-linux": "https://clearlinux.org",
}
for did, url in TARGETS.items():
    crawl(did, url)

results = {}
for f in os.listdir(OUT):
    results[f.split(".")[0]] = f
with open(os.path.join(BASE, "assets", "data", "logos.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print(f"\nlogos.json 更新完毕, 共 {len(results)} 个 logo")
