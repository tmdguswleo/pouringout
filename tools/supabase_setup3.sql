-- 3단계: 사진·영상 다시 올리기(덮어쓰기)·지우기를 직원에게 허용 (SQL Editor에 붙여 넣고 Run)
drop policy if exists media_select on storage.objects;
drop policy if exists media_update on storage.objects;
create policy media_select on storage.objects for select to authenticated
  using (bucket_id = 'media' and public.is_staff());
create policy media_update on storage.objects for update to authenticated
  using (bucket_id = 'media' and public.is_staff())
  with check (bucket_id = 'media' and public.is_staff());
