# -*- coding: utf-8 -*-
"""
주비스 자율 사이클 (한 번 실행 = 한 번 생각하고 일하기)

윈도우 작업 스케줄러가 2시간마다 이 파일을 실행한다 (install_task.bat).
하는 일:
  1. STOP 파일이 있으면 아무것도 안 하고 끝 (긴급정지)
  2. 실전 봇 파일(엔진, my_keys, run_bot.bat)의 지문을 찍어 둔다
  3. Claude Code(claude -p)를 주비스 폴더에서 실행 → CYCLE_PROMPT.md 대로 스스로 일함
  4. 끝나면 실전 봇 파일 지문을 다시 확인. 바뀌었으면 원래대로 되돌리고 STOP + 텔레그램 경보
  5. 주비스가 남긴 telegram.txt가 있으면 승주에게 보냄
  6. 주비스 폴더를 git에 커밋 (기억의 기록)

비밀번호·키는 이 파일에 쓰지 않는다. 텔레그램은 환경변수 JUBIS_TG_TOKEN / JUBIS_TG_CHAT 에서 읽는다.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

JUBIS_DIR = Path(__file__).resolve().parent.parent          # ...\jubis
AUTO_DIR = JUBIS_DIR / "autopilot"
OUT_DIR = AUTO_DIR / "out"
LOG_DIR = AUTO_DIR / "logs"
BACKUP_DIR = AUTO_DIR / "protected_backup"
STOP_FILE = AUTO_DIR / "STOP"
LOCK_FILE = AUTO_DIR / "cycle.lock"
TELEGRAM_FILE = OUT_DIR / "telegram.txt"
JOBS_DIR = AUTO_DIR / "jobs"            # 오래 걸리는 시험을 주비스 대신 스케줄러가 돌리는 곳
JOBS_PENDING = JOBS_DIR / "pending"     # 주비스가 요청 파일(.json)을 여기에 둔다
JOBS_RUNNING = JOBS_DIR / "running"
JOBS_DONE = JOBS_DIR / "done"

# 실전 봇 폴더 (PC 돌파봇). 다르면 환경변수 JUBIS_BOT_DIR 로 바꾼다.
BOT_DIR = Path(os.environ.get("JUBIS_BOT_DIR", r"C:\Users\PC_1M"))
# 주비스가 절대 바꾸면 안 되는 파일
PROTECTED_PATTERNS = ["rule_engine_*.py", "my_keys.py", "run_bot.bat"]

CYCLE_TIMEOUT_SEC = 90 * 60     # 한 사이클 최대 90분
MAX_TURNS = 80                  # 한 사이클에서 Claude가 도구를 쓰는 최대 횟수
KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST)


def log(msg):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{now_kst():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with open(LOG_DIR / f"{now_kst():%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_telegram(text):
    token = os.environ.get("JUBIS_TG_TOKEN")
    chat = os.environ.get("JUBIS_TG_CHAT")
    if not token or not chat:
        log("텔레그램 환경변수 없음 → 전송 생략")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": text[:3900]},
            timeout=15,
        )
    except Exception as e:
        log(f"텔레그램 전송 실패: {e}")


def market_mode():
    """평일 08:30~15:40 은 장중 → 리플레이 금지(한투 토큰·실전 봇과 충돌 방지)."""
    t = now_kst()
    if t.weekday() < 5 and (8, 30) <= (t.hour, t.minute) <= (15, 40):
        return "MARKET"
    return "OFF"


def protected_files():
    files = []
    for pat in PROTECTED_PATTERNS:
        files.extend(sorted(BOT_DIR.glob(pat)))
    return files


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_protected():
    """실전 봇 파일 지문 + 백업. 백업은 이 PC 안에만 있고 git에는 안 올라간다(.gitignore)."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    snap = {}
    for p in protected_files():
        snap[p] = fingerprint(p)
        shutil.copy2(p, BACKUP_DIR / p.name)
    return snap


def verify_protected(snap):
    problems = []
    for p, digest in snap.items():
        if not p.exists():
            shutil.copy2(BACKUP_DIR / p.name, p)
            problems.append(f"{p.name} 삭제됨 → 백업으로 복구")
        elif fingerprint(p) != digest:
            shutil.copy2(BACKUP_DIR / p.name, p)
            problems.append(f"{p.name} 변경됨 → 원래대로 복구")
    new_files = set(protected_files()) - set(snap)
    for p in new_files:
        problems.append(f"{p.name} 새로 생김 (확인 필요, 지우지 않음)")
    return problems


# ---------------------------------------------------------------
# 백그라운드 작업(job): 주비스가 끝나면 주비스가 띄운 프로그램도 같이 죽는다.
# 그래서 오래 걸리는 시험은 주비스가 요청 파일만 남기고, 스케줄러가 대신 따로 돌린다.
# 요청 파일 예 (autopilot/jobs/pending/후보14.json):
#   {"script": "C:\\Users\\PC_1M\\jubis_exp_후보14.py", "args": [], "cwd": "C:\\Users\\PC_1M"}
# ---------------------------------------------------------------

def pid_alive(pid):
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                               capture_output=True, text=True, errors="replace")
            return str(pid) in r.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _inside(path, base):
    try:
        path.resolve().relative_to(Path(base).resolve())
        return True
    except ValueError:
        return False


def validate_job(job):
    """주비스가 요청할 수 있는 건 'jubis_로 시작하는 .py 파일 하나'뿐이다."""
    script = Path(job.get("script", ""))
    args = [str(a) for a in job.get("args", [])]
    cwd = Path(job.get("cwd") or BOT_DIR)
    if script.suffix.lower() != ".py" or not script.name.startswith("jubis_"):
        return "script 이름이 jubis_ 로 시작하는 .py 가 아님"
    if not script.exists():
        return "script 파일이 없음"
    if not (_inside(script, JUBIS_DIR) or _inside(script, BOT_DIR)):
        return "script 가 jubis 폴더나 실전 봇 폴더 밖에 있음"
    if not cwd.is_dir() or not (_inside(cwd, JUBIS_DIR) or _inside(cwd, BOT_DIR)):
        return "cwd 가 허용된 폴더가 아님"
    text = script.read_text(encoding="utf-8", errors="replace")
    # replay 스크립트는 'import my_keys'로 값을 바꿔 쓰므로 허용. 파일을 직접 열거나 엔진을 건드리는 건 거절.
    if "my_keys.py" in text or any("my_keys.py" in a or "rule_engine" in a for a in args):
        return "my_keys.py 파일이나 엔진 파일을 직접 다루는 코드는 허용되지 않음"
    return None


def refresh_jobs():
    """돌고 있던 job 이 끝났으면 done 으로 옮긴다."""
    for d in (JOBS_PENDING, JOBS_RUNNING, JOBS_DONE):
        d.mkdir(parents=True, exist_ok=True)
    for st in JOBS_RUNNING.glob("*.status.json"):
        try:
            info = json.loads(st.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not pid_alive(info.get("pid", 0)):
            info["ended"] = f"{now_kst():%Y-%m-%d %H:%M:%S}"
            (JOBS_DONE / st.name).write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
            st.unlink()
            log(f"job 끝남: {info.get('name')}")


def launch_pending_jobs(mode):
    refresh_jobs()
    if mode == "MARKET":
        return
    if any(JOBS_RUNNING.glob("*.status.json")):
        return                      # 한 번에 하나만 (한투 토큰 충돌 방지)
    for req in sorted(JOBS_PENDING.glob("*.json")):
        name = req.stem
        try:
            job = json.loads(req.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"job 요청 읽기 실패 {name}: {e}")
            req.rename(JOBS_DONE / f"{name}.rejected.json")
            continue
        why = validate_job(job)
        if why:
            log(f"job 거절 {name}: {why}")
            job["rejected"] = why
            (JOBS_DONE / f"{name}.rejected.json").write_text(
                json.dumps(job, ensure_ascii=False, indent=1), encoding="utf-8")
            req.unlink()
            continue
        out_path = JOBS_DIR / f"{name}.out.txt"
        out = open(out_path, "w", encoding="utf-8", errors="replace")
        cmd = [sys.executable, str(job["script"])] + [str(a) for a in job.get("args", [])]
        flags = 0
        if os.name == "nt":
            flags = 0x00000008 | 0x00000200 | 0x01000000   # DETACHED | NEW_PROCESS_GROUP | BREAKAWAY_FROM_JOB
        env = dict(os.environ, PYTHONUTF8="1")
        try:
            proc = subprocess.Popen(cmd, cwd=job.get("cwd") or BOT_DIR, stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, creationflags=flags, env=env)
        except OSError:
            proc = subprocess.Popen(cmd, cwd=job.get("cwd") or BOT_DIR, stdout=out, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL,
                                    creationflags=(flags & ~0x01000000) if os.name == "nt" else 0, env=env)
        info = {"name": name, "pid": proc.pid, "started": f"{now_kst():%Y-%m-%d %H:%M:%S}",
                "script": str(job["script"]), "output": str(out_path)}
        (JOBS_RUNNING / f"{name}.status.json").write_text(json.dumps(info, ensure_ascii=False, indent=1),
                                                          encoding="utf-8")
        req.rename(JOBS_RUNNING / req.name)
        log(f"job 시작: {name} (pid {proc.pid})")
        break


def jobs_summary():
    lines = []
    for label, d in (("돌고 있음", JOBS_RUNNING), ("끝남(최근)", JOBS_DONE)):
        files = sorted(d.glob("*.status.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for f in files:
            try:
                i = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            tail = ""
            try:
                txt = Path(i["output"]).read_text(encoding="utf-8", errors="replace").splitlines()
                tail = " / 출력 마지막: " + " | ".join(txt[-3:])[:300] if txt else " / 출력 없음"
            except Exception:
                pass
            lines.append(f"- [{label}] {i['name']} 시작 {i['started']}" + (f" 끝 {i['ended']}" if "ended" in i else "")
                         + f" (출력 파일: {i['output']})" + tail)
    for f in JOBS_DONE.glob("*.rejected.json"):
        try:
            lines.append(f"- [거절됨] {f.stem}: {json.loads(f.read_text(encoding='utf-8')).get('rejected')}")
        except Exception:
            pass
    return "\n".join(lines) if lines else "- (없음)"


def find_claude():
    for name in ("claude", "claude.cmd", "claude.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def build_prompt(mode):
    base = (AUTO_DIR / "CYCLE_PROMPT.md").read_text(encoding="utf-8")
    t = now_kst()
    header = (
        f"지금 시각(한국): {t:%Y-%m-%d %H:%M} ({'월화수목금토일'[t.weekday()]}요일)\n"
        f"모드: {mode}  (MARKET = 장중, 리플레이·주문·한투 API 호출 금지 / OFF = 리플레이 가능)\n"
        f"실전 봇 폴더: {BOT_DIR}\n\n"
        f"[백그라운드 작업 현황]\n{jobs_summary()}\n\n"
    )
    return header + base


def run_claude(mode):
    claude = find_claude()
    if not claude:
        log("claude 명령을 찾을 수 없음 (Claude Code 설치 필요)")
        send_telegram("[주비스] Claude Code가 설치되어 있지 않아 사이클을 못 돌렸어요.")
        return None
    cmd = [
        claude, "-p",
        "--permission-mode", "acceptEdits",
        "--max-turns", str(MAX_TURNS),
        "--output-format", "text",
        "--add-dir", str(BOT_DIR),
    ]
    log(f"사이클 시작 (모드 {mode})")
    try:
        r = subprocess.run(
            cmd,
            input=build_prompt(mode),
            cwd=JUBIS_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CYCLE_TIMEOUT_SEC,
        )
        out = (r.stdout or "") + ("\n[stderr]\n" + r.stderr if r.stderr else "")
        log(f"사이클 종료 (코드 {r.returncode})")
    except subprocess.TimeoutExpired:
        out = "시간 초과로 중단"
        log("사이클 시간 초과")
    with open(LOG_DIR / f"{now_kst():%Y-%m-%d_%H%M}_claude.txt", "w", encoding="utf-8") as f:
        f.write(out)
    return out


def git_commit():
    if not shutil.which("git") or not (JUBIS_DIR / ".git").exists():
        return
    subprocess.run(["git", "add", "-A"], cwd=JUBIS_DIR, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"주비스 사이클 {now_kst():%Y-%m-%d %H:%M}"],
        cwd=JUBIS_DIR, capture_output=True,
    )


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if STOP_FILE.exists():
        log("STOP 파일 있음 → 쉼")
        return
    if LOCK_FILE.exists() and time.time() - LOCK_FILE.stat().st_mtime < CYCLE_TIMEOUT_SEC + 600:
        log("이전 사이클이 아직 도는 중 → 건너뜀")
        return
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    try:
        refresh_jobs()
        snap = snapshot_protected()
        log(f"보호 파일 {len(snap)}개 지문 저장")
        run_claude(market_mode())

        problems = verify_protected(snap)
        if problems:
            STOP_FILE.write_text("보호 파일 변경 감지\n" + "\n".join(problems), encoding="utf-8")
            log("보호 파일 문제: " + " / ".join(problems))
            send_telegram("[주비스 경보] 실전 봇 파일이 바뀌어서 되돌리고 멈췄어요.\n"
                          + "\n".join(problems)
                          + "\n확인 후 autopilot\\STOP 파일을 지우면 다시 돌아요.")

        if TELEGRAM_FILE.exists():
            send_telegram(TELEGRAM_FILE.read_text(encoding="utf-8"))
            TELEGRAM_FILE.unlink()
        git_commit()
        launch_pending_jobs(market_mode())
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
