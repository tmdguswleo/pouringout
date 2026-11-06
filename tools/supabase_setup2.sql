-- 2단계: 로그인 상태 확인 · 사장 휴대폰 번호 확인 (SQL Editor에 붙여 넣고 Run)

-- 로그인 화면용: new = 아직 가입 전(휴대폰 번호로 첫 로그인), temp = 초기화됨(휴대폰 번호), set = 본인 비밀번호
create or replace function public.login_state(p_key text) returns text
language sql stable security definer set search_path = public, auth as $$
  select case
    when s.key is null then null
    when not exists(select 1 from auth.users u where u.email = s.email) then 'new'
    when s.must_change then 'temp'
    else 'set' end
  from (select 1) d left join public.staff_accounts s on s.key = p_key
$$;
grant execute on function public.login_state(text) to anon, authenticated;

-- 직원 비밀번호 초기화 전에 사장 휴대폰 번호 확인 (사장만)
create or replace function public.verify_boss_phone(p_pw text) returns boolean
language sql stable security definer set search_path = public, extensions as $$
  select public.is_boss() and exists(select 1 from public.staff_accounts
    where is_boss and temp_hash is not null and temp_hash = crypt(p_pw, temp_hash))
$$;
grant execute on function public.verify_boss_phone(text) to authenticated;
