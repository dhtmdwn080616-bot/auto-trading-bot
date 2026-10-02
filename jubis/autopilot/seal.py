# -*- coding: utf-8 -*-
"""
실험 사전등록 봉인.  "결과를 보고 기준을 바꾸지 않는다"를 증명하는 도구.

  python autopilot/seal.py memory/experiments/후보14.md          # 시험 전에 봉인
  python autopilot/seal.py --check memory/experiments/후보14.md  # 결과 쓸 때 확인

파일에서 '## 결과' 줄 위쪽(가설·규칙·합격 기준)만 지문을 찍어 SEALS.log 에 남긴다.
결과를 아래에 덧붙이는 건 괜찮고, 위쪽을 고치면 --check 가 CHANGED 를 낸다.
"""

import hashlib
import sys
from datetime import datetime
from pathlib import Path

SEALS = Path(__file__).resolve().parent.parent / "memory" / "experiments" / "SEALS.log"


def preregistered_part(path):
    text = Path(path).read_text(encoding="utf-8")
    return text.split("\n## 결과", 1)[0].strip()


def digest(path):
    return hashlib.sha256(preregistered_part(path).encode("utf-8")).hexdigest()


def seal(path):
    name = Path(path).name
    for line in SEALS.read_text(encoding="utf-8").splitlines() if SEALS.exists() else []:
        if line.split("\t")[-1] == name:
            print(f"이미 봉인됨: {line}")
            return 1
    with open(SEALS, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{digest(path)}\t{name}\n")
    print(f"봉인 완료: {name}")
    return 0


def check(path):
    name = Path(path).name
    if not SEALS.exists():
        print("NOT SEALED")
        return 2
    for line in SEALS.read_text(encoding="utf-8").splitlines():
        stamp, d, n = line.split("\t")
        if n == name:
            if d == digest(path):
                print(f"OK (봉인 {stamp})")
                return 0
            print(f"CHANGED — 봉인({stamp}) 뒤에 규칙/기준이 바뀜. 이 실험은 무효.")
            return 3
    print("NOT SEALED")
    return 2


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "--check":
        sys.exit(check(args[1]))
    if len(args) == 1:
        sys.exit(seal(args[0]))
    print(__doc__)
    sys.exit(1)
