#!/usr/bin/env python3
"""아이폰 메모에서 옮겨 온 자료실 메모 중, 사진·영상이 맨 아래에 몰려 있는 것을 찾아
아이폰 메모(NoteStore.sqlite, 읽기 전용)의 첨부 위치(바로 앞 줄)를 계획(JSON)으로 만든다.

사용: python3 tools/media_order.py <docs JSON 폴더> <계획 출력.json>
실제 본문 재배치는 브라우저(앱의 docClean과 같은 규칙)에서 하고, DB 쓰기는 Claude가 한다.
"""
import glob, gzip, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sync_minutes as sm

IMG = re.compile(r"(jpeg|jpg|png|heic|heif|gif|tiff|image)", re.I)
MOV = re.compile(r"(movie|mpeg-4|mp4|quicktime|video)", re.I)


def note_attachments(con, title):
    rows = con.execute("select n.ZDATA from ZICCLOUDSYNCINGOBJECT o join ZICNOTEDATA n on n.Z_PK=o.ZNOTEDATA "
                       "where o.ZTITLE1=? and ifnull(o.ZMARKEDFORDELETION,0)=0", (title,)).fetchall()
    if not rows and title:  # 앱에서 제목이 조금 바뀐 경우([토디 사용법] → 토디 사용법): 제목을 포함하는 메모가 하나뿐이면 그것
        rows = con.execute("select n.ZDATA from ZICCLOUDSYNCINGOBJECT o join ZICNOTEDATA n on n.Z_PK=o.ZNOTEDATA "
                           "where o.ZTITLE1 like ? and ifnull(o.ZMARKEDFORDELETION,0)=0", ("%" + title + "%",)).fetchall()
    if len(rows) != 1 or not rows[0][0]:
        return None  # 없거나 같은 제목이 여러 개면 건너뜀
    note = sm._fields(sm._get(sm._fields(sm._get(sm._fields(gzip.decompress(rows[0][0])), 2)[0]), 3)[0])
    text = sm._get(note, 2)[0].decode("utf-8")
    pos, out = 0, []
    for r in sm._get(note, 5):
        rf = sm._fields(r); n = sm._get(rf, 1)[0]
        ai = sm._get(rf, 12)
        if ai:
            uti = (sm._get(sm._fields(ai[0]), 2) or [b""])[0].decode()
            k = "video" if MOV.search(uti) else "image" if IMG.search(uti) else None
            if k:
                lines = [sm.norm(l) for l in text[:pos].replace("￼", "\n").split("\n")]
                before = next((l for l in reversed(lines) if l), "")
                out.append({"k": k, "before": before})
        pos += n
    return out


def main():
    src, outp = sys.argv[1], sys.argv[2]
    con = sqlite3.connect(f"file:{sm.NOTESTORE}?mode=ro", uri=True)
    plans, skipped = [], []
    for f in sorted(glob.glob(os.path.join(src, "*.json"))):
        raw = json.load(open(f)); d = raw.get("data", raw) if isinstance(raw.get("data"), dict) else raw
        did = os.path.basename(f)[:-5]
        h = d.get("html") or ""
        media = re.findall(r'<(img|video) data-id="([0-9a-f]{32})"', h)
        if not media or d.get("importedFrom") != "notes":
            continue
        # 마지막 글자 뒤에 사진·영상만 있는지 (= 맨 아래에 몰려 있음)
        last_text = max((m.end() for m in re.finditer(r">[^<\s][^<]*<", h)), default=0)
        first_media = h.find("<" + media[0][0] + " data-id")
        if first_media < last_text:
            continue  # 이미 본문 중간에 있음
        atts = note_attachments(con, d.get("title") or "")
        if atts is None or len(atts) != len(media) or [a["k"] for a in atts] != [("video" if t == "video" else "image") for t, _ in media]:
            skipped.append((did, d.get("title"), len(media), None if atts is None else len(atts)))
            continue
        plans.append({"id": did, "title": d.get("title"), "version": raw.get("version"),
                      "items": [{"id": mid, "k": a["k"], "before": a["before"]} for (t, mid), a in zip(media, atts)]})
    json.dump(plans, open(outp, "w"), ensure_ascii=False, indent=1)
    print("PLANS", len(plans))
    for p in plans:
        print(" ", p["id"], p["title"], len(p["items"]))
    print("SKIPPED", len(skipped))
    for s in skipped:
        print(" ", s)


if __name__ == "__main__":
    main()
