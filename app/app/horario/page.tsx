import Link from "next/link";
import { Encabezado } from "@/components/Encabezado";
import { FilaEvento } from "@/components/FilaEvento";
import { MensajeError } from "@/components/MensajeError";
import { colorRamo } from "@/lib/colores";
import {
  agruparPorDia,
  claveDia,
  COLUMNAS_EVENTO,
  lunesDeLaSemana,
  nombreDia,
  ramoDeEvento,
  sumarDias,
  type EventoResumen,
} from "@/lib/horario";
import { createClient } from "@/lib/supabase/server";
import type { Curso } from "@/lib/tipos";

const MENSAJE_ERROR =
  "No se pudo cargar tu horario. Intenta de nuevo mas tarde.";
const SEMANAS_MAX = 5;
const DIAS = 6; // lunes a sabado

export default async function PaginaHorario({
  searchParams,
}: {
  searchParams: Promise<{ semana?: string }>;
}) {
  const { semana } = await searchParams;
  const desplazamiento = Math.min(
    Math.max(Number.parseInt(semana ?? "0", 10) || 0, -1),
    SEMANAS_MAX,
  );

  const ahora = new Date();
  const lunes = sumarDias(lunesDeLaSemana(ahora), desplazamiento * 7);
  const dias = Array.from({ length: DIAS }, (_, i) => sumarDias(lunes, i));
  // Margen de un dia a cada lado: el filtro fino se hace por dia local.
  const desde = new Date(`${sumarDias(lunes, -1)}T00:00:00Z`).toISOString();
  const hasta = new Date(`${sumarDias(lunes, 8)}T00:00:00Z`).toISOString();

  const supabase = await createClient();
  const [eventosRes, cursosRes] = await Promise.all([
    supabase
      .from("calendar_events")
      .select(COLUMNAS_EVENTO)
      .gte("start_at", desde)
      .lt("start_at", hasta),
    supabase.from("courses").select("canvas_id, name, position"),
  ]);
  const error = eventosRes.error ?? cursosRes.error;
  if (error) {
    console.error("Error de Supabase cargando el horario:", error.message);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  const eventos = (eventosRes.data ?? []) as EventoResumen[];
  const cursos = (cursosRes.data ?? []) as Pick<
    Curso,
    "canvas_id" | "name" | "position"
  >[];
  const porDia = agruparPorDia(eventos);
  const hoy = claveDia(ahora);
  const colorDe = (titulo: string) => {
    const curso = ramoDeEvento(titulo, cursos);
    return curso ? colorRamo(curso) : undefined;
  };
  const sinEventos = dias.every((d) => !porDia.get(d)?.length);

  const titulo =
    desplazamiento === 0
      ? "Esta semana"
      : desplazamiento === 1
        ? "Proxima semana"
        : desplazamiento === -1
          ? "Semana pasada"
          : `Semana del ${nombreDia(lunes)}`;

  const boton =
    "rounded-full border border-borde bg-superficie px-3 py-1.5 text-xs font-medium text-texto transition-colors hover:bg-superficie-2";

  return (
    <>
      <Encabezado />
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6 lg:px-8 lg:py-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-texto lg:text-2xl">
              {titulo}
            </h1>
            <p className="text-xs text-texto-2 capitalize">
              {nombreDia(dias[0])} – {nombreDia(dias[DIAS - 1])}
            </p>
          </div>
          <div className="flex gap-2">
            {desplazamiento > -1 ? (
              <Link href={`?semana=${desplazamiento - 1}`} className={boton}>
                ← Anterior
              </Link>
            ) : null}
            {desplazamiento !== 0 ? (
              <Link href="?" className={boton}>
                Hoy
              </Link>
            ) : null}
            {desplazamiento < SEMANAS_MAX ? (
              <Link href={`?semana=${desplazamiento + 1}`} className={boton}>
                Siguiente →
              </Link>
            ) : null}
          </div>
        </header>

        {sinEventos ? (
          <p className="rounded-xl border border-dashed border-borde px-4 py-3 text-sm text-texto-2">
            No hay clases ni evaluaciones esta semana en tu Google Calendar. Si
            esperabas verlas, revisa que el PC haya sincronizado y que Google
            este autorizado con permiso de Calendar.
          </p>
        ) : null}

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {dias.map((dia) => {
            const delDia = porDia.get(dia) ?? [];
            if (delDia.length === 0 && dia !== hoy) return null;
            return (
              <section key={dia} className="flex flex-col gap-2">
                <h2
                  className={`text-sm font-semibold capitalize ${
                    dia === hoy ? "text-acento" : "text-texto"
                  }`}
                >
                  {nombreDia(dia)}
                  {dia === hoy ? " · hoy" : ""}
                </h2>
                {delDia.length === 0 ? (
                  <p className="text-sm text-texto-2">Sin clases.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {delDia.map((e) => (
                      <FilaEvento
                        key={e.google_id}
                        evento={e}
                        colorRamo={colorDe(e.title)}
                        ahora={ahora}
                      />
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      </main>
    </>
  );
}
