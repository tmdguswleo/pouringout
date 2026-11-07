/* 푸어링아웃 서비스 워커: 빠른 실행(화면 파일 저장) + 푸시 알림 */
const CACHE = "po-v3";
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./icon2-180.png", "./icon2-192.png", "./icon2-512.png",
  "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).catch(() => {})); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE && k !== "po-badge").map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (u.hostname.endsWith("supabase.co")) return; // 데이터·사진은 늘 서버에서
  if (u.pathname.endsWith("version.json")) return; // 새 버전 확인은 늘 서버에서
  const isPage = e.request.mode === "navigate" || u.pathname.endsWith("/") || u.pathname.endsWith(".html");
  if (isPage) { // 화면: 새 버전 먼저, 안 되면 저장해 둔 것
    e.respondWith(fetch(e.request, { cache: "no-cache" }).then(r => { const c = r.clone(); caches.open(CACHE).then(x => x.put(e.request, c)); return r; })
      .catch(() => caches.match(e.request).then(r => r || caches.match("./"))));
    return;
  }
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(res => {
    if (res.ok && (u.origin === location.origin || u.hostname === "cdn.jsdelivr.net")) { const c = res.clone(); caches.open(CACHE).then(x => x.put(e.request, c)); }
    return res;
  })));
});
async function bumpBadge() { // 아이콘 숫자 하나 올리기 (앱을 열면 실제 안 읽은 수로 다시 맞춤)
  try { const c = await caches.open("po-badge"); const r = await c.match("/badge"); const n = (r ? parseInt(await r.text(), 10) || 0 : 0) + 1;
    await c.put("/badge", new Response(String(n))); if (self.navigator.setAppBadge) await self.navigator.setAppBadge(n); } catch (_) {}
}
self.addEventListener("push", e => {
  let d = {}; try { d = e.data ? e.data.json() : {}; } catch (_) { d = { body: e.data && e.data.text() }; }
  e.waitUntil(bumpBadge().then(() => self.registration.showNotification(d.title || "pouring out", { body: d.body || "", icon: "icon2-192.png", badge: "icon2-192.png", data: { url: d.url || "./" }, tag: d.tag || undefined })));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "./";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(ws => {
    for (const w of ws) { if ("focus" in w) { w.navigate && w.navigate(url).catch(() => {}); return w.focus(); } }
    return self.clients.openWindow(url);
  }));
});
