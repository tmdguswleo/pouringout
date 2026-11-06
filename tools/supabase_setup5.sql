-- 5단계: 알림 받기 기기 등록(pushsubs)·사용 중 표시(presence)는 본인 것만 읽고 씀, 사장은 모두 읽음 (SQL Editor에 붙여 넣고 Run)
drop policy if exists store_read on public.store;
drop policy if exists store_write on public.store;
drop policy if exists store_update on public.store;
drop policy if exists store_delete on public.store;
create policy store_read on public.store for select to authenticated
  using (public.is_staff() and (col not in ('presence','pushsubs') or public.is_boss()
         or (col = 'presence' and id = public.my_key()) or (col = 'pushsubs' and id like public.my_key() || '\_%')));
create policy store_write on public.store for insert to authenticated
  with check (public.is_staff() and (col <> 'presence' or id = public.my_key())
              and (col <> 'pushsubs' or id like public.my_key() || '\_%'));
create policy store_update on public.store for update to authenticated
  using (public.is_staff() and (col not in ('presence','pushsubs') or id = public.my_key() or id like public.my_key() || '\_%' or public.is_boss()))
  with check (public.is_staff() and (col <> 'presence' or id = public.my_key())
              and (col <> 'pushsubs' or id like public.my_key() || '\_%'));
create policy store_delete on public.store for delete to authenticated
  using (public.is_staff() and col <> 'presence' and (col <> 'pushsubs' or id like public.my_key() || '\_%' or public.is_boss()));
