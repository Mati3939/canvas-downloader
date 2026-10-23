-- Esquema inicial de Better Canvas (etapa 1).
-- Convencion: todas las tablas tienen user_id (duenio de los datos en Canvas),
-- RLS habilitado y una policy de solo lectura para el propio usuario.
-- La escritura la hace unicamente el trabajador, con la service key (sin policy).

-- ---------------------------------------------------------------- courses

create table if not exists public.courses (
  user_id uuid not null references auth.users(id) on delete cascade,
  canvas_id bigint not null,
  name text not null,
  role text not null check (role in ('student', 'ta')),
  canvas_url text not null,
  drive_url text,
  position integer,
  initial_published_at timestamptz,
  updated_at timestamptz not null default now(),
  primary key (user_id, canvas_id)
);

alter table public.courses enable row level security;

create policy courses_select_own
  on public.courses
  for select
  using (user_id = auth.uid());

-- ---------------------------------------------------------------- announcements

create table if not exists public.announcements (
  user_id uuid not null references auth.users(id) on delete cascade,
  canvas_id bigint not null,
  course_id bigint not null,
  title text not null,
  message_html text not null,
  posted_at timestamptz not null,
  canvas_url text not null,
  attachment_ids bigint[] not null default '{}',
  inicial boolean not null default false,
  first_seen_at timestamptz not null default now(),
  primary key (user_id, canvas_id)
);

create index if not exists announcements_user_course_idx
  on public.announcements (user_id, course_id);

alter table public.announcements enable row level security;

create policy announcements_select_own
  on public.announcements
  for select
  using (user_id = auth.uid());

-- ---------------------------------------------------------------- assignments

create table if not exists public.assignments (
  user_id uuid not null references auth.users(id) on delete cascade,
  canvas_id bigint not null,
  course_id bigint not null,
  name text not null,
  description_html text not null,
  canvas_due_at timestamptz,
  unlock_at timestamptz,
  canvas_created_at timestamptz not null,
  canvas_url text not null,
  inicial boolean not null default false,
  first_seen_at timestamptz not null default now(),
  primary key (user_id, canvas_id)
);

create index if not exists assignments_user_course_idx
  on public.assignments (user_id, course_id);

alter table public.assignments enable row level security;

create policy assignments_select_own
  on public.assignments
  for select
  using (user_id = auth.uid());

-- ---------------------------------------------------------------- modules

create table if not exists public.modules (
  user_id uuid not null references auth.users(id) on delete cascade,
  canvas_id bigint not null,
  course_id bigint not null,
  name text not null,
  position integer not null,
  unlock_at timestamptz,
  primary key (user_id, canvas_id)
);

create index if not exists modules_user_course_idx
  on public.modules (user_id, course_id);

alter table public.modules enable row level security;

create policy modules_select_own
  on public.modules
  for select
  using (user_id = auth.uid());

-- ---------------------------------------------------------------- module_items

create table if not exists public.module_items (
  user_id uuid not null references auth.users(id) on delete cascade,
  canvas_id bigint not null,
  course_id bigint not null,
  module_id bigint not null,
  position integer not null,
  title text not null,
  type text not null,
  file_id bigint,
  external_url text,
  canvas_url text,
  primary key (user_id, canvas_id)
);

create index if not exists module_items_user_course_idx
  on public.module_items (user_id, course_id);

alter table public.module_items enable row level security;

create policy module_items_select_own
  on public.module_items
  for select
  using (user_id = auth.uid());

-- ---------------------------------------------------------------- files

create table if not exists public.files (
  user_id uuid not null references auth.users(id) on delete cascade,
  canvas_id bigint not null,
  course_id bigint not null,
  name text not null,
  size bigint not null,
  modified_at timestamptz not null,
  source text not null check (source in ('modulos', 'anuncios', 'archivos', 'tareas', 'mensajes')),
  source_label text not null,
  drive_url text,
  canvas_url text not null,
  inicial boolean not null default false,
  first_seen_at timestamptz not null default now(),
  primary key (user_id, canvas_id)
);

create index if not exists files_user_course_idx
  on public.files (user_id, course_id);

alter table public.files enable row level security;

create policy files_select_own
  on public.files
  for select
  using (user_id = auth.uid());

-- ---------------------------------------------------------------- worker_runs

create table if not exists public.worker_runs (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  started_at timestamptz not null,
  finished_at timestamptz,
  ok boolean,
  summary jsonb not null default '{}'
);

create index if not exists worker_runs_user_id_idx
  on public.worker_runs (user_id);

alter table public.worker_runs enable row level security;

create policy worker_runs_select_own
  on public.worker_runs
  for select
  using (user_id = auth.uid());
