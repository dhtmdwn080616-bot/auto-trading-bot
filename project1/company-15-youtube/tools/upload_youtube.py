#!/usr/bin/env python3
"""UPLOAD-KIT.md 의 표와 영상 폴더로 유튜브 업로드를 예약한다. 대표 노트북에서 실행.
인증: 대표 본인의 구글 계정 OAuth (client_secret.json 은 이 컴퓨터에만 둔다. 저장소에 올리지 말 것).
사용: python3 upload_youtube.py --videos 영상폴더 --start 2026-10-06 [--dry-run] [--only 1,2]
기본 동작: 비공개로 올리고 지정 시각에 자동 공개(예약). 하루 1편씩, 매일 21:00(KST)."""
import argparse, datetime as dt, json, os, re, sys

KST = dt.timezone(dt.timedelta(hours=9))
KIT = os.path.join(os.path.dirname(__file__), "..", "UPLOAD-KIT.md")

def parse_kit(path):
    rows = {}
    for line in open(path, encoding="utf8"):
        m = re.match(r"\|\s*(\d+)\s*\|(.+)\|(.+)\|(.+)\|\s*$", line)
        if m:
            rows[int(m.group(1))] = dict(title=m.group(2).strip(), description=m.group(3).strip(), pinned=m.group(4).strip())
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True); ap.add_argument("--start", required=True)
    ap.add_argument("--hour", type=int, default=21); ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--secret", default="client_secret.json"); ap.add_argument("--token", default="token.json")
    a = ap.parse_args()
    rows = parse_kit(KIT)
    want = [int(x) for x in a.only.split(",") if x] or sorted(rows)
    day0 = dt.datetime.strptime(a.start, "%Y-%m-%d").replace(hour=a.hour, tzinfo=KST)
    plan = []
    for i, n in enumerate(want):
        f = os.path.join(a.videos, f"balance-{n:02d}.mp4")
        if n not in rows or not os.path.exists(f): print(f"건너뜀: {n}번 (표 또는 파일 없음)"); continue
        when = day0 + dt.timedelta(days=i)
        if when <= dt.datetime.now(KST) + dt.timedelta(minutes=15): print(f"건너뜀: {n}번 공개 시각이 과거"); continue
        plan.append((n, f, rows[n], when))
    for n, f, r, when in plan: print(f"{n:>2}번 {when:%Y-%m-%d %H:%M} KST  {r['title']}")
    if a.dry_run or not plan: print("(dry-run 또는 올릴 영상 없음)"); return
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = Credentials.from_authorized_user_file(a.token, scopes) if os.path.exists(a.token) else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
        else: creds = InstalledAppFlow.from_client_secrets_file(a.secret, scopes).run_local_server(port=0)
        open(a.token, "w").write(creds.to_json())
    yt = build("youtube", "v3", credentials=creds)
    for n, f, r, when in plan:
        body = dict(snippet=dict(title=r["title"][:100], description=r["description"], categoryId="24"),
                    status=dict(privacyStatus="private", publishAt=when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                selfDeclaredMadeForKids=False))
        req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(f, chunksize=-1, resumable=True))
        resp = None
        while resp is None: _, resp = req.next_chunk()
        print(f"{n}번 업로드 완료: https://youtu.be/{resp['id']} (예약 {when:%m-%d %H:%M})")
    print("고정 댓글은 API로 고정할 수 없어 유튜브 스튜디오에서 직접 달아야 합니다 (UPLOAD-KIT.md 참고).")
if __name__ == "__main__": main()
