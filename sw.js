/* 푸어링아웃 서비스 워커: 빠른 실행(화면 파일 저장) + 푸시 알림 */
const CACHE = "po-v4";
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./icon3-180.png", "./icon3-192.png", "./icon3-512.png",
  "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).catch(() => {})); self.skipWaiting(); });
// 업데이트 시 기존 앱 캐시·오프라인 데이터는 지우지 않음.
self.addEventListener("activate", e => { e.waitUntil(self.clients.claim()); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (u.hostname.endsWith("supabase.co")) return; // 데이터·사진은 늘 서버에서
  if (u.pathname.endsWith("version.json")) return; // 새 버전 확인은 늘 서버에서
  // 독립 복구는 앱 첫 화면으로 대체하지 않음. 외부 리소스·앱 실행 없이 읽는 페이지.
  if (u.origin === location.origin && u.pathname.endsWith("/recovery.html")) {
    e.respondWith(fetch(e.request, { cache: "no-store" }).catch(() => new Response(
      "독립 복구 페이지를 불러오지 못했습니다. 인터넷 연결을 확인하고 recovery.html을 다시 여세요. 앱 화면으로 대체하지 않았습니다.",
      { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }
    )));
    return;
  }
  const isPage = e.request.mode === "navigate" || u.pathname.endsWith("/") || u.pathname.endsWith(".html");
  if (isPage) { // 화면: 새 버전 먼저. 인터넷이 느리면 2.5초만 기다리고 저장해 둔 화면으로 바로 열기(새 버전은 받아 두었다가 다음에 열 때 반영)
    let saving = null;
    const net = fetch(e.request, { cache: "no-cache" }).then(r => { if (r.ok) { const c = r.clone(); saving = caches.open(CACHE).then(x => x.put(e.request, c)); } return r; });
    const cached = () => caches.match(e.request).then(r => r || caches.match("./"));
    e.respondWith(Promise.race([net.catch(() => null), new Promise(r => setTimeout(() => r(null), 2500))])
      .then(r => r || cached().then(c => c || net)));
    e.waitUntil(net.then(() => saving).catch(() => {})); // 새 화면을 끝까지 저장해 다음 실행에 쓰게
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
