import { MS_POR_DIA } from "./fechas";
import type { Tarea } from "./tipos";

export type TareaResumen = Pick<
  Tarea,
  "canvas_id" | "course_id" | "name" | "canvas_due_at" | "canvas_url"
>;

export const COLUMNAS_TAREA_RESUMEN =
  "canvas_id, course_id, name, canvas_due_at, canvas_url";

export type TareasOrdenadas<T> = { proximas: T[]; sinFecha: T[]; pasadas: T[] };

/**
 * Separa las tareas de un ramo en proximas (de la mas cercana a la mas
 * lejana), sin fecha y pasadas (de la mas reciente a la mas antigua).
 */
export function ordenarTareas<T extends Pick<TareaResumen, "canvas_due_at" | "name">>(
  tareas: T[],
  ahora: Date,
): TareasOrdenadas<T> {
  const proximas: T[] = [];
  const sinFecha: T[] = [];
  const pasadas: T[] = [];
  for (const t of tareas) {
    if (!t.canvas_due_at) sinFecha.push(t);
    else if (new Date(t.canvas_due_at) >= ahora) proximas.push(t);
    else pasadas.push(t);
  }
  const ms = (t: T) => new Date(t.canvas_due_at as string).getTime();
  proximas.sort((a, b) => ms(a) - ms(b));
  pasadas.sort((a, b) => ms(b) - ms(a));
  sinFecha.sort((a, b) => a.name.localeCompare(b.name, "es"));
  return { proximas, sinFecha, pasadas };
}

/**
 * Tareas con entrega entre ahora y `dias` dias mas, solo de los ramos
 * indicados (los ramos donde se es alumno), de la mas cercana a la mas
 * lejana.
 */
export function proximasEntregas<T extends TareaResumen>(
  tareas: T[],
  cursosAlumno: Set<number>,
  ahora: Date,
  dias: number,
): T[] {
  const hasta = ahora.getTime() + dias * MS_POR_DIA;
  return tareas
    .filter((t) => {
      if (!t.canvas_due_at || !cursosAlumno.has(t.course_id)) return false;
      const ms = new Date(t.canvas_due_at).getTime();
      return ms >= ahora.getTime() && ms <= hasta;
    })
    .sort(
      (a, b) =>
        new Date(a.canvas_due_at as string).getTime() -
        new Date(b.canvas_due_at as string).getTime(),
    );
}
