-- 4단계: 회의록 자동 반영용 계정(sync) 추가 (SQL Editor에 붙여 넣고 Run)
-- 사람 계정이 아니라 이 Mac의 회의록 동기화 도구가 쓰는 계정. 앱 로그인 화면에는 안 나옴.
insert into public.staff_accounts(key, email, is_boss, temp_hash, must_change)
values ('sync', 'sync@pouringout.app', false, null, false)
on conflict (key) do nothing;
