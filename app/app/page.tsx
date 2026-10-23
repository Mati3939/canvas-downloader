import { EstadoTrabajador } from "@/components/EstadoTrabajador";
import { Novedad } from "@/components/Novedad";
import { TarjetaRamo } from "@/components/TarjetaRamo";
import {
  armarNovedades,
  type AnuncioParaNovedades,
  type TareaParaNovedades,
} from "@/lib/novedades";
import { createClient } from "@/lib/supabase/server";
import type { Archivo, CorridaTrabajador, Curso } from "@/lib/tipos";

const DIAS_LO_NUEVO = 14;
const MS_POR_DIA = 24 * 60 * 60 * 1000;

const COLUMNAS_ANUNCIOS =
  "canvas_id, course_id, title, posted_at, canvas_url, attachment_ids, inicial";
const COLUMNAS_TAREAS =
  "canvas_id, course_id, name, canvas_url, inicial, first_seen_at";

function MensajeError() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-2 bg-zinc-50 px-6 text-center dark:bg-black">
      <p className="text-sm text-red-600 dark:text-red-400">
        No se pudo cargar la informacion de tus ramos. Intenta de nuevo mas
        tarde.
      </p>
    </main>
  );
}

export default async function Home() {
  const supabase = await createClient();
  const ahora = new Date();
  const desde = new Date(ahora.getTime() - DIAS_LO_NUEVO * MS_POR_DIA);

  const [cursosRes, anunciosRes, tareasRes, archivosRes, corridaRes] =
    await Promise.all([
      supabase
        .from("courses")
        .select("*")
        .order("position", { ascending: true, nullsFirst: false })
        .order("name", { ascending: true }),
      supabase
        .from("announcements")
        .select(COLUMNAS_ANUNCIOS)
        .eq("inicial", false),
      supabase.from("assignments").select(COLUMNAS_TAREAS).eq("inicial", false),
      supabase.from("files").select("*").eq("inicial", false),
      supabase
        .from("worker_runs")
        .select("*")
        .not("finished_at", "is", null)
        .order("finished_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
    ]);

  const error =
    cursosRes.error ??
    anunciosRes.error ??
    tareasRes.error ??
    archivosRes.error ??
    corridaRes.error;

  if (error) {
    return <MensajeError />;
  }

  const cursos = (cursosRes.data ?? []) as Curso[];
  const anuncios = (anunciosRes.data ?? []) as AnuncioParaNovedades[];
  const tareas = (tareasRes.data ?? []) as TareaParaNovedades[];
  const archivos = (archivosRes.data ?? []) as Archivo[];
  const corrida = (corridaRes.data ?? null) as CorridaTrabajador | null;

  const novedades = armarNovedades(anuncios, tareas, archivos, desde);
  const nombrePorCurso = new Map(cursos.map((c) => [c.canvas_id, c.name]));

  return (
    <main className="flex flex-1 flex-col gap-8 bg-zinc-50 px-4 py-6 dark:bg-black">
      <section className="flex flex-col gap-3">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Lo nuevo
        </h1>
        {novedades.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            No hay nada nuevo en los ultimos {DIAS_LO_NUEVO} dias.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {novedades.map((novedad) => (
              <Novedad
                key={`${novedad.tipo}-${novedad.id}`}
                novedad={novedad}
                nombreRamo={nombrePorCurso.get(novedad.courseId) ?? "Ramo"}
                ahora={ahora}
              />
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Tus ramos
        </h2>
        {cursos.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Todavia no hay ramos sincronizados.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {cursos.map((curso) => (
              <TarjetaRamo key={curso.canvas_id} curso={curso} />
            ))}
          </div>
        )}
      </section>

      <footer className="mt-auto pt-4">
        <EstadoTrabajador corrida={corrida} ahora={ahora} />
      </footer>
    </main>
  );
}
