import Link from "next/link";
import { Encabezado } from "@/components/Encabezado";
import { EstadoTrabajador } from "@/components/EstadoTrabajador";
import { MensajeError } from "@/components/MensajeError";
import { FilaEvento } from "@/components/FilaEvento";
import { FilaTarea } from "@/components/FilaTarea";
import { Novedad } from "@/components/Novedad";
import { TarjetaRamo } from "@/components/TarjetaRamo";
import { colorRamo } from "@/lib/colores";
import { MS_POR_DIA } from "@/lib/fechas";
import {
  armarNovedades,
  COLUMNAS_ANUNCIO_PARA_NOVEDADES,
  COLUMNAS_TAREA_PARA_NOVEDADES,
  type AnuncioParaNovedades,
  type TareaParaNovedades,
} from "@/lib/novedades";
import {
  claveDia,
  COLUMNAS_EVENTO,
  nombreDia,
  ramoDeEvento,
  type EventoResumen,
} from "@/lib/horario";
import { createClient } from "@/lib/supabase/server";
import {
  COLUMNAS_TAREA_RESUMEN,
  proximasEntregas,
  type TareaResumen,
} from "@/lib/tareas";
import type { Archivo, CorridaTrabajador, Curso } from "@/lib/tipos";

const DIAS_LO_NUEVO = 14;
const DIAS_ENTREGAS = 14;
const MENSAJE_ERROR =
  "No se pudo cargar la informacion de tus ramos. Intenta de nuevo mas tarde.";

export default async function Home() {
  const supabase = await createClient();
  const ahora = new Date();
  const desde = new Date(ahora.getTime() - DIAS_LO_NUEVO * MS_POR_DIA);

  const [
    cursosRes,
    anunciosRes,
    tareasRes,
    archivosRes,
    corridaRes,
    entregasRes,
    eventosRes,
  ] = await Promise.all([
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
      .lte(
        "canvas_due_at",
        new Date(ahora.getTime() + DIAS_ENTREGAS * MS_POR_DIA).toISOString(),
      ),
    supabase
      .from("calendar_events")
      .select(COLUMNAS_EVENTO)
      .gte("start_at", new Date(ahora.getTime() - MS_POR_DIA).toISOString())
      .lte(
        "start_at",
        new Date(ahora.getTime() + DIAS_ENTREGAS * MS_POR_DIA).toISOString(),
      )
      .order("start_at", { ascending: true }),
  ]);

  const error =
    cursosRes.error ??
    anunciosRes.error ??
    tareasRes.error ??
    archivosRes.error ??
    corridaRes.error ??
    entregasRes.error ??
    eventosRes.error;

  if (error) {
    console.error(
      "Error de Supabase cargando la pagina de inicio:",
      error.message,
    );
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  const cursos = (cursosRes.data ?? []) as Curso[];
  const anuncios = (anunciosRes.data ?? []) as AnuncioParaNovedades[];
  const tareas = (tareasRes.data ?? []) as TareaParaNovedades[];
  const archivos = (archivosRes.data ?? []) as Archivo[];
  const corrida = (corridaRes.data ?? null) as CorridaTrabajador | null;

  const novedades = armarNovedades(anuncios, tareas, archivos, desde);
  const nombrePorCurso = new Map(cursos.map((c) => [c.canvas_id, c.name]));
  const colorPorCurso = new Map(cursos.map((c) => [c.canvas_id, colorRamo(c)]));
  const cursosAlumno = new Set(
    cursos.filter((c) => c.role === "student").map((c) => c.canvas_id),
  );
  const entregas = proximasEntregas(
    (entregasRes.data ?? []) as TareaResumen[],
    cursosAlumno,
    ahora,
    DIAS_ENTREGAS,
  );

  const eventos = (eventosRes.data ?? []) as EventoResumen[];
  const hoy = claveDia(ahora);
  const eventosHoy = eventos.filter((e) => claveDia(e.start_at) === hoy);
  const evaluaciones = eventos.filter(
    (e) => e.kind === "evaluacion" && new Date(e.end_at) > ahora,
  );
  const colorDeEvento = (titulo: string) => {
    const curso = ramoDeEvento(titulo, cursos);
    return curso ? colorRamo(curso) : undefined;
  };
  const pendientes = [
    ...entregas.map((t) => ({
      clave: `t-${t.canvas_id}`,
      fecha: t.canvas_due_at as string,
      nodo: (
        <FilaTarea
          key={`t-${t.canvas_id}`}
          tarea={t}
          ahora={ahora}
          nombreRamo={nombrePorCurso.get(t.course_id) ?? "Ramo"}
          colorRamo={colorPorCurso.get(t.course_id)}
        />
      ),
    })),
    ...evaluaciones.map((e) => ({
      clave: `e-${e.google_id}`,
      fecha: e.start_at,
      nodo: (
        <FilaEvento
          key={`e-${e.google_id}`}
          evento={e}
          colorRamo={colorDeEvento(e.title)}
          ahora={ahora}
          conDia
        />
      ),
    })),
  ].sort((a, b) => new Date(a.fecha).getTime() - new Date(b.fecha).getTime());

  return (
    <>
      <Encabezado />
      <main className="mx-auto grid w-full max-w-6xl flex-1 grid-cols-1 content-start gap-8 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-10 lg:px-8 lg:py-10">
        <section className="flex flex-col gap-3 lg:col-start-1">
          <div className="flex items-baseline justify-between gap-2">
            <h1 className="text-base font-semibold text-texto">
              Hoy{" "}
              <span className="font-normal text-texto-2 capitalize">
                · {nombreDia(hoy)}
              </span>
            </h1>
            <Link
              href="/horario"
              className="text-xs font-medium text-acento hover:underline"
            >
              Ver horario →
            </Link>
          </div>
          {eventosHoy.length === 0 ? (
            <p className="rounded-xl border border-dashed border-borde px-4 py-3 text-sm text-texto-2">
              Hoy no tienes clases ni evaluaciones en tu calendario.
            </p>
          ) : (
            <ul className="grid grid-cols-1 gap-2 xl:grid-cols-2">
              {eventosHoy.map((e) => (
                <FilaEvento
                  key={e.google_id}
                  evento={e}
                  colorRamo={colorDeEvento(e.title)}
                  ahora={ahora}
                />
              ))}
            </ul>
          )}
        </section>

        <section className="flex flex-col gap-3 lg:col-start-1">
          <h2 className="text-base font-semibold text-texto">
            Proximas entregas y evaluaciones
          </h2>
          {pendientes.length === 0 ? (
            <p className="rounded-xl border border-dashed border-borde px-4 py-3 text-sm text-texto-2">
              No hay entregas con fecha ni evaluaciones en los proximos{" "}
              {DIAS_ENTREGAS} dias.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {pendientes.map((p) => p.nodo)}
            </ul>
          )}
        </section>

        <aside className="flex flex-col gap-3 lg:col-start-2 lg:row-span-3 lg:row-start-1">
          <h2 className="text-base font-semibold text-texto">Tus ramos</h2>
          {cursos.length === 0 ? (
            <p className="text-sm text-texto-2">
              Todavia no hay ramos sincronizados.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1">
              {cursos.map((curso) => (
                <TarjetaRamo key={curso.canvas_id} curso={curso} />
              ))}
            </div>
          )}
          <div className="pt-2">
            <EstadoTrabajador corrida={corrida} ahora={ahora} />
          </div>
        </aside>

        <section className="flex flex-col gap-3 lg:col-start-1">
          <h2 className="text-base font-semibold text-texto">Lo nuevo</h2>
          {novedades.length === 0 ? (
            <p className="rounded-xl border border-dashed border-borde px-4 py-3 text-sm text-texto-2">
              No hay nada nuevo en los ultimos {DIAS_LO_NUEVO} dias.
            </p>
          ) : (
            <ul className="grid grid-cols-1 gap-2 xl:grid-cols-2">
              {novedades.map((novedad) => (
                <Novedad
                  key={`${novedad.tipo}-${novedad.id}`}
                  novedad={novedad}
                  nombreRamo={nombrePorCurso.get(novedad.courseId) ?? "Ramo"}
                  colorRamo={colorPorCurso.get(novedad.courseId) ?? "#888"}
                  ahora={ahora}
                />
              ))}
            </ul>
          )}
        </section>
      </main>
    </>
  );
}
