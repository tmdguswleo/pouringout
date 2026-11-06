-- 푸어링아웃 매장노트: Supabase 처음 설정 (SQL Editor에 통째로 붙여 넣고 Run)
-- 휴대폰 번호는 이 파일에 없음. 직원 목록·임시 비밀번호는 따로 받은 파일로 넣음.

create extension if not exists pgcrypto;

-- 1) 앱 데이터: 예전 아티팩트 db와 같은 모양 (컬렉션 / 문서 id / 내용)
create table if not exists public.store (
  col text not null,
  id text not null,
  data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (col, id)
);
alter table public.store enable row level security;

-- 2) 직원 계정 목록 (앱에서 직접 읽을 수 없음: 정책 없음)
create table if not exists public.staff_accounts (
  key text primary key,            -- daseul, junhyung …
  email text unique not null,      -- daseul@pouringout.app (로그인용 가짜 주소)
  is_boss boolean not null default false,
  temp_hash text,                  -- 임시 비밀번호(휴대폰 번호)의 bcrypt 값
  must_change boolean not null default true,
  changed_at timestamptz
);
alter table public.staff_accounts enable row level security;

-- 3) 도우미 함수
create or replace function public.my_key() returns text
language sql stable security definer set search_path = public as $$
  select key from public.staff_accounts where email = (auth.jwt() ->> 'email')
$$;
create or replace function public.is_staff() returns boolean
language sql stable security definer set search_path = public as $$
  select exists(select 1 from public.staff_accounts where email = (auth.jwt() ->> 'email'))
$$;
create or replace function public.is_boss() returns boolean
language sql stable security definer set search_path = public as $$
  select exists(select 1 from public.staff_accounts where email = (auth.jwt() ->> 'email') and is_boss)
$$;

-- 4) 접근 규칙: 로그인한 직원만 읽고 씀. presence(사용 중 표시)는 사장만 읽음
drop policy if exists store_read on public.store;
drop policy if exists store_write on public.store;
drop policy if exists store_update on public.store;
drop policy if exists store_delete on public.store;
create policy store_read on public.store for select to authenticated
  using (public.is_staff() and (col <> 'presence' or public.is_boss()));
create policy store_write on public.store for insert to authenticated
  with check (public.is_staff() and (col <> 'presence' or id = public.my_key()));
create policy store_update on public.store for update to authenticated
  using (public.is_staff() and (col <> 'presence' or id = public.my_key() or public.is_boss()))
  with check (public.is_staff() and (col <> 'presence' or id = public.my_key()));
create policy store_delete on public.store for delete to authenticated
  using (public.is_staff() and col <> 'presence');

-- 5) 실시간 반영
do $$ begin
  alter publication supabase_realtime add table public.store;
exception when duplicate_object then null; end $$;

-- 6) 명단에 없는 주소로는 가입 자체가 안 되게
create or replace function public.only_listed_staff() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if not exists(select 1 from public.staff_accounts where email = new.email) then
    raise exception 'not a staff account';
  end if;
  return new;
end $$;
drop trigger if exists only_listed_staff on auth.users;
create trigger only_listed_staff before insert on auth.users
  for each row execute function public.only_listed_staff();

-- 7) 첫 로그인: 임시 비밀번호(휴대폰 번호)가 맞는지 확인 (로그인 전에도 부를 수 있음)
create or replace function public.check_temp(p_key text, p_pw text) returns boolean
language sql stable security definer set search_path = public, extensions as $$
  select exists(select 1 from public.staff_accounts
    where key = p_key and must_change and temp_hash is not null and temp_hash = crypt(p_pw, temp_hash))
$$;
grant execute on function public.check_temp(text, text) to anon, authenticated;

-- 8) 내 상태 (새 비밀번호를 정해야 하는지)
create or replace function public.my_status() returns table(key text, is_boss boolean, must_change boolean)
language sql stable security definer set search_path = public as $$
  select key, is_boss, must_change from public.staff_accounts where email = (auth.jwt() ->> 'email')
$$;
grant execute on function public.my_status() to authenticated;

-- 9) 새 비밀번호를 정한 뒤 표시
create or replace function public.mark_changed() returns void
language sql security definer set search_path = public as $$
  update public.staff_accounts set must_change = false, changed_at = now() where email = (auth.jwt() ->> 'email')
$$;
grant execute on function public.mark_changed() to authenticated;

-- 10) 사장: 직원 비밀번호 초기화 → 다시 휴대폰 번호로 첫 로그인
create or replace function public.reset_staff(p_key text) returns void
language plpgsql security definer set search_path = public, auth, extensions as $$
declare r public.staff_accounts;
begin
  if not public.is_boss() then raise exception 'boss only'; end if;
  select * into r from public.staff_accounts where key = p_key;
  if r.key is null or r.is_boss then raise exception 'no such staff'; end if;
  update auth.users set encrypted_password = r.temp_hash where email = r.email;
  update public.staff_accounts set must_change = true, changed_at = null where key = p_key;
end $$;
grant execute on function public.reset_staff(text) to authenticated;

-- 11) 사장: 가입 현황
create or replace function public.staff_status() returns table(key text, must_change boolean, changed_at timestamptz, joined boolean)
language sql stable security definer set search_path = public, auth as $$
  select s.key, s.must_change, s.changed_at, exists(select 1 from auth.users u where u.email = s.email)
  from public.staff_accounts s where public.is_boss()
$$;
grant execute on function public.staff_status() to authenticated;

-- 12) 사진·영상 저장소 (주소를 아는 사람만 열 수 있게 공개 읽기, 올리기·지우기는 직원만)
insert into storage.buckets (id, name, public) values ('media', 'media', true)
  on conflict (id) do nothing;
drop policy if exists media_upload on storage.objects;
drop policy if exists media_delete on storage.objects;
create policy media_upload on storage.objects for insert to authenticated
  with check (bucket_id = 'media' and public.is_staff());
create policy media_delete on storage.objects for delete to authenticated
  using (bucket_id = 'media' and public.is_staff());
