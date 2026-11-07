#!/usr/bin/env python3
"""아이폰 메모(iCloud) '00.회의록 & 전달사항' 폴더에서 오늘 날짜 회의록(예: 11/4(수))을 읽어
앱 오늘 탭 전달사항(notices) 형식의 JSON으로 만든다.

사용:
  python3 tools/sync_minutes.py check   → 바뀌었으면 CHANGED <json경로>, 아니면 UNCHANGED / NONE
  python3 tools/sync_minutes.py fill <sha>=<assetId> ...  → 새로 올린 사진의 저장소 id를 본문에 채움
  python3 tools/sync_minutes.py merge <앱 문서 json>  → 앱에서 체크된 항목은 체크 유지
  python3 tools/sync_minutes.py mark    → 방금 올린 내용을 '반영됨'으로 기록
  python3 tools/sync_minutes.py push    → (새 주소) 확인 → 사진·영상 올리기 → 앱 체크 유지 → Supabase에 저장 → 반영됨 기록까지 한 번에
     로그인 정보: ~/.config/pouringout/sync.json {"email","password"} (저장소 밖, 커밋 안 함)
사진: 메모 속 사진은 JPEG로 바꿔 tools/.sync_img/<sha>.jpg 에 저장. 이미 올린 사진은 state의 imgs에 id가 있어 다시 안 올림.
앱 DB에 쓰는 것은 Claude(ArtifactData)가 한다. 이 스크립트는 읽기와 변환만 한다.
"""
import base64, datetime, hashlib, html, json, os, re, subprocess, sys
from html.parser import HTMLParser

FOLDER = "00.회의록 & 전달사항"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, ".sync_minutes_state.json")
OUT = os.path.join(HERE, ".sync_minutes_out.json")
IMGDIR = os.path.join(HERE, ".sync_img")
DOW = "월화수목금토일"
ALLOWED = {"div", "p", "br", "h1", "h2", "h3", "b", "strong", "i", "em", "u", "s", "strike",
           "ul", "ol", "li", "table", "tbody", "tr", "td", "th", "a"}


def today_title():
    t = datetime.date.today()
    return t, f"{t.month}/{t.day}({DOW[t.weekday()]})"


def read_note(title):
    # 제목이 오늘 날짜로 시작하는 메모 중 가장 최근에 고친 것
    script = f'''
    tell application "Notes"
      set out to ""
      set US to (ASCII character 31)
      set RS to (ASCII character 30)
      repeat with n in (notes of folder "{FOLDER}")
        if (name of n) starts with "{title}" then
          set out to out & (id of n) & US & ((modification date of n) as «class isot» as string) & US & ((creation date of n) as «class isot» as string) & US & (count of attachments of n) & US & (body of n) & RS
        end if
      end repeat
      return out
    end tell'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        sys.exit("ERROR " + r.stderr.strip())
    notes = []
    for rec in r.stdout.split("\x1e"):
        p = rec.strip("\n").split("\x1f")
        if len(p) == 5:
            notes.append({"id": p[0], "mod": p[1], "created": p[2], "att": int(p[3] or 0), "body": p[4]})
    notes.sort(key=lambda n: n["mod"], reverse=True)
    return notes[0] if notes else None


class Clean(HTMLParser):
    """앱이 허용하는 태그만 남기고 나머지는 글자만 남김"""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            m = re.match(r"data:image/([\w.+-]+);base64,(.*)", dict(attrs).get("src") or "", re.S)
            if m:
                raw = base64.b64decode(m.group(2))
                sha = hashlib.sha256(raw).hexdigest()[:24]
                os.makedirs(IMGDIR, exist_ok=True)
                jpg = os.path.join(IMGDIR, sha + ".jpg")
                if not os.path.exists(jpg):
                    src = os.path.join(IMGDIR, sha + "." + m.group(1).split("+")[0])
                    open(src, "wb").write(raw)
                    # JPEG로, 긴 변 1600px (앱의 사진 줄이기와 같게)
                    subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", "1600", src, "--out", jpg], capture_output=True)
                    os.remove(src)
                self.imgs.append(sha)
                self.out.append(f'<img data-id="@@{sha}@@">')
            return
        if tag not in ALLOWED:
            return
        if tag == "br":
            self.out.append("<br>"); return
        if tag == "a":
            href = dict(attrs).get("href") or ""
            self.out.append(f'<a href="{html.escape(href)}">' if re.match(r"https?://", href) else "<a>"); return
        self.out.append(f"<{'div' if tag == 'p' else tag}>")

    def handle_endtag(self, tag):
        if tag in ALLOWED and tag != "br":
            self.out.append(f"</{'div' if tag == 'p' else tag}>")

    def handle_data(self, data):
        self.out.append(html.escape(data, quote=False))


def convert(body):
    c = Clean(); c.feed(body); h = "".join(c.out); convert.imgs = c.imgs
    h = re.sub(r">\s+<", "><", h).strip()
    # 끝의 빈 줄 정리
    h = re.sub(r"(<div><br></div>)+$", "", h)
    # 글자만 (첫 줄 = 날짜 제목은 뺌, 빈 줄은 하나로)
    t = re.sub(r"<br>", "\n", h)
    t = re.sub(r"</(div|li|h1|h2|h3|tr)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    lines = [l.rstrip() for l in t.split("\n")]
    if lines:
        lines = lines[1:]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return h, text


# ---------- 체크리스트: AppleScript 본문에는 체크 정보가 없어서 메모 DB(NoteStore.sqlite, 읽기 전용)에서 읽음 ----------
NOTESTORE = os.path.expanduser("~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite")


def _varint(b, i):
    r = sh = 0
    while True:
        x = b[i]; i += 1; r |= (x & 0x7F) << sh; sh += 7
        if x < 0x80:
            return r, i


def _fields(b):
    i, out = 0, []
    while i < len(b):
        k, i = _varint(b, i); f, t = k >> 3, k & 7
        if t == 0:
            v, i = _varint(b, i)
        elif t == 2:
            l, i = _varint(b, i); v = b[i:i + l]; i += l
        elif t == 5:
            v = b[i:i + 4]; i += 4
        elif t == 1:
            v = b[i:i + 8]; i += 8
        else:
            raise ValueError("protobuf type %d" % t)
        out.append((f, v))
    return out


def _get(fs, f):
    return [v for (ff, v) in fs if ff == f]


def norm(t):
    return re.sub(r"\s+", " ", t.replace(" ", " ").replace("￼", "")).strip()


def checklist(title):
    """메모의 체크리스트 줄을 순서대로 [(글자, 체크됨)]"""
    import gzip, sqlite3
    try:
        con = sqlite3.connect(f"file:{NOTESTORE}?mode=ro", uri=True)
        row = con.execute("select n.ZDATA from ZICCLOUDSYNCINGOBJECT o join ZICNOTEDATA n on n.Z_PK=o.ZNOTEDATA "
                          "where o.ZTITLE1 like ? and ifnull(o.ZMARKEDFORDELETION,0)=0 order by o.ZMODIFICATIONDATE1 desc limit 1",
                          (title + "%",)).fetchone()
        con.close()
        if not row or not row[0]:
            return []
        note = _fields(_get(_fields(_get(_fields(gzip.decompress(row[0])), 2)[0]), 3)[0])
        text = _get(note, 2)[0].decode("utf-8")
        style = []  # 글자마다 (종류, 체크)
        for r in _get(note, 5):
            rf = _fields(r); n = _get(rf, 1)[0]; st, done = 0, 0
            ps = _get(rf, 2)
            if ps:
                pf = _fields(ps[0]); st = (_get(pf, 1) or [0])[0]
                ck = _get(pf, 5)
                if ck:
                    done = (_get(_fields(ck[0]), 2) or [0])[0]
            style += [(st, done)] * n
        out, pos = [], 0
        for line in text.split("\n"):
            st, done = style[pos] if pos < len(style) else (0, 0)
            if st == 103:
                out.append((norm(line), bool(done)))
            pos += len(line) + 1
        return out
    except Exception as e:  # DB 형식이 바뀌어도 동기화는 계속 (체크박스만 빠짐)
        print("WARN checklist", e, file=sys.stderr)
        return []


def mark_checks(h, items):
    """메모의 체크리스트 줄을 html에서 찾아 class="ck"(체크됐으면 "ck done").
    띄어쓰기는 무시하고 비교, 한 줄이 안 맞아도 다음 줄들은 계속 찾음(예전엔 한 줄이 어긋나면 그 뒤가 모두 빠졌음).
    메모에선 체크리스트인데 html에 <div>로 온 줄도 체크 항목으로 바꿈."""
    key = lambda t: re.sub(r"\s+", "", t.replace("\u00a0", "").replace("\ufffc", ""))
    keys = [key(t) for t, _ in items]; used = [False] * len(items); pos = 0

    def find(txt):
        nonlocal pos
        k = key(txt)
        if not k:
            return None
        for j in list(range(pos, len(items))) + list(range(0, pos)):
            if not used[j] and keys[j] == k:
                used[j] = True
                if j >= pos:
                    pos = j + 1
                return j
        return None

    def cls(j):
        return "ck done" if items[j][1] else "ck"

    def rep(m):
        j = find(html.unescape(re.sub(r"<[^>]+>", "", m.group(1))))
        return m.group(0) if j is None else f'<li class="{cls(j)}">' + m.group(1) + "</li>"
    h = re.sub(r"<li>(.*?)</li>", rep, h, flags=re.S)

    def rep2(m):
        inner = m.group(1); k = key(html.unescape(re.sub(r"<[^>]+>", "", inner)))
        if not k:
            return m.group(0)
        for j in range(len(items)):
            if not used[j] and keys[j] == k:
                used[j] = True
                return f'<ul><li class="{cls(j)}">' + inner + "</li></ul>"
        return m.group(0)
    return re.sub(r"<div>((?:(?!</?div[ >]).)*?)</div>", rep2, h, flags=re.S)


# ---------- 영상: AppleScript 본문에는 영상이 빠져 있음 → 메모 DB에서 위치(바로 앞 줄)와 파일을 찾아 그 자리에 넣음 ----------
MEDIA_DIR = os.path.expanduser("~/Library/Group Containers/group.com.apple.notes/Media")


def note_videos(title):
    """[(파일 경로 또는 None, 파일 이름, 바로 앞 줄)] — 메모 속 순서대로"""
    import gzip, sqlite3, glob as _g
    out = []
    try:
        con = sqlite3.connect(f"file:{NOTESTORE}?mode=ro", uri=True)
        row = con.execute("select n.ZDATA from ZICCLOUDSYNCINGOBJECT o join ZICNOTEDATA n on n.Z_PK=o.ZNOTEDATA "
                          "where o.ZTITLE1 like ? and ifnull(o.ZMARKEDFORDELETION,0)=0 order by o.ZMODIFICATIONDATE1 desc limit 1",
                          (title + "%",)).fetchone()
        if not row or not row[0]:
            return out
        note = _fields(_get(_fields(_get(_fields(gzip.decompress(row[0])), 2)[0]), 3)[0])
        text = _get(note, 2)[0].decode("utf-8")
        pos = 0
        for r in _get(note, 5):
            rf = _fields(r); n = _get(rf, 1)[0]
            ai = _get(rf, 12)
            if ai:
                af = _fields(ai[0])
                ident = (_get(af, 1) or [b""])[0].decode(); uti = (_get(af, 2) or [b""])[0].decode()
                if re.search(r"movie|mpeg-4|video", uti, re.I):
                    lines = [norm(l) for l in text[:pos].replace("￼", "\n").split("\n")]
                    before = next((l for l in reversed(lines) if l), "")
                    m = con.execute("select m.ZIDENTIFIER, m.ZFILENAME from ZICCLOUDSYNCINGOBJECT o join ZICCLOUDSYNCINGOBJECT m on m.Z_PK=o.ZMEDIA "
                                    "where o.ZIDENTIFIER=?", (ident,)).fetchone()
                    path = None
                    if m and m[0]:
                        hits = _g.glob(os.path.join(MEDIA_DIR, m[0], "**", m[1] or "*"), recursive=True)
                        path = next((h for h in hits if os.path.isfile(h)), None)
                    out.append((path, (m[1] if m else "") or "영상", before))
            pos += n
        con.close()
    except Exception as e:
        print("WARN video", e, file=sys.stderr)
    return out


def to_mp4(path):
    """앱에 올릴 mp4 (15MB 이하가 되도록 화질을 낮춰 가며). 같은 파일은 다시 안 만듦"""
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()[:24]
    os.makedirs(IMGDIR, exist_ok=True)
    out = os.path.join(IMGDIR, sha + ".mp4")
    if not os.path.exists(out):
        for preset in ("PresetAppleM4VWiFi", "PresetAppleM4VCellular", "PresetAppleM4ViPod"):  # 휴대폰에서 보기 좋은 크기부터 작게
            if os.path.exists(out):
                os.remove(out)
            tmp = out[:-4] + ".m4v"  # 이 프리셋들은 .m4v로만 저장됨 → 만든 뒤 .mp4로 이름만 바꿈(같은 MPEG-4)
            subprocess.run(["avconvert", "--preset", preset, "--source", path, "--output", tmp, "--replace"], capture_output=True, timeout=600)
            if os.path.exists(tmp):
                os.replace(tmp, out)
            if os.path.exists(out) and os.path.getsize(out) <= 15 * 1024 * 1024:
                break
    return sha, out if os.path.exists(out) and os.path.getsize(out) <= 15 * 1024 * 1024 else None


def poster_jpg(mp4):
    """영상 첫 장면을 JPEG로 (qlmanage 썸네일). 이름 = 내용 해시"""
    import tempfile
    try:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["qlmanage", "-t", "-s", "640", "-o", td, mp4], capture_output=True, timeout=120)
            png = os.path.join(td, os.path.basename(mp4) + ".png")
            if not os.path.exists(png):
                return None
            jpg = os.path.join(td, "p.jpg")
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", png, "--out", jpg], capture_output=True)
            raw = open(jpg, "rb").read()
        sha = hashlib.sha256(raw).hexdigest()[:24]
        out = os.path.join(IMGDIR, sha + ".jpg")
        if not os.path.exists(out):
            open(out, "wb").write(raw)
        return sha
    except Exception as e:
        print("WARN poster", e, file=sys.stderr)
        return None


def top_blocks(h):
    """맨 바깥 줄(블록)들의 끝 위치와 글자 [(끝 위치, 글자)]"""
    out, depth, start = [], 0, 0
    for m in re.finditer(r"<(/?)(div|ul|ol|table|h1|h2|h3)\b[^>]*>", h):
        if not m.group(1):
            if depth == 0:
                start = m.start()
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                txt = html.unescape(re.sub(r"<[^>]+>", " ", h[start:m.end()]))
                out.append((m.end(), norm(txt)))
    return out


def place_videos(h, vids):
    """영상마다 '바로 앞 줄' 글자로 끝나는(또는 그 글자가 든) 줄 뒤에 <video> 줄을 넣음. 못 찾으면 맨 끝"""
    missing, after = [], 0
    for path, name, before in vids:
        if not path:
            missing.append(name); continue
        r = to_mp4(path)
        if not r[1]:
            missing.append(name); continue
        ps = poster_jpg(r[1])  # 첫 장면 사진(미리보기)
        tag = f'<div><video data-id="@@{r[0]}@@"' + (f' data-poster="@@{ps}@@"' if ps else "") + '></video></div>'
        b = norm(before)
        spot = next((end for end, t in top_blocks(h) if end > after and b and (t.endswith(b) or b in t)), None)
        if spot is None:
            h += tag; after = len(h); continue
        h = h[:spot] + tag + h[spot:]; after = spot + len(tag)
    return h, missing


SUPA_URL = "https://wvmvsobyigsqmwvuepqk.supabase.co"
SUPA_KEY = "sb_publishable_sVSKargypenzMn-XwEZLRw_y53zir3o"  # 공개용 키
CRED = os.path.expanduser("~/.config/pouringout/sync.json")


def _req(method, path, token=None, body=None, headers=None, raw=None):
    import urllib.request, urllib.error
    h = {"apikey": SUPA_KEY}
    if token: h["Authorization"] = "Bearer " + token
    data = None
    if raw is not None: data = raw
    elif body is not None: data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    h.update(headers or {})
    r = urllib.request.Request(SUPA_URL + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as res:
            t = res.read(); return res.status, (json.loads(t) if t[:1] in (b"{", b"[") else t)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf8", "replace")


def push():
    """새 주소(Supabase)로 오늘 회의록을 바로 반영"""
    # 2026-11-07부터 회의록은 앱에서 바로 씀 → 아이폰 메모 동기화 중단
    if datetime.date.today() >= datetime.date(2026, 11, 7):
        print("STOPPED 11/7부터 회의록은 앱에서 바로 써요"); return
    import io, contextlib, secrets
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sys.argv = [sys.argv[0], "check"]; main()
    lines = buf.getvalue().strip().splitlines()
    if not lines or not lines[0].startswith("CHANGED"):
        print(lines[0] if lines else "NONE"); return
    cred = json.load(open(CRED))
    c, j = _req("POST", "/auth/v1/token?grant_type=password", body={"email": cred["email"], "password": cred["password"]})
    if c != 200: sys.exit("ERROR 로그인 실패 " + str(c))
    tok = j["access_token"]
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    imgs = st.setdefault("imgs", {}); nimg = nvid = 0
    for ln in lines[1:]:
        if not ln.startswith("UPLOAD"): continue
        _, sha, f = ln.split(" ", 2)
        aid = secrets.token_hex(16); ct = "video/mp4" if f.endswith(".mp4") else "image/jpeg"
        c, j = _req("POST", "/storage/v1/object/media/" + aid, tok, raw=open(f, "rb").read(), headers={"Content-Type": ct})
        if c not in (200, 201): sys.exit("ERROR 사진 올리기 실패 " + str(c))
        imgs[sha] = aid
        if ct == "video/mp4": nvid += 1
        else: nimg += 1
    json.dump(st, open(STATE, "w"))
    d = json.load(open(OUT))
    d["html"] = re.sub(r"@@([0-9a-f]+)@@", lambda m: imgs.get(m.group(1), m.group(0)), d["html"])
    did = "mt-" + d["date"]
    c, rows = _req("GET", "/rest/v1/store?col=eq.notices&id=eq." + did + "&select=data", tok)
    if c == 200 and rows:
        app = rows[0]["data"]
        done = {norm(html.unescape(re.sub(r"<[^>]+>", "", t))) for t in re.findall(r'<li class="ck done">(.*?)</li>', app.get("html") or "", re.S)}
        d["html"] = re.sub(r'<li class="ck">(.*?)</li>', lambda m: '<li class="ck done">' + m.group(1) + "</li>" if norm(html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))) in done else m.group(0), d["html"], flags=re.S)
    json.dump(d, open(OUT, "w"), ensure_ascii=False)
    c, j = _req("POST", "/rest/v1/store", tok, body={"col": "notices", "id": did, "data": d, "updated_at": datetime.datetime.utcnow().isoformat() + "Z"}, headers={"Prefer": "resolution=merge-duplicates"})
    if c not in (200, 201, 204): sys.exit("ERROR 저장 실패 " + str(c) + " " + str(j)[:200])
    st.update({"date": d["date"], "hash": d["srcHash"]}); json.dump(st, open(STATE, "w"))
    print(f"PUSHED {d['date']} 사진 {nimg}장 영상 {nvid}개")
    for ln in lines[1:]:
        if ln.startswith("VIDEO_MISSING"): print(ln)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "push": return push()
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if cmd == "fill":
        imgs = st.setdefault("imgs", {})
        for a in sys.argv[2:]:
            k, v = a.split("=", 1)
            if not re.fullmatch(r"[0-9a-f]{32}", v):
                sys.exit("ERROR 저장소 id 형식이 아님: " + v)
            imgs[k] = v
        json.dump(st, open(STATE, "w"))
        d = json.load(open(OUT))
        d["html"] = re.sub(r"@@([0-9a-f]+)@@", lambda m: imgs.get(m.group(1), m.group(0)), d["html"])
        left = re.findall(r"@@([0-9a-f]+)@@", d["html"])
        json.dump(d, open(OUT, "w"), ensure_ascii=False)
        print("FILLED" if not left else "MISSING " + " ".join(left)); return
    if cmd == "merge":
        # 앱에서 체크된 항목은 메모에 체크가 없어도 체크된 채로 둠 (앱에서 누른 체크가 동기화로 풀리지 않게)
        app = json.load(open(sys.argv[2])); app = app.get("data", app) if isinstance(app.get("data"), dict) else app
        done = {norm(html.unescape(re.sub(r"<[^>]+>", "", t))) for c, t in re.findall(r'<li class="(ck done)">(.*?)</li>', app.get("html") or "", re.S)}
        d = json.load(open(OUT)); n = 0
        def rep(m):
            nonlocal n
            if norm(html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))) in done:
                n += 1; return '<li class="ck done">' + m.group(1) + "</li>"
            return m.group(0)
        d["html"] = re.sub(r'<li class="ck">(.*?)</li>', rep, d["html"], flags=re.S)
        json.dump(d, open(OUT, "w"), ensure_ascii=False)
        print("MERGED", n); return
    if cmd == "mark":
        if os.path.exists(OUT):
            d = json.load(open(OUT))
            st.update({"date": d["date"], "hash": d["srcHash"]})
            json.dump(st, open(STATE, "w"))
            print("MARKED", d["date"])
        return
    day, title = today_title()
    n = read_note(title)
    if not n:
        print("NONE", title); return
    h, text = convert(n["body"])
    h = mark_checks(h, checklist(title))
    h, vmiss = place_videos(h, note_videos(title))
    hsh = hashlib.sha256(h.encode()).hexdigest()[:16]
    if st.get("date") == day.isoformat() and st.get("hash") == hsh:
        print("UNCHANGED", title); return
    # 메모 앱 시각(이 Mac 시간대) → UTC ISO
    created = datetime.datetime.fromisoformat(n["created"]).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data = {"date": day.isoformat(), "store": "", "by": "", "past": True, "importedFrom": "notes",
            "html": h, "text": text, "srcHash": hsh, "srcMod": n["mod"],
            "createdAt": created}
    # 이미 올린 사진은 id로 바로 채우고, 새 사진만 올리라고 알려줌
    imgs = st.get("imgs", {})
    data["html"] = re.sub(r"@@([0-9a-f]+)@@", lambda m: imgs.get(m.group(1), m.group(0)), data["html"])
    new = sorted(set(re.findall(r"@@([0-9a-f]+)@@", data["html"])))
    json.dump(data, open(OUT, "w"), ensure_ascii=False)
    print("CHANGED", title, OUT)
    for sha in new:
        f = os.path.join(IMGDIR, sha + ".jpg")
        print("UPLOAD", sha, f if os.path.exists(f) else os.path.join(IMGDIR, sha + ".mp4"))
    for nm in vmiss:
        print("VIDEO_MISSING", nm, "(이 Mac에 영상 파일이 아직 내려받아지지 않았거나 15MB가 넘음)")


if __name__ == "__main__":
    main()
