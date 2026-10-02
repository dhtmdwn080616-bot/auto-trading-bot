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
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
