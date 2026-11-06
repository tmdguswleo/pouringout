#!/usr/bin/env python3
"""오늘 회의록(아이폰 메모 '00.회의록 & 전달사항', 제목 예: 11/4(수))의 수정 시각을 30초마다 확인해서
바뀌었을 때만 한 줄 출력한다. (Claude의 Monitor가 이 줄을 받아 sync_minutes.py로 앱에 반영)
메모 DB는 읽기만 한다."""
import datetime, os, sqlite3, sys, time

DB = os.path.expanduser("~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite")
DOW = "월화수목금토일"
INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 30


def title():
    t = datetime.date.today()
    return f"{t.month}/{t.day}({DOW[t.weekday()]})"


def mod(tt):
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
        r = con.execute("select max(ZMODIFICATIONDATE1) from ZICCLOUDSYNCINGOBJECT where ZTITLE1 like ? and ifnull(ZMARKEDFORDELETION,0)=0",
                        (tt + "%",)).fetchone()
        con.close()
        return r[0] if r else None
    except Exception as e:
        print("WATCH_ERROR", e, flush=True)
        return "error"


last = {}
while True:
    tt = title()
    m = mod(tt)
    if m not in (None, "error"):
        if tt in last and last[tt] != m:
            print("MINUTES_CHANGED", tt, flush=True)
        last[tt] = m
    elif m is None and tt not in last:
        last[tt] = None  # 아직 오늘 메모 없음 → 생기면 알림
    time.sleep(INTERVAL)
