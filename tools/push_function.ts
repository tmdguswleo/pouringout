// Supabase Edge Function "notify": store 테이블에 새 글이 들어오면 휴대폰에 알림 보내기
// Supabase → Edge Functions → notify → Code → 이 내용 붙여 넣기 → Deploy
// Secrets: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT (mailto:주인 이메일), NOTIFY_SECRET
// 함수 설정에서 'Verify JWT'는 끄고, 대신 Database Webhook이 보내는 x-notify-secret 머리글로 확인함
const NAME: Record<string, string> = { seunghyun: "승현", daseul: "다슬", junhyung: "준형", jeonghan: "정한", wonseok: "원석", woojun: "우준", koha: "koha", hojeong: "호정" };
const STORE: Record<string, string> = { pouring: "푸어링", meraki: "메라키" };
const cut = (s: string, n = 80) => (s || "").replace(/\s+/g, " ").trim().slice(0, n);
const json = (o: unknown, status = 200) => new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json" } });

// 시간 알림(tick): 1분마다 pg_cron이 {"type":"tick"}으로 부름 → remindAt이 지난 체크 항목(예: 밀크티 out 15:00)을
// 그날 그 매장 근무자에게 알리고 reminded 표시. 비밀값 없이 불러도 '때가 된 알림'만 보내므로 괜찮음
const SLOT: Record<string, string[]> = { meraki: ["m1", "m2"], pouring: ["b1", "b2"] };
// 직원 알림은 근무 중일 때만 (사장은 늘). 오늘(한국 시간) 근무표 칸 시간 + koha 근무(monthnotes/koha), 근무 시작 시각부터 (2026-11-07 사용자: 30분 전 말고 시작할 때)
const SLOT_T: Record<string, [string, string]> = { m1: ["8:00", "10:30"], m2: ["10:30", "19:30"], b1: ["10:30", "13:30"], b2: ["13:30", "22:30"] };
const mins = (t: string) => { const [h, m] = String(t || "").split(":").map(Number); return (h || 0) * 60 + (m || 0); };
// deno-lint-ignore no-explicit-any
async function workFilter(sb: any) {
  const k = new Date(Date.now() + 9 * 3600e3), day = k.toISOString().slice(0, 10), now = k.getUTCHours() * 60 + k.getUTCMinutes();
  const { data: sc } = await sb.from("store").select("data").eq("col", "schedule").eq("id", day).maybeSingle();
  const { data: ko } = await sb.from("store").select("data").eq("col", "monthnotes").eq("id", "koha").maybeSingle();
  if (!sc) return (_: string) => true; // 오늘 근무표가 없으면 거르지 않음
  const on = new Set<string>(), d = sc.data || {};
  for (const [slot, [a, b]] of Object.entries(SLOT_T)) if (now >= mins(a) && now < mins(b)) (d[slot] || []).forEach((x: string) => on.add(x));
  for (const e of (ko?.data?.entries || [])) if (e.date === day && now >= mins(e.start) && now < mins(e.end)) on.add("koha");
  (d.off || []).forEach((x: string) => on.delete(x));
  return (x: string) => x === "seunghyun" || on.has(x);
}
async function tick() {
  const { createClient } = await import("npm:@supabase/supabase-js@2.45.4");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || Deno.env.get("SUPABASE_SECRET_KEY") || "";
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, key);
  const now = new Date(), from = new Date(now.getTime() - 6 * 3600e3); // 6시간 넘게 지난 건 안 보냄
  const { data: due, error } = await sb.from("store").select("id,data").eq("col", "notices")
    .gte("data->>remindAt", from.toISOString()).lte("data->>remindAt", now.toISOString());
  if (error) return json({ error: "due " + error.message }, 500);
  const list = (due || []).filter(r => !r.data?.reminded && !r.data?.done);
  if (!list.length) return json({ due: 0 });
  const { default: webpush } = await import("npm:web-push@3.6.7");
  webpush.setVapidDetails(Deno.env.get("VAPID_SUBJECT") || "mailto:pouringout@example.com", Deno.env.get("VAPID_PUBLIC_KEY")!, Deno.env.get("VAPID_PRIVATE_KEY")!);
  const { data: subs } = await sb.from("store").select("id,data").eq("col", "pushsubs");
  const working = await workFilter(sb);
  let sent = 0;
  for (const r of list) {
    const d = r.data || {};
    const { data: sc } = await sb.from("store").select("data").eq("col", "schedule").eq("id", d.date).maybeSingle();
    const who = new Set<string>(); (SLOT[d.store] || []).forEach(k => (sc?.data?.[k] || []).forEach((x: string) => who.add(x)));
    const to = (k: string) => (who.size ? who.has(k) : true) && working(k); // 근무표가 비어 있으면 모두에게(근무 중인 사람만)
    for (const s of subs || []) {
      const k = s.data?.k; if (!k || !to(k) || !s.data?.sub) continue;
      try { await webpush.sendNotification(s.data.sub, JSON.stringify({ title: `${STORE[d.store] || ""} ${cut(d.text || "", 40)}`, body: "시간이 됐어요. 체크리스트에서 확인해 주세요", tag: "remind-" + r.id, url: "./" })); sent++; }
      catch (e) { const c = (e as { statusCode?: number }).statusCode; if (c === 404 || c === 410) await sb.from("store").delete().eq("col", "pushsubs").eq("id", s.id); }
    }
    await sb.from("store").update({ data: { ...d, reminded: true } }).eq("col", "notices").eq("id", r.id);
  }
  return json({ due: list.length, sent });
}

Deno.serve(async (req) => {
  const p = await req.json().catch(() => ({}));
  if (p.type === "tick") { try { return await tick(); } catch (e) { return json({ error: String((e as Error)?.message || e) }, 500); } }
  const need = Deno.env.get("NOTIFY_SECRET");
  if (!need || req.headers.get("x-notify-secret") !== need) return json({ error: "forbidden" }, 403); // 연결된 Webhook만 부를 수 있음
  try {
    if (p.type !== "INSERT" || !p.record) return json({ skip: true });
    const r = p.record, d = r.data || {};
    let title = "", body = "", tag = "", to: (k: string) => boolean = () => false;
    if (r.col === "notices") {
      if (d.showAt && Date.parse(d.showAt) > Date.now()) return json({ later: true }); // 내일 공개 글은 지금 알리지 않음
      if (d.importedFrom === "notes") { title = "오늘 회의록이 올라왔어요"; body = cut(d.text || ""); tag = "minutes"; to = () => true; }
      else { title = d.store ? `${STORE[d.store] || ""} 체크리스트` : "전달사항"; body = `${NAME[d.by] || ""}: ${cut(d.text || "사진")}`; to = k => k !== d.by; }
    } else if (r.col === "checks") {
      title = `${STORE[d.store] || ""} 체크리스트`; body = cut(d.text || ""); to = k => k !== d.by;
    } else if (r.col === "orders") {
      title = "발주 요청"; body = `${NAME[d.by] || ""}: ${cut(d.text || "")}`; to = k => k === "seunghyun" && k !== d.by;
    } else return json({ skip: true });
    const { default: webpush } = await import("npm:web-push@3.6.7");
    const { createClient } = await import("npm:@supabase/supabase-js@2.45.4");
    const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || Deno.env.get("SUPABASE_SECRET_KEY") || "";
    const sb = createClient(Deno.env.get("SUPABASE_URL")!, key);
    webpush.setVapidDetails(Deno.env.get("VAPID_SUBJECT") || "mailto:pouringout@example.com", Deno.env.get("VAPID_PUBLIC_KEY")!, Deno.env.get("VAPID_PRIVATE_KEY")!);
    const { data: subs, error } = await sb.from("store").select("id,data").eq("col", "pushsubs");
    if (error) return json({ error: "read " + error.message }, 500);
    const working = await workFilter(sb);
    let sent = 0;
    for (const s of subs || []) {
      const k = s.data?.k; if (!k || !to(k) || !working(k) || !s.data?.sub) continue;
      try { await webpush.sendNotification(s.data.sub, JSON.stringify({ title, body, tag, url: "./" })); sent++; }
      catch (e) { const c = (e as { statusCode?: number }).statusCode; if (c === 404 || c === 410) await sb.from("store").delete().eq("col", "pushsubs").eq("id", s.id); }
    }
    return json({ sent, subs: (subs || []).length });
  } catch (e) {
    return json({ error: String((e as Error)?.message || e) }, 500);
  }
});
