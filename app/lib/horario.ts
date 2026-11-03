import type { EventoCalendario } from "./tipos";

const ZONA = "America/Santiago";

export type EventoResumen = Pick<
  EventoCalendario,
  | "google_id"
  | "title"
  | "location"
  | "start_at"
  | "end_at"
  | "all_day"
  | "kind"
  | "html_link"
>;

export const COLUMNAS_EVENTO =
  "google_id, title, location, start_at, end_at, all_day, kind, html_link";

/** Fecha local en Santiago como "AAAA-MM-DD". */
export function claveDia(fecha: string | Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: ZONA,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(fecha));
}

/** Suma `dias` a una clave "AAAA-MM-DD" (aritmetica de calendario). */
export function sumarDias(clave: string, dias: number): string {
  const [a, m, d] = clave.split("-").map(Number);
  const f = new Date(Date.UTC(a, m - 1, d + dias, 12));
  return f.toISOString().slice(0, 10);
}

/** Clave del lunes de la semana (en Santiago) que contiene `fecha`. */
export function lunesDeLaSemana(fecha: Date): string {
  const clave = claveDia(fecha);
  const [a, m, d] = clave.split("-").map(Number);
  const diaSemana = new Date(Date.UTC(a, m - 1, d, 12)).getUTCDay(); // 0 = domingo
  return sumarDias(clave, -((diaSemana + 6) % 7));
}

/** Agrupa eventos por dia local, ordenados por hora de inicio. */
export function agruparPorDia<T extends Pick<EventoResumen, "start_at">>(
  eventos: T[],
): Map<string, T[]> {
  const grupos = new Map<string, T[]>();
  const ordenados = [...eventos].sort(
    (a, b) => new Date(a.start_at).getTime() - new Date(b.start_at).getTime(),
  );
  for (const e of ordenados) {
    const clave = claveDia(e.start_at);
    grupos.set(clave, [...(grupos.get(clave) ?? []), e]);
  }
  return grupos;
}

/** Hora local "HH:MM". */
export function hora(fecha: string | Date): string {
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: ZONA,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(fecha));
}

/** "lunes 3 nov" para una clave de dia. */
export function nombreDia(clave: string): string {
  const [a, m, d] = clave.split("-").map(Number);
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: "UTC",
    weekday: "long",
    day: "numeric",
    month: "short",
  }).format(new Date(Date.UTC(a, m - 1, d, 12)));
}

const PALABRAS_GENERICAS = new Set([
  "taller",
  "curso",
  "seminario",
  "introduccion",
]);

function raices(texto: string): string[] {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((p) => p.length >= 4 && !PALABRAS_GENERICAS.has(p))
    .map((p) => p.slice(0, 4));
}

/**
 * El ramo al que corresponde un evento, si todas las palabras importantes
 * del nombre del ramo aparecen en el titulo (comparando sus primeras
 * cuatro letras, sin tildes). Si hay varios, el de nombre mas especifico.
 */
export function ramoDeEvento<C extends { canvas_id: number; name: string }>(
  titulo: string,
  cursos: C[],
): C | null {
  const enTitulo = new Set(raices(titulo));
  let mejor: { curso: C; n: number } | null = null;
  for (const curso of cursos) {
    const delRamo = raices(curso.name);
    if (delRamo.length === 0) continue;
    if (
      delRamo.every((r) => enTitulo.has(r)) &&
      (!mejor || delRamo.length > mejor.n)
    ) {
      mejor = { curso, n: delRamo.length };
    }
  }
  return mejor?.curso ?? null;
}
