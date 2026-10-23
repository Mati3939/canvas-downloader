// Tipos de fila que reflejan las tablas de
// `app/supabase/migrations/0001_etapa1.sql`. Los nombres de columna se
// mantienen igual que en SQL (snake_case) para que un cambio de esquema sea
// facil de rastrear hasta aqui.

export type Curso = {
  user_id: string;
  canvas_id: number;
  name: string;
  role: "student" | "ta";
  canvas_url: string;
  drive_url: string | null;
  position: number | null;
  initial_published_at: string | null;
  updated_at: string;
};

export type Anuncio = {
  user_id: string;
  canvas_id: number;
  course_id: number;
  title: string;
  message_html: string;
  posted_at: string;
  canvas_url: string;
  attachment_ids: number[];
  inicial: boolean;
  first_seen_at: string;
};

export type Tarea = {
  user_id: string;
  canvas_id: number;
  course_id: number;
  name: string;
  description_html: string;
  canvas_due_at: string | null;
  unlock_at: string | null;
  canvas_created_at: string;
  canvas_url: string;
  inicial: boolean;
  first_seen_at: string;
};

export type Archivo = {
  user_id: string;
  canvas_id: number;
  course_id: number;
  name: string;
  size: number;
  modified_at: string;
  source: "modulos" | "anuncios" | "archivos" | "tareas" | "mensajes";
  source_label: string;
  drive_url: string | null;
  canvas_url: string;
  inicial: boolean;
  first_seen_at: string;
};

export type Modulo = {
  user_id: string;
  canvas_id: number;
  course_id: number;
  name: string;
  position: number;
  unlock_at: string | null;
};

export type ItemModulo = {
  user_id: string;
  canvas_id: number;
  course_id: number;
  module_id: number;
  position: number;
  title: string;
  type: string;
  file_id: number | null;
  external_url: string | null;
  canvas_url: string | null;
};

export type CorridaTrabajador = {
  id: number;
  user_id: string;
  started_at: string;
  finished_at: string | null;
  ok: boolean | null;
  summary: Record<string, unknown>;
};
