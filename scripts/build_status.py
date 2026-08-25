#!/usr/bin/env python3
"""
Static status page generator for oracle-status.
- Pings each site via curl (no external API / no api.github.com needed)
- Appends a sample to history.json (committed to repo main)
- Renders a fully self-contained index.html with inline SVG charts (no JS fetch)
Deploys index.html + data.json to gh-pages via the workflow.
"""
import json
import subprocess
import time
import os
import datetime

REPO_ROOT = os.environ.get("GITHUB_WORKSPACE", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def log(msg):
    print(f"[{datetime.datetime.now().isoformat()}] {msg}", flush=True)


def load_sites():
    with open(os.path.join(REPO_ROOT, "sites.json")) as f:
        return json.load(f)


def measure(url, expected, timeout=12):
    try:
        proc = subprocess.run(
            ["curl", "-L", "-o", "/dev/null", "-s", "-m", str(timeout),
             "-w", "%{http_code} %{time_total}", url],
            capture_output=True, text=True, timeout=timeout + 8,
        )
        out = proc.stdout.strip()
        if " " in out:
            code_s, rt_s = out.split()
            code = int(code_s)
            rt = round(float(rt_s) * 1000)  # ms
        else:
            code, rt = 0, None
        return {"up": code in expected, "code": code, "rt": rt}
    except Exception as e:
        return {"up": False, "code": 0, "rt": None, "error": str(e)[:80]}


def load_history():
    p = os.path.join(REPO_ROOT, "history.json")
    if os.path.exists(p):
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            log("history.json corrupt, starting fresh")
    return {"updatedAt": None, "samples": []}


def save_history(h):
    with open(os.path.join(REPO_ROOT, "history.json"), "w") as f:
        json.dump(h, f)


def _dt(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def prune(samples, days=30):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return [s for s in samples if _dt(s["t"]) >= cutoff]


def window_stats(samples, site, hours):
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
    rel = [s for s in samples if _dt(s["t"]) >= cutoff and site in s["sites"]]
    if not rel:
        return {"uptime": None, "avg_rt": None, "count": 0}
    up = sum(1 for s in rel if s["sites"][site].get("up"))
    rts = [s["sites"][site]["rt"] for s in rel if s["sites"][site].get("rt") is not None]
    return {
        "uptime": round(100 * up / len(rel), 2),
        "avg_rt": round(sum(rts) / len(rts)) if rts else None,
        "count": len(rel),
    }


def sparkline(values, width=160, height=34):
    vals = [v for v in values if v is not None]
    if not vals:
        return ""
    mn, mx = min(vals), max(vals)
    if mx == mn:
        mx = mn + 1
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = round((i / max(n - 1, 1)) * width, 1)
        if v is None:
            y = height - 2
        else:
            y = round(height - 2 - ((v - mn) / (mx - mn)) * (height - 6), 1)
        pts.append(f"{x},{y}")
    return "M " + " L ".join(pts)


def uptime_bar(pct):
    color = "#1faa59" if (pct or 0) >= 99 else ("#e0a106" if (pct or 0) >= 95 else "#e0413e")
    return f'''
      <div class="bar"><div class="bar-fill" style="width:{pct or 0:.1f}%;background:{color}"></div></div>
      <span class="pct">{pct if pct is not None else "—"}%</span>'''


def svg_status_dot(up):
    c = "#1faa59" if up else "#e0413e"
    return f'<span class="dot" style="background:{c}"></span>'


def build_card(site, sample, samples):
    name = site["name"]
    cur = sample["sites"].get(name, {"up": False, "code": 0, "rt": None})
    up = cur.get("up")
    rt = cur.get("rt")
    # last N response times
    rts = [s["sites"][name].get("rt") if name in s["sites"] else None for s in samples[-60:]]
    spark = sparkline(rts)
    w24 = window_stats(samples, name, 24)
    w7 = window_stats(samples, name, 24 * 7)
    w30 = window_stats(samples, name, 24 * 30)
    state = "up" if up else "down"
    label = "يعمل" if up else "متوقف"
    rt_txt = f"{rt} ms" if rt is not None else "—"
    spark_svg = ""
    if spark:
        spark_svg = f'''
        <svg class="spark" viewBox="0 0 160 34" preserveAspectRatio="none" width="160" height="34">
          <path d="{spark}" fill="none" stroke="{('#1faa59' if up else '#e0413e')}" stroke-width="1.5"/>
        </svg>'''
    return f'''
    <div class="card {state}">
      <div class="card-head">
        {svg_status_dot(up)}
        <div class="card-title">{name}</div>
        <div class="card-state">{label}</div>
      </div>
      <div class="card-desc">{site.get('description','')}</div>
      <div class="metrics">
        <div class="metric"><span class="m-label">الحالة</span><span class="m-val">{cur.get('code')} {('OK' if up else 'FAIL')}</span></div>
        <div class="metric"><span class="m-label">زمن الاستجابة</span><span class="m-val">{rt_txt}</span></div>
      </div>
      {spark_svg}
      <div class="uptime-row">
        <div class="up-col"><span class="up-label">24س</span>{uptime_bar(w24['uptime'])}</div>
        <div class="up-col"><span class="up-label">7ي</span>{uptime_bar(w7['uptime'])}</div>
        <div class="up-col"><span class="up-label">30ي</span>{uptime_bar(w30['uptime'])}</div>
      </div>
      <div class="card-url"><a href="{site['url']}" target="_blank" rel="noopener">{site['url']}</a></div>
    </div>'''


CSS = """
:root{--bg:#0f1419;--panel:#171d26;--panel2:#1d2530;--text:#e6edf3;--muted:#8b97a6;--accent:#0fb5ae;--up:#1faa59;--down:#e0413e;--border:#263041}
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
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px}
.card.down{border-color:rgba(224,65,62,.5)}
.card-head{display:flex;align-items:center;gap:8px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:0 0 auto}
.card-title{font-weight:700;font-size:15px}
.card-state{margin-left:auto;font-size:12px;font-weight:700;padding:2px 8px;border-radius:20px;background:var(--panel2);color:var(--muted)}
.card.down .card-state{color:#f19390;background:rgba(224,65,62,.15)}
.card.up .card-state{color:#7ee2a8;background:rgba(31,170,89,.15)}
.card-desc{color:var(--muted);font-size:12.5px;margin:6px 0 12px}
.metrics{display:flex;gap:10px;margin-bottom:10px}
.metric{flex:1;background:var(--panel2);border-radius:8px;padding:8px 10px}
.m-label{display:block;font-size:11px;color:var(--muted)}
.m-val{display:block;font-weight:700;font-size:14px;margin-top:2px}
.spark{width:100%;height:34px;margin:4px 0 12px;display:block}
.uptime-row{display:flex;gap:10px}
.up-col{flex:1}
.up-label{font-size:11px;color:var(--muted);display:block;margin-bottom:3px}
.bar{height:7px;background:var(--panel2);border-radius:6px;overflow:hidden}
.bar-fill{height:100%;border-radius:6px}
.pct{font-size:11px;color:var(--muted);margin-left:4px}
.card-url{margin-top:10px;font-size:11px;word-break:break-all}
.card-url a{color:var(--accent);text-decoration:none}
footer{margin-top:30px;color:var(--muted);font-size:12px;text-align:center}
footer a{color:var(--accent);text-decoration:none}
.meta{color:var(--muted);font-size:12px;margin:4px 0 20px}
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
    <div class="logo">◈</div>
    <h1>{TITLE}</h1>
  </header>
  <p class="lead">{INTRO}</p>
  <div class="banner {BANNER_CLASS}">
    <span class="b-dot" style="background:{BANNER_COLOR}"></span>{BANNER_TEXT}
  </div>
  <p class="meta">آخر فحص: {UPDATED} · يُحدّث تلقائياً كل {INTERVAL} دقائق من سيرفرات GitHub المستقلة</p>
  <div class="grid">{CARDS}</div>
  <footer>
    <p>صفحة حالة مستقلة — البيانات تُحفظ محلياً على GitHub Pages (بدون الاعتماد على GitHub API).</p>
    <p>مفتوح المصدر على <a href="https://github.com/m3sh2003/oracle-status">GitHub</a>.</p>
  </footer>
</div>
</body>
</html>"""


def main():
    cfg = load_sites()
    sites = cfg["sites"]
    history = load_history()
    samples = history.get("samples", [])

    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()
    sample = {"t": now_iso, "sites": {}}
    for site in sites:
        r = measure(site["url"], site.get("expectedStatusCodes", [200]))
        sample["sites"][site["name"]] = r
        log(f"{site['name']}: up={r['up']} code={r['code']} rt={r['rt']}")

    samples.append(sample)
    samples = prune(samples, days=30)
    history = {"updatedAt": now_iso, "samples": samples}
    save_history(history)

    # overall status
    ups = [sample["sites"][site["name"]]["up"] for site in sites]
    n_up = sum(ups)
    if n_up == len(sites):
        bclass, bcolor, btext = "up", "#1faa59", "جميع الأنظمة تعمل بكفاءة ✓"
    elif n_up == 0:
        bclass, bcolor, btext = "down", "#e0413e", "انقطاع كبير — معظم الخدمات متوقفة"
    else:
        bclass, bcolor, btext = "degraded", "#e0a106", f"اضطراب جزئي — {n_up} من {len(sites)} خدمات تعمل"

    cards = "".join(build_card(site, sample, samples) for site in sites)

    html = HTML.format(
        TITLE=cfg.get("title", "Status"),
        INTRO=cfg.get("introMessage", ""),
        CSS=CSS,
        BANNER_CLASS=bclass,
        BANNER_COLOR=bcolor,
        BANNER_TEXT=btext,
        UPDATED=now.strftime("%Y-%m-%d %H:%M UTC"),
        INTERVAL=cfg.get("checkIntervalMinutes", 5),
        CARDS=cards,
    )

    with open(os.path.join(REPO_ROOT, "index.html"), "w") as f:
        f.write(html)

    data = {
        "updatedAt": now_iso,
        "overall": {"up": n_up, "total": len(sites), "state": bclass},
        "sites": {site["name"]: sample["sites"][site["name"]] for site in sites},
    }
    with open(os.path.join(REPO_ROOT, "data.json"), "w") as f:
        json.dump(data, f)

    # also keep latest 60 rt series for quick embeds
    log(f"Built index.html ({len(html)} bytes). Overall: {bclass} ({n_up}/{len(sites)})")


if __name__ == "__main__":
    main()
