#!/usr/bin/env python3
"""从各发行版官网爬取 logo 资源到本地 assets/logos/"""
import json, os, re, sys, time, hashlib
from urllib.parse import urljoin, urlparse
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "assets", "data", "distros.json")
OUT = os.path.join(BASE, "assets", "logos")
os.makedirs(OUT, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,image/*,*/*;q=0.8",
}
TIMEOUT = 8
KNOWN_CANDIDATES = [
    "/favicon.ico", "/favicon.svg", "/logo.png", "/logo.svg",
    "/images/logo.png", "/assets/img/logo.png",
]

def fetch(url, timeout=TIMEOUT):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True, verify=True)
        if r.status_code == 200:
            return r
    except Exception as e:
        print(f"  fetch fail {url}: {e}")
    return None

def extract_icon_candidates(html, base_url):
    cands = []
    # <link rel="icon|apple-touch-icon" href="...">
    for m in re.finditer(r'<link[^>]+rel=["\']([^"\']*(?:icon|shortcut)[^"\']*)["\'][^>]*>', html, re.I):
        href = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        if href:
            cands.append(urljoin(base_url, href.group(1)))
    # og:image
    for m in re.finditer(r'<meta[^>]+property=["\']og:image["\'][^>]*>', html, re.I):
        content = re.search(r'content=["\']([^"\']+)["\']', m.group(0))
        if content:
            cands.append(urljoin(base_url, content.group(1)))
    return cands

def good_image(r):
    ct = r.headers.get("Content-Type", "")
    body = r.content
    if not body or len(body) < 100:
        return False
    if "svg" in ct or body[:5].lower() == b"<?xml" or b"<svg" in body[:500].lower():
        return True
    sigs = [(b"\x89PNG", "png"), (b"\xff\xd8", "jpg"), (b"GIF8", "gif"), (b"RIFF", "webp"), (b"II*\x00", "tiff")]
    for sig, _ in sigs:
        if body[:4] == sig or (sig == b"\xff\xd8" and body[:2] == sig):
            return True
    return False

def ext_of(r):
    ct = r.headers.get("Content-Type", "").lower()
    body = r.content
    if "svg" in ct or b"<svg" in body[:500].lower():
        return "svg"
    if "png" in ct or body[:4] == b"\x89PNG":
        return "png"
    if "jpeg" in ct or "jpg" in ct or body[:2] == b"\xff\xd8":
        return "jpg"
    if "gif" in ct:
        return "gif"
    if "webp" in ct or body[:4] == b"RIFF":
        return "webp"
    return "bin"

def try_download(url):
    """尝试下载图片，成功返回 (bytes, ext)，失败返回 None"""
    r = fetch(url)
    if r and good_image(r):
        return r.content, ext_of(r)
    return None

def download_for(distro):
    did = distro["id"]
    logo = distro.get("logo")
    url = distro["url"]
    result_path = None

    if logo and logo != "auto":
        r = try_download(logo)
        if r:
            content, ext = r
            result_path = f"{did}.{ext}"
            with open(os.path.join(OUT, result_path), "wb") as f:
                f.write(content)
            print(f"OK   {did}: {logo} -> {result_path}")
            return result_path
        print(f"WARN {did}: explicit logo failed: {logo}")

    # auto: 抓首页，解析 favicon / og:image，再兜底常见路径
    page = fetch(url)
    cands = []
    if page:
        cands = extract_icon_candidates(page.text, url)
    # 追加已知路径兜底（去重）
    seen = set()
    for c in cands:
        if c not in seen:
            seen.add(c)
    for c in KNOWN_CANDIDATES:
        u = urljoin(url, c)
        if u not in seen:
            seen.add(u)
    for c in seen:
        r = try_download(c)
        if r:
            content, ext = r
            result_path = f"{did}.{ext}"
            with open(os.path.join(OUT, result_path), "wb") as f:
                f.write(content)
            print(f"OK   {did}: {c} -> {result_path}")
            return result_path
    print(f"FAIL {did}: no logo found from {url}")
    return None

def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    distros = data["distros"]
    results = {}
    print(f"共 {len(distros)} 个发行版，开始爬取...\n")
    for d in distros:
        results[d["id"]] = download_for(d)
        time.sleep(0.15)  # 礼貌间隔
    ok = [k for k, v in results.items() if v]
    fail = [k for k, v in results.items() if not v]
    print(f"\n成功 {len(ok)} / 失败 {len(fail)}")
    if fail:
        print("失败列表:", ", ".join(fail))
    with open(os.path.join(BASE, "assets", "data", "logos.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
