import { EstadoTrabajador } from "@/components/EstadoTrabajador";
import { Novedad } from "@/components/Novedad";
import { TarjetaRamo } from "@/components/TarjetaRamo";
import { armarNovedades } from "@/lib/novedades";
import { createClient } from "@/lib/supabase/server";
import type {
  Anuncio,
  Archivo,
  CorridaTrabajador,
  Curso,
  Tarea,
} from "@/lib/tipos";

const DIAS_LO_NUEVO = 14;
const MS_POR_DIA = 24 * 60 * 60 * 1000;

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
      supabase.from("announcements").select("*").eq("inicial", false),
      supabase.from("assignments").select("*").eq("inicial", false),
      supabase.from("files").select("*").eq("inicial", false),
      supabase
        .from("worker_runs")
        .select("*")
        .not("finished_at", "is", null)
        .order("finished_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
    ]);

  const cursos = (cursosRes.data ?? []) as Curso[];
  const anuncios = (anunciosRes.data ?? []) as Anuncio[];
  const tareas = (tareasRes.data ?? []) as Tarea[];
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
