// Supabase Edge Function "notify": store 테이블에 새 글이 들어오면 휴대폰에 알림 보내기
// Supabase → Edge Functions → Deploy a new function → Via Editor → 이름 notify → 이 내용 붙여 넣기 → Deploy
// Secrets: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT (예: mailto:주인 이메일), NOTIFY_SECRET
// 함수 설정에서 'Verify JWT'는 끄고, 대신 Database Webhook이 보내는 x-notify-secret 머리글로 확인함
import webpush from "npm:web-push@3.6.7";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const sb = createClient(Deno.env.get("SUPABASE_URL")!, (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || Deno.env.get("SUPABASE_SECRET_KEY"))!);
webpush.setVapidDetails(Deno.env.get("VAPID_SUBJECT") || "mailto:pouringout@example.com",
  Deno.env.get("VAPID_PUBLIC_KEY")!, Deno.env.get("VAPID_PRIVATE_KEY")!);
const NAME: Record<string, string> = { seunghyun: "승현", daseul: "다슬", junhyung: "준형", jeonghan: "정한", wonseok: "원석", woojun: "우준", koha: "koha", hojeong: "호정" };
const STORE: Record<string, string> = { pouring: "푸어링", meraki: "메라키" };
const cut = (s: string, n = 80) => (s || "").replace(/\s+/g, " ").trim().slice(0, n);

Deno.serve(async (req) => {
  const need = Deno.env.get("NOTIFY_SECRET");
  if (!need || req.headers.get("x-notify-secret") !== need) return new Response("forbidden", { status: 403 }); // 연결된 Webhook만 부를 수 있음
  const p = await req.json().catch(() => ({}));
  if (p.type !== "INSERT" || !p.record) return new Response("skip");
  const r = p.record, d = r.data || {};
  let title = "", body = "", tag = "", to: (k: string) => boolean = () => false;
  if (r.col === "notices") {
    if (d.showAt && Date.parse(d.showAt) > Date.now()) return new Response("later"); // 내일 공개 글은 지금 알리지 않음
    if (d.importedFrom === "notes") { title = "오늘 회의록이 올라왔어요"; body = cut(d.text || ""); tag = "minutes"; to = () => true; }
    else { title = d.store ? `${STORE[d.store] || ""} 체크리스트` : "전달사항"; body = `${NAME[d.by] || ""}: ${cut(d.text || "사진")}`; to = k => k !== d.by; }
  } else if (r.col === "checks") {
    title = `${STORE[d.store] || ""} 체크리스트`; body = cut(d.text || ""); to = k => k !== d.by;
  } else if (r.col === "orders") {
    title = "발주 요청"; body = `${NAME[d.by] || ""}: ${cut(d.text || "")}`; to = k => k === "seunghyun" && k !== d.by;
  } else return new Response("skip");
  const { data: subs } = await sb.from("store").select("id,data").eq("col", "pushsubs");
  let sent = 0;
  for (const s of subs || []) {
    const k = s.data?.k; if (!k || !to(k) || !s.data?.sub) continue;
    try { await webpush.sendNotification(s.data.sub, JSON.stringify({ title, body, tag, url: "./" })); sent++; }
    catch (e) { const c = (e as { statusCode?: number }).statusCode; if (c === 404 || c === 410) await sb.from("store").delete().eq("col", "pushsubs").eq("id", s.id); }
  }
  return new Response(JSON.stringify({ sent }), { headers: { "Content-Type": "application/json" } });
});
