-- 6단계: 시간 알림 (밀크티 out 15:00 같은 항목을 그 시각에 그날 그 매장 근무자에게)
-- 1분마다 notify 함수를 {"type":"tick"}으로 부름. 비밀값 없음 (때가 된 알림만 보냄)
create extension if not exists pg_cron;
create extension if not exists pg_net;
select cron.unschedule('notify-tick') where exists (select 1 from cron.job where jobname = 'notify-tick');
select cron.schedule('notify-tick', '* * * * *', $$
  select net.http_post(
    url := 'https://wvmvsobyigsqmwvuepqk.supabase.co/functions/v1/notify',
    headers := '{"Content-Type":"application/json"}'::jsonb,
    body := '{"type":"tick"}'::jsonb)
$$);
