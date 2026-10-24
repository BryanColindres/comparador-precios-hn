-- Precios HN: datos compartidos por hogar (se pega una vez en Supabase > SQL Editor).
-- Cada hogar se identifica con un código largo e imposible de adivinar que genera la app.
-- La tabla no se puede leer ni escribir directo desde internet: solo por las dos funciones de abajo.

create table if not exists public.precios_datos (
  hogar       text   not null check (char_length(hogar) between 16 and 64),
  perfil      text   not null check (char_length(perfil) between 1 and 40),
  datos       jsonb  not null,
  version     bigint not null default 1,
  actualizado timestamptz not null default now(),
  primary key (hogar, perfil)
);

alter table public.precios_datos enable row level security;
-- Sin políticas a propósito: anon y authenticated no tocan la tabla directamente.
revoke all on public.precios_datos from anon, authenticated;

-- Leer todos los perfiles de un hogar.
create or replace function public.precios_leer(p_hogar text)
returns table (perfil text, datos jsonb, version bigint, actualizado timestamptz)
language sql security definer set search_path = public as $$
  select d.perfil, d.datos, d.version, d.actualizado
  from public.precios_datos d
  where d.hogar = p_hogar and char_length(p_hogar) >= 16;
$$;

-- Guardar un perfil. p_version es la versión que la app tenía al leer:
-- si otro celular guardó antes, devuelve 'conflicto' y la app mezcla y reintenta.
create or replace function public.precios_guardar(p_hogar text, p_perfil text, p_datos jsonb, p_version bigint)
returns text
language plpgsql security definer set search_path = public as $$
declare actual bigint;
begin
  if char_length(p_hogar) < 16 or char_length(p_perfil) not between 1 and 40 then
    return 'invalido';
  end if;
  if pg_column_size(p_datos) > 1000000 then
    return 'muy_grande';
  end if;
  select version into actual from public.precios_datos where hogar = p_hogar and perfil = p_perfil for update;
  if not found then
    insert into public.precios_datos (hogar, perfil, datos) values (p_hogar, p_perfil, p_datos);
    return 'ok:1';
  end if;
  if p_version is distinct from actual then
    return 'conflicto:' || actual;
  end if;
  update public.precios_datos
     set datos = p_datos, version = actual + 1, actualizado = now()
   where hogar = p_hogar and perfil = p_perfil;
  return 'ok:' || (actual + 1);
end $$;

revoke all on function public.precios_leer(text) from public;
revoke all on function public.precios_guardar(text, text, jsonb, bigint) from public;
grant execute on function public.precios_leer(text) to anon, authenticated;
grant execute on function public.precios_guardar(text, text, jsonb, bigint) to anon, authenticated;
