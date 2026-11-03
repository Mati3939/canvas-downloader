import { EstadoTrabajador } from "@/components/EstadoTrabajador";
import { MensajeError } from "@/components/MensajeError";
import { FilaTarea } from "@/components/FilaTarea";
import { Novedad } from "@/components/Novedad";
import { TarjetaRamo } from "@/components/TarjetaRamo";
import { MS_POR_DIA } from "@/lib/fechas";
import {
  armarNovedades,
  COLUMNAS_ANUNCIO_PARA_NOVEDADES,
  COLUMNAS_TAREA_PARA_NOVEDADES,
  type AnuncioParaNovedades,
  type TareaParaNovedades,
} from "@/lib/novedades";
import { createClient } from "@/lib/supabase/server";
import {
  COLUMNAS_TAREA_RESUMEN,
  proximasEntregas,
  type TareaResumen,
} from "@/lib/tareas";
import type { Archivo, CorridaTrabajador, Curso } from "@/lib/tipos";

const DIAS_LO_NUEVO = 14;
const DIAS_ENTREGAS = 7;
const MENSAJE_ERROR =
  "No se pudo cargar la informacion de tus ramos. Intenta de nuevo mas tarde.";

export default async function Home() {
  const supabase = await createClient();
  const ahora = new Date();
  const desde = new Date(ahora.getTime() - DIAS_LO_NUEVO * MS_POR_DIA);

  const [cursosRes, anunciosRes, tareasRes, archivosRes, corridaRes, entregasRes] =
    await Promise.all([
      supabase
        .from("courses")
        .select("*")
        .order("position", { ascending: true, nullsFirst: false })
        .order("name", { ascending: true }),
      supabase
        .from("announcements")
        .select(COLUMNAS_ANUNCIO_PARA_NOVEDADES)
        .eq("inicial", false),
      supabase
        .from("assignments")
        .select(COLUMNAS_TAREA_PARA_NOVEDADES)
        .eq("inicial", false),
      supabase.from("files").select("*").eq("inicial", false),
      supabase
        .from("worker_runs")
        .select("*")
        .not("finished_at", "is", null)
        .order("finished_at", { ascending: false })
        .limit(1)
        .maybeSingle(),
      supabase
        .from("assignments")
        .select(COLUMNAS_TAREA_RESUMEN)
        .gte("canvas_due_at", ahora.toISOString())
        .lte("canvas_due_at", new Date(ahora.getTime() + DIAS_ENTREGAS * MS_POR_DIA).toISOString()),
    ]);

  const error =
    cursosRes.error ??
    anunciosRes.error ??
    tareasRes.error ??
    archivosRes.error ??
    corridaRes.error ??
    entregasRes.error;

  if (error) {
    console.error("Error de Supabase cargando la pagina de inicio:", error.message);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  const cursos = (cursosRes.data ?? []) as Curso[];
  const anuncios = (anunciosRes.data ?? []) as AnuncioParaNovedades[];
  const tareas = (tareasRes.data ?? []) as TareaParaNovedades[];
  const archivos = (archivosRes.data ?? []) as Archivo[];
  const corrida = (corridaRes.data ?? null) as CorridaTrabajador | null;

  const novedades = armarNovedades(anuncios, tareas, archivos, desde);
  const nombrePorCurso = new Map(cursos.map((c) => [c.canvas_id, c.name]));
  const cursosAlumno = new Set(
    cursos.filter((c) => c.role === "student").map((c) => c.canvas_id),
  );
  const entregas = proximasEntregas(
    (entregasRes.data ?? []) as TareaResumen[],
    cursosAlumno,
    ahora,
    DIAS_ENTREGAS,
  );

  return (
    <main className="flex flex-1 flex-col gap-8 bg-zinc-50 px-4 py-6 dark:bg-black">
      <section className="flex flex-col gap-3">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Proximas entregas
        </h1>
        {entregas.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            No hay entregas con fecha en Canvas en los proximos {DIAS_ENTREGAS} dias.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {entregas.map((tarea) => (
              <FilaTarea
                key={tarea.canvas_id}
                tarea={tarea}
                ahora={ahora}
                nombreRamo={nombrePorCurso.get(tarea.course_id) ?? "Ramo"}
              />
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Lo nuevo
        </h2>
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
