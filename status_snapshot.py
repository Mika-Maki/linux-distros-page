#!/usr/bin/env python3
"""status 快照生成器：采集 pcstatus API → 生成静态 HTML（数据内嵌）→ push 到 GitHub Pages

用法:
  python3 status_snapshot.py            # 生成 + push 一次
  python3 status_snapshot.py --once     # 只生成不上传
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

API = "http://127.0.0.1:8093/api/status"
OUT_DIR = "/home/f9bdd3e6/linux-distros-page/status"
PROXY = "http://127.0.0.1:7890"


def fetch_status():
    req = urllib.request.Request(API, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def fmt_bytes(n):
    if n is None:
        return "–"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if n >= 10 else f"{n:.1f} {unit}"
        n /= 1024
    return "–"


def render(d):
    gpu = d.get("gpu", {})
    gpu_avail = gpu.get("available", False)
    idle = d.get("idle_secs", 0)
    active = d.get("user_active", False)
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(d.get("time", time.time())))

    def rows(list_, kind):
        if not list_:
            return '<tr><td colspan="3" style="color:var(--dim)">–</td></tr>'
        out = []
        for p in list_:
            if kind == "cpu":
                v = f"{p.get('pct', 0):.1f}%"
            elif kind == "gpu":
                v = fmt_bytes(p.get("rss", 0) * 1024 * 1024)
            else:
                v = fmt_bytes(p.get("rss", 0) * 1024)
            out.append(f'<tr><td class="name">{p.get("name","?")}</td><td class="pid">{p.get("pid","")}</td><td class="pct">{v}</td></tr>')
        return "".join(out)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-store">
<title>🖥️ 电脑状态 · 快照</title>
<style>
:root{{--bg:#0b0f14;--fg:#e6edf3;--card:#11161d;--border:#2a3646;--accent:#4fc3f7;--ok:#66bb6a;--warn:#ffb74d;--danger:#ef5350;--dim:#7d8ca0}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;min-height:100vh;padding:24px 16px 48px}}
.wrap{{max-width:960px;margin:0 auto}}
header{{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:20px}}
h1{{font-size:1.5rem;font-weight:700}}
h1 span{{color:var(--dim);font-size:.9rem;font-weight:400}}
.status-pill{{display:inline-flex;align-items:center;gap:8px;padding:5px 14px;border-radius:999px;font-size:.85rem;font-weight:600;border:1px solid var(--border)}}
.status-pill .dot{{width:9px;height:9px;border-radius:50%;background:var(--dim)}}
.status-pill.active{{color:var(--ok);border-color:rgba(102,187,106,.4)}}
.status-pill.active .dot{{background:var(--ok);box-shadow:0 0 8px var(--ok);animation:pulse 2s infinite}}
.status-pill.idle{{color:var(--dim)}}
@keyframes pulse{{50%{{opacity:.4}}}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:20px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px}}
.card h3{{font-size:.75rem;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;font-weight:600}}
.big{{font-size:2rem;font-weight:800;font-family:monospace}}
.big small{{font-size:.9rem;color:var(--dim);font-weight:400}}
.bar{{height:7px;background:#1f2937;border-radius:99px;margin-top:10px;overflow:hidden}}
.bar>div{{height:100%;border-radius:99px;transition:width .6s cubic-bezier(.165,.84,.44,1)}}
.meta{{display:flex;justify-content:space-between;font-size:.75rem;color:var(--dim);margin-top:6px;font-family:monospace}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px}}
@media(max-width:700px){{.grid2{{grid-template-columns:1fr}}}}
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--border)}}
th{{color:var(--dim);font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em}}
td.pct{{font-family:monospace;text-align:right}}
td.name{{font-family:monospace;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
td.pid{{color:var(--dim);font-family:monospace}}
.foot{{color:var(--dim);font-size:.75rem;text-align:center;margin-top:24px;font-family:monospace}}
.snapshot{{color:var(--accent);font-family:monospace;font-size:.8rem}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🖥️ 电脑状态 <span>@ {d.get('hostname','')}</span></h1>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <span class="status-pill {'active' if active else 'idle'}"><span class="dot"></span>{'🖱️ 正在使用中' if active else f'💤 已空闲 {int(idle)}s'}</span>
      <span class="snapshot">📸 快照 {ts}</span>
    </div>
  </header>
  <div class="cards">
    <div class="card"><h3>CPU</h3><div class="big">{d.get('cpu',0):.1f}<small>%</small></div><div class="bar"><div style="width:{min(d.get('cpu',0),100):.0f}%;background:{'var(--danger)' if d.get('cpu',0)>85 else 'var(--warn)' if d.get('cpu',0)>60 else 'var(--ok)'}"></div></div><div class="meta"><span>load: {', '.join(f'{x:.2f}' for x in d.get('loadavg',[0,0,0]))}</span><span>up {int(d.get('uptime',0)/3600)}h{int(d.get('uptime',0)%3600/60)}m</span></div></div>
    <div class="card"><h3>内存</h3><div class="big">{d.get('mem_pct',0):.1f}<small>%</small></div><div class="bar"><div style="width:{min(d.get('mem_pct',0),100):.0f}%;background:{'var(--danger)' if d.get('mem_pct',0)>85 else 'var(--warn)' if d.get('mem_pct',0)>60 else 'var(--ok)'}"></div></div><div class="meta"><span>{fmt_bytes(d.get('mem_used'))} / {fmt_bytes(d.get('mem_total'))}</span><span>swap: {fmt_bytes(d.get('swap_used'))}</span></div></div>
    <div class="card"><h3>GPU</h3><div class="big">{f'{gpu.get("util",0):.0f}' if gpu_avail else '–'}<small>%</small></div><div class="bar"><div style="width:{min(gpu.get('util',0),100):.0f}%;background:var(--accent)"></div></div><div class="meta"><span>{fmt_bytes(gpu.get('mem_used',0)*1024*1024) if gpu_avail else 'N/A'} / {fmt_bytes(gpu.get('mem_total',0)*1024*1024) if gpu_avail else ''}</span><span>{f'{gpu.get("temp",0):.0f}°C' if gpu_avail else ''} {gpu.get('model','') if gpu_avail else '无 NVIDIA GPU'}</span></div></div>
    <div class="card"><h3>磁盘 /</h3><div class="big">{d.get('disk_pct',0):.0f}<small>%</small></div><div class="bar"><div style="width:{min(d.get('disk_pct',0),100):.0f}%;background:{'var(--danger)' if d.get('disk_pct',0)>85 else 'var(--warn)' if d.get('disk_pct',0)>60 else 'var(--ok)'}"></div></div><div class="meta"><span>{fmt_bytes(d.get('disk_used'))} / {fmt_bytes(d.get('disk_total'))}</span><span>–</span></div></div>
  </div>
  <div class="grid2">
    <div class="card"><h3>🔥 CPU 占用 Top 3</h3><table><thead><tr><th>进程</th><th>PID</th><th style="text-align:right">CPU</th></tr></thead><tbody>{rows(d.get('top_cpu',[]),'cpu')}</tbody></table></div>
    <div class="card"><h3>💾 内存占用 Top 3</h3><table><thead><tr><th>进程</th><th>PID</th><th style="text-align:right">RSS</th></tr></thead><tbody>{rows(d.get('top_mem',[]),'mem')}</tbody></table></div>
    <div class="card" style="grid-column:1/-1"><h3>🎮 GPU 进程（显存）</h3><table><thead><tr><th>进程</th><th>PID</th><th style="text-align:right">显存</th></tr></thead><tbody>{rows(d.get('top_gpu',[]),'gpu') if d.get('top_gpu') else '<tr><td colspan="3" style="color:var(--dim)">无 GPU 负载</td></tr>'}</tbody></table></div>
  </div>
  <div class="foot">PCStatus 快照 · 由 {d.get('hostname','?')} 定时生成并推送 · GitHub Pages 静态托管</div>
</div>
</body>
</html>"""
    return html


def git_push():
    env = dict(os.environ)
    env["https_proxy"] = PROXY
    env["http_proxy"] = PROXY
    for args in (
        ["git", "add", "status/"],
        ["git", "-c", "user.name=Mika-Maki", "-c", "user.email=mika@users.noreply.github.com",
         "commit", "-m", f"status snapshot {time.strftime('%Y-%m-%d %H:%M:%S')}"],
        ["git", "-c", "http.proxy=" + PROXY, "push", "origin", "main"],
    ):
        r = subprocess.run(args, cwd="/home/f9bdd3e6/linux-distros-page", env=env,
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 and "nothing to commit" not in r.stderr:
            print(f"[git] {args[2] if len(args)>2 else args[0]}: {r.stderr.strip()[:120]}")
            return False
    return True


def main():
    only_gen = "--once" in sys.argv
    loop = "--loop" in sys.argv
    if loop:
        import signal
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        prev_sig = None  # 上次推送时的数据指纹
        while True:
            try:
                d = fetch_status()
            except Exception as e:
                print(f"[snapshot] 采集失败: {e}", flush=True)
                time.sleep(30)
                continue
            os.makedirs(OUT_DIR, exist_ok=True)
            with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
                f.write(render(d))
            print(f"[snapshot] 已生成 {time.strftime('%H:%M:%S')}", flush=True)
            # 数据指纹：仅内容相关字段（时间戳/idle 除外）
            # 低负载（<1%）的 top_cpu 进程名随机轮换，忽略它们避免无意义推送
            # mem_pct 取整、rss 取 MB 级，容忍正常波动
            sig = json.dumps({
                "cpu": round(d.get("cpu", 0)),
                "mem_pct": round(d.get("mem_pct", 0)),
                "disk_pct": round(d.get("disk_pct", 0)),
                "gpu_util": d.get("gpu", {}).get("util", 0),
                "top_cpu": [(p.get("name"), round(p.get("pct", 0), 1)) for p in d.get("top_cpu", []) if p.get("pct", 0) >= 1.0],
                "top_mem": [(p.get("name"), p.get("rss", 0) // 1024) for p in d.get("top_mem", [])],
            }, ensure_ascii=False)
            if sig != prev_sig:
                prev_sig = sig
                git_push()
            else:
                print("[snapshot] 数据无变化，跳过 push", flush=True)
            time.sleep(30)
        return 0
    try:
        d = fetch_status()
    except Exception as e:
        print(f"[snapshot] 采集失败: {e}")
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(d))
    print(f"[snapshot] 已生成 {time.strftime('%H:%M:%S')}")
    if only_gen:
        return 0
    return 0 if git_push() else 2


if __name__ == "__main__":
    sys.exit(main())
