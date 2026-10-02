# -*- coding: utf-8 -*-
"""
주비스 대시보드 만들기: jubis/dashboard.html 한 파일을 새로 쓴다.
  - 사이클이 끝날 때마다 jubis_cycle.py 가 부른다.
  - 손으로 돌릴 때: python autopilot\\make_dashboard.py  → jubis\\dashboard.html 더블클릭
읽는 곳: logs, jobs, reports, memory 폴더뿐. my_keys.py·토큰은 읽지도 쓰지도 않는다.
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path

JUBIS_DIR = Path(__file__).resolve().parent.parent
AUTO = JUBIS_DIR / "autopilot"
OUT = JUBIS_DIR / "dashboard.html"


def read(p, limit=6000):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def esc(s):
    return html.escape(s or "")


def newest(folder, pattern):
    files = sorted(Path(folder).glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def md_to_html(text):
    """아주 단순한 변환: 제목, 목록, 문단만. 모르는 건 그대로 글자로 보여 준다."""
    out, in_ul = [], False
    for line in text.splitlines():
        s = line.rstrip()
        if re.match(r"^\s*[-*] ", s):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append("<li>" + esc(re.sub(r"^\s*[-*] ", "", s)) + "</li>")
            continue
        if in_ul:
            out.append("</ul>")
            in_ul = False
        m = re.match(r"^(#{1,4})\s+(.*)", s)
        if m:
            lv = min(len(m.group(1)) + 2, 6)
            out.append(f"<h{lv}>{esc(m.group(2))}</h{lv}>")
        elif s.strip():
            out.append("<p>" + esc(s) + "</p>")
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def last_cycles():
    rows = []
    for f in newest(AUTO / "logs", "*.log")[:2]:
        for line in read(f, 200000).splitlines():
            rows.append(line)
    return rows[-14:]


def jobs_block():
    items = []
    for label, d in (("돌고 있음", AUTO / "jobs" / "running"), ("끝남", AUTO / "jobs" / "done")):
        for f in newest(d, "*.status.json")[:6]:
            try:
                i = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append((label, i.get("name", "?"), i.get("started", ""), i.get("ended", "")))
    for f in (AUTO / "jobs" / "done").glob("*.rejected.json") if (AUTO / "jobs" / "done").exists() else []:
        try:
            items.append(("거절됨", f.stem.replace(".rejected", ""), "", json.loads(f.read_text(encoding="utf-8")).get("rejected", "")))
        except Exception:
            pass
    return items


def experiments_block():
    rows = []
    for f in newest(JUBIS_DIR / "memory" / "experiments", "*.md"):
        if f.name.lower() == "readme.md":
            continue
        text = read(f, 20000)
        title = next((l.lstrip("# ").strip() for l in text.splitlines() if l.startswith("#")), f.stem)
        result = ""
        if "## 결과" in text:
            result = text.split("## 결과", 1)[1].strip().splitlines()
            result = " ".join(x.strip() for x in result[:3] if x.strip())[:240]
        rows.append((f.name, title, result or "아직 결과 없음", datetime.fromtimestamp(f.stat().st_mtime)))
    return rows


def page():
    now = datetime.now()
    stop = AUTO / "STOP"
    status = "멈춤" if stop.exists() else "작동 중"
    stop_msg = read(stop, 500) if stop.exists() else ""

    cycles = last_cycles()
    report_files = newest(JUBIS_DIR / "reports", "20*.md")
    report = md_to_html(read(report_files[0], 5000)) if report_files else "<p>아직 보고서가 없어요. 저녁 8시 이후 사이클에서 처음 만들어져요.</p>"
    report_name = report_files[0].name if report_files else ""
    diary_files = newest(JUBIS_DIR / "memory" / "diary", "20*.md")
    diary = md_to_html(read(diary_files[0], 5000)) if diary_files else "<p>아직 일기가 없어요.</p>"
    diary_name = diary_files[0].name if diary_files else ""
    now_md = md_to_html(read(JUBIS_DIR / "memory" / "now.md", 5000))

    exp_html = "".join(
        f"<tr><td>{esc(t)}</td><td>{esc(r)}</td><td>{d:%m-%d %H:%M}</td></tr>"
        for n, t, r, d in experiments_block()
    ) or "<tr><td colspan=3>아직 없어요</td></tr>"
    job_html = "".join(
        f"<tr><td>{esc(l)}</td><td>{esc(n)}</td><td>{esc(s)}</td><td>{esc(e)}</td></tr>" for l, n, s, e in jobs_block()
    ) or "<tr><td colspan=4>없어요</td></tr>"
    cycle_html = "<br>".join(esc(x) for x in cycles) or "아직 기록이 없어요"

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>주비스 대시보드</title>
<style>
:root{{--bg:#f6f5f2;--card:#fff;--ink:#1c1b19;--mute:#6b6a66;--line:#e4e2dc;--ok:#1f7a4d;--bad:#b3261e;--acc:#2f5fd0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--card:#1f1f1d;--ink:#eceae4;--mute:#9a988f;--line:#33322f;--ok:#58c58e;--bad:#f2867f;--acc:#8ab0ff}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,'Malgun Gothic',sans-serif}}
main{{max-width:960px;margin:0 auto;padding:20px 16px 60px}}
h1{{font-size:24px;margin:8px 0 4px}}.sub{{color:var(--mute);font-size:14px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin:16px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.card h2{{font-size:14px;color:var(--mute);margin:0 0 6px;font-weight:600}}
.big{{font-size:22px;font-weight:700}}.ok{{color:var(--ok)}}.bad{{color:var(--bad)}}
section{{margin-top:22px}}section>h2{{font-size:18px;margin:0 0 8px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:14px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:var(--mute);font-weight:600}}
.box{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 16px}}
.box p,.box li{{margin:6px 0}}.box h3,.box h4,.box h5{{margin:12px 0 4px}}
.log{{font:13px/1.6 ui-monospace,Consolas,monospace;color:var(--mute)}}
.scroll{{overflow-x:auto}}
</style></head><body><main>
<h1>주비스 대시보드</h1>
<div class="sub">이 화면은 사이클이 끝날 때마다 새로 만들어져요 · 만든 시각 {now:%Y-%m-%d %H:%M} · 5분마다 자동 새로고침</div>
<div class="grid">
<div class="card"><h2>주비스 상태</h2><div class="big {'bad' if stop.exists() else 'ok'}">{status}</div>{('<div class="sub">'+esc(stop_msg)+'</div>') if stop_msg else ''}</div>
<div class="card"><h2>실험 기록</h2><div class="big">{len(experiments_block())}개</div></div>
<div class="card"><h2>백그라운드 작업</h2><div class="big">{sum(1 for j in jobs_block() if j[0]=='돌고 있음')}개 실행 중</div></div>
</div>
<section><h2>최신 보고서 <span class="sub">{esc(report_name)}</span></h2><div class="box">{report}</div></section>
<section><h2>주비스가 다음에 할 일</h2><div class="box">{now_md}</div></section>
<section><h2>실험 목록</h2><div class="scroll"><table><tr><th>실험</th><th>결과 요약</th><th>수정 시각</th></tr>{exp_html}</table></div></section>
<section><h2>백그라운드 작업</h2><div class="scroll"><table><tr><th>상태</th><th>이름</th><th>시작</th><th>끝/사유</th></tr>{job_html}</table></div></section>
<section><h2>최근 일기 <span class="sub">{esc(diary_name)}</span></h2><div class="box">{diary}</div></section>
<section><h2>최근 사이클 기록</h2><div class="box log">{cycle_html}</div></section>
</main></body></html>"""


def main():
    OUT.write_text(page(), encoding="utf-8")
    print("대시보드 갱신:", OUT)


if __name__ == "__main__":
    main()
