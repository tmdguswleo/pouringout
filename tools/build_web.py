#!/usr/bin/env python3
"""pouring.html → index.html (GitHub Pages용). 화면 코드는 같고, 홈 화면 아이콘·앱 이름·확대 막기만 머리에 넣음."""
import json, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
src = (root / "pouring.html").read_text(encoding="utf8")
old = '<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">'
assert src.count(old) == 1, "viewport meta not found"
head = ('<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover">'
        '<link rel="manifest" href="manifest.webmanifest">'
        '<link rel="apple-touch-icon" href="icon2-180.png">'
        '<link rel="icon" href="icon2-192.png">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-title" content="pouring out">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black">'
        '<meta name="theme-color" content="#141414">'
        '<meta name="robots" content="noindex,nofollow">')
out = src.replace(old, head)
(root / "index.html").write_text(out, encoding="utf8")
(root / "manifest.webmanifest").write_text(json.dumps({
    "name": "pouring out", "short_name": "pouring out", "start_url": "./", "scope": "./",
    "display": "standalone", "background_color": "#141414", "theme_color": "#141414",
    "icons": [{"src": "icon2-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "icon2-512.png", "sizes": "512x512", "type": "image/png"}]}, ensure_ascii=False, indent=1), encoding="utf8")
(root / ".nojekyll").write_text("", encoding="utf8")
print("built index.html")
