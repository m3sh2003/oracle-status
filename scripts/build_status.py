#!/usr/bin/env python3
"""
Static status page generator for oracle-status (Uptime Kuma edition).
Reads status-data.json (produced by Hermes from Uptime Kuma) and renders a
fully self-contained index.html (inline CSS, no JS fetch, no api.github.com).
Deploys index.html + data.json to gh-pages via the workflow.
"""
import json
import os
import datetime

REPO_ROOT = os.environ.get("GITHUB_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def log(msg):
    print(f"[{datetime.datetime.now().isoformat()}] {msg}", flush=True)


CSS = """
:root{--bg:#0f1419;--panel:#171d26;--panel2:#1d2530;--text:#e6edf3;--muted:#8b97a6;--accent:#0fb5ae;--up:#1faa59;--down:#e0413e;--pending:#e0a106;--border:#263041}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans Arabic',sans-serif;background:var(--bg);color:var(--text);line-height:1.5}
.container{max-width:960px;margin:0 auto;padding:24px 16px 60px}
header.top{display:flex;align-items:center;gap:12px;margin-bottom:6px}
header.top .logo{width:38px;height:38px;border-radius:9px;background:linear-gradient(135deg,#0fb5ae,#0a8f88);display:flex;align-items:center;justify-content:center;font-weight:800;color:#04110f;font-size:20px}
header.top h1{font-size:22px;margin:0}
.lead{color:var(--muted);margin:0 0 18px;font-size:14px}
.banner{border-radius:12px;padding:16px 18px;margin:18px 0;display:flex;align-items:center;gap:12px;font-weight:600;font-size:16px}
.banner.up{background:rgba(31,170,89,.12);border:1px solid rgba(31,170,89,.4);color:#7ee2a8}
.banner.degraded{background:rgba(224,161,6,.12);border:1px solid rgba(224,161,6,.4);color:#f0c869}
.banner.down{background:rgba(224,65,62,.12);border:1px solid rgba(224,65,62,.4);color:#f19390}
.banner .b-dot{width:12px;height:12px;border-radius:50%}
.server{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:0 0 20px}
.scard{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px 16px}
.scard .s-label{font-size:12px;color:var(--muted);display:flex;justify-content:space-between}
.scard .s-val{font-weight:800;font-size:18px;margin-top:2px}
.sbar{height:8px;background:var(--panel2);border-radius:6px;overflow:hidden;margin-top:8px}
.sbar-fill{height:100%;border-radius:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px}
.card.down{border-color:rgba(224,65,62,.5)}
.card.pending{border-color:rgba(224,161,6,.45)}
.card-head{display:flex;align-items:center;gap:8px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:0 0 auto}
.card-title{font-weight:700;font-size:15px}
.card-state{margin-left:auto;font-size:12px;font-weight:700;padding:2px 8px;border-radius:20px;background:var(--panel2);color:var(--muted)}
.card.down .card-state{color:#f19390;background:rgba(224,65,62,.15)}
.card.up .card-state{color:#7ee2a8;background:rgba(31,170,89,.15)}
.card.pending .card-state{color:#f0c869;background:rgba(224,161,6,.15)}
.card-desc{color:var(--muted);font-size:12.5px;margin:6px 0 12px}
.metrics{display:flex;gap:10px;margin-bottom:10px}
.metric{flex:1;background:var(--panel2);border-radius:8px;padding:8px 10px}
.m-label{display:block;font-size:11px;color:var(--muted)}
.m-val{display:block;font-weight:700;font-size:14px;margin-top:2px}
.uptime-row{display:flex;gap:10px}
.up-col{flex:1}
.up-label{font-size:11px;color:var(--muted);display:block;margin-bottom:3px}
.bar{height:7px;background:var(--panel2);border-radius:6px;overflow:hidden}
.bar-fill{height:100%;border-radius:6px}
.pct{font-size:11px;color:var(--muted);margin-left:4px}
.card-url{margin-top:10px;font-size:11px;word-break:break-all}
.card-url a{color:var(--accent);text-decoration:none}
.meta{color:var(--muted);font-size:12px;margin:4px 0 20px}
footer{margin-top:30px;color:var(--muted);font-size:12px;text-align:center}
footer a{color:var(--accent);text-decoration:none}
@media (prefers-color-scheme: light){:root{--bg:#f5f7fa;--panel:#fff;--panel2:#eef1f5;--text:#1a2230;--muted:#5b6675;--border:#e2e8f0}}
"""

HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
<style>{CSS}</style>
<script>if('serviceWorker' in navigator){navigator.serviceWorker.getRegistrations().then(function(r){r.forEach(function(x){x.unregister();});}).catch(function(){});}</script>
</head>
<body>
<div class="container">
  <header class="top">
    <div class="logo">&#9672;</div>
    <h1>{TITLE}</h1>
  </header>
  <p class="lead">{INTRO}</p>
  <div class="banner {BANNER_CLASS}">
    <span class="b-dot" style="background:{BANNER_COLOR}"></span>{BANNER_TEXT}
  </div>
  <p class="meta">آخر فحص: {UPDATED} &middot; يُحدّث تلقائياً كل {INTERVAL} دقائق من سيرفرات GitHub المستقلة (البيانات من Uptime Kuma على مضيف Oracle)</p>
{SERVER}
  <div class="grid">{CARDS}</div>
  <footer>
    <p>مراقبة مستقلة لمنظومة Oracle AI Stack &mdash; البيانات تُحفظ على GitHub Pages (بدون الاعتماد على GitHub API وقت التشغيل).</p>
    <p>مفتوح المصدر على <a href="https://github.com/m3sh2003/oracle-status">GitHub</a> &middot; مشغّل بواسطة <a href="http://145.241.107.81:3002" target="_blank" rel="noopener">Uptime Kuma</a>.</p>
  </footer>
</div>
</body>
</html>"""


def server_block(server):
    if not server:
        return ""
    def bar(label, val):
        v = float(val or 0)
        color = "#1faa59" if v < 70 else ("#e0a106" if v < 85 else "#e0413e")
        return f'''<div class="scard">
      <div class="s-label"><span>{label}</span><span>{v:.1f}%</span></div>
      <div class="s-val">{v:.1f}%</div>
      <div class="sbar"><div class="sbar-fill" style="width:{v:.1f}%;background:{color}"></div></div>
    </div>'''
    return '<div class="server">' + bar("المعالج (CPU)", server.get("cpu")) + \
        bar("الذاكرة (RAM)", server.get("ram")) + \
        bar("القرص (Disk)", server.get("disk")) + '</div>'


def uptime_bar(pct):
    if pct is None:
        return '<span class="pct">&mdash;</span>'
    color = "#1faa59" if pct >= 99 else ("#e0a106" if pct >= 95 else "#e0413e")
    return f'<div class="bar"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div><span class="pct">{pct:.1f}%</span>'


def build_card(m):
    status = m.get("status", "pending")
    up = (status == "up")
    state = "up" if up else ("down" if status == "down" else "pending")
    label = {"up": "يعمل", "down": "متوقف", "pending": "بانتظار"}.get(status, "?")
    dot_color = {"up": "#1faa59", "down": "#e0413e", "pending": "#e0a106"}.get(status, "#8b97a6")
    ping = m.get("ping")
    rt_txt = f"{ping} ms" if ping is not None else "—"
    code = m.get("code") or ""
    target = m.get("target") or ""
    up24 = m.get("uptime_24h")
    last = m.get("last_check") or ""
    return f'''
    <div class="card {state}">
      <div class="card-head">
        <span class="dot" style="background:{dot_color}"></span>
        <div class="card-title">{m.get('name','')}</div>
        <div class="card-state">{label}</div>
      </div>
      <div class="card-desc">{m.get('description','')}</div>
      <div class="metrics">
        <div class="metric"><span class="m-label">الحالة</span><span class="m-val">{code}</span></div>
        <div class="metric"><span class="m-label">زمن الاستجابة</span><span class="m-val">{rt_txt}</span></div>
      </div>
      <div class="uptime-row">
        <div class="up-col"><span class="up-label">٢٤س</span>{uptime_bar(up24)}</div>
      </div>
      <div class="card-url"><span style="color:var(--muted)">آخر فحص: {last}</span></div>
      {('<div class="card-url"><a href="'+target+'" target="_blank" rel="noopener">'+target+'</a></div>' if target else '')}
    </div>'''


def banner_for(monitors):
    total = len(monitors)
    n_up = sum(1 for m in monitors if m.get("status") == "up")
    if total == 0:
        return "down", "#e0413e", "لا توجد بيانات بعد — في انتظار أول فحص من Uptime Kuma"
    if n_up == total:
        return "up", "#1faa59", f"جميع الأنظمة تعمل بكفاءة ✓ ({n_up}/{total})"
    if n_up == 0:
        return "down", "#e0413e", "انقطاع كبير — جميع الخدمات متوقفة"
    return "degraded", "#e0a106", f"اضطراب جزئي — {n_up} من {total} خدمات تعمل"


def main():
    p = os.path.join(REPO_ROOT, "status-data.json")
    if os.path.exists(p):
        try:
            with open(p) as f:
                snapshot = json.load(f)
        except Exception:
            snapshot = {"generated_at": None, "server": {}, "monitors": []}
    else:
        snapshot = {"generated_at": None, "server": {}, "monitors": []}

    monitors = snapshot.get("monitors", [])
    server = snapshot.get("server", {})
    bclass, bcolor, btext = banner_for(monitors)
    cards = "".join(build_card(m) for m in monitors)

    updated = snapshot.get("generated_at") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = (HTML
            .replace("{TITLE}", "Oracle Mesh Status")
            .replace("{INTRO}", "مراقبة مستقلة لمنظومة Oracle AI Stack — تُحدّث من Uptime Kuma كل 5 دقائق.")
            .replace("{CSS}", CSS)
            .replace("{BANNER_CLASS}", bclass)
            .replace("{BANNER_COLOR}", bcolor)
            .replace("{BANNER_TEXT}", btext)
            .replace("{UPDATED}", updated)
            .replace("{INTERVAL}", "5")
            .replace("{SERVER}", server_block(server))
            .replace("{CARDS}", cards))

    with open(os.path.join(REPO_ROOT, "index.html"), "w") as f:
        f.write(html)
    with open(os.path.join(REPO_ROOT, "data.json"), "w") as f:
        json.dump(snapshot, f, ensure_ascii=False)

    log(f"Built index.html ({len(html)} bytes). Overall: {bclass} ({sum(1 for m in monitors if m.get('status')=='up')}/{len(monitors)})")


if __name__ == "__main__":
    main()
