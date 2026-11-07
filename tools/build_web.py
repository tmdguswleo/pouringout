#!/usr/bin/env python3
"""pouring.html → index.html (GitHub Pages용). 화면 코드는 같고, 홈 화면 아이콘·앱 이름·확대 막기만 머리에 넣음."""
import datetime, json, pathlib, sys
root = pathlib.Path(__file__).resolve().parent.parent
src = (root / "pouring.html").read_text(encoding="utf8")
old = '<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
assert src.count(old) == 1, "viewport meta not found"
head = ('<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">'
        '<link rel="manifest" href="manifest.webmanifest">'
        '<link rel="apple-touch-icon" href="icon3-180.png"><link rel="apple-touch-icon" sizes="1024x1024" href="icon3-1024.png">'
        '<link rel="icon" href="icon3-192.png">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-title" content="pouring out">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black">'
        '<meta name="theme-color" content="#141414">'
        '<meta name="robots" content="noindex,nofollow">')
# 새 버전 알림(사장만): 올린 시각 + 바뀐 내용. 사용법: python3 tools/build_web.py "바뀐 내용 한두 줄"
ver = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
note = sys.argv[1].strip() if len(sys.argv) > 1 else ""
head += "<script>window.__APP_VER=%s;window.__APP_NOTE=%s</script>" % (json.dumps(ver), json.dumps(note, ensure_ascii=False).replace("</", "<\\/"))
out = src.replace(old, head)
(root / "index.html").write_text(out, encoding="utf8")
(root / "manifest.webmanifest").write_text(json.dumps({
    "name": "pouring out", "short_name": "pouring out", "start_url": "./", "scope": "./",
    "display": "standalone", "background_color": "#141414", "theme_color": "#141414",
    "icons": [{"src": "icon3-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "icon3-512.png", "sizes": "512x512", "type": "image/png"}, {"src": "icon3-1024.png", "sizes": "1024x1024", "type": "image/png", "purpose": "any maskable"}]}, ensure_ascii=False, indent=1), encoding="utf8")
(root / "version.json").write_text(json.dumps({"v": ver, "note": note}, ensure_ascii=False), encoding="utf8")
(root / ".nojekyll").write_text("", encoding="utf8")
print("built index.html")
