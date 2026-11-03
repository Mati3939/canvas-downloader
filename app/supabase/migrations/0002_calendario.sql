-- Eventos de Google Calendar (clases y evaluaciones) publicados por el
-- trabajador. Solo lectura para el usuario dueno de las filas.

create table if not exists public.calendar_events (
  user_id uuid not null references auth.users(id) on delete cascade,
  google_id text not null,
  title text not null,
  location text,
  description text,
  start_at timestamptz not null,
  end_at timestamptz not null,
  all_day boolean not null default false,
  kind text not null check (kind in ('clase', 'evaluacion')),
  html_link text,
  updated_at timestamptz not null default now(),
  primary key (user_id, google_id)
);

create index if not exists calendar_events_user_start_idx
  on public.calendar_events (user_id, start_at);

alter table public.calendar_events enable row level security;

create policy calendar_events_select_own
  on public.calendar_events
  for select
  using (user_id = (select auth.uid()));
