const ZONA = "America/Santiago";

export const MS_POR_DIA = 24 * 60 * 60 * 1000;

const UNIDADES: { limite: number; div: number; unidad: Intl.RelativeTimeFormatUnit }[] = [
  { limite: 60, div: 1, unidad: "second" },
  { limite: 3600, div: 60, unidad: "minute" },
  { limite: 86400, div: 3600, unidad: "hour" },
  { limite: 604800, div: 86400, unidad: "day" },
  { limite: 2629800, div: 604800, unidad: "week" },
  { limite: Infinity, div: 2629800, unidad: "month" },
];

/**
 * "hace X" en espanol (Intl.RelativeTimeFormat), p.ej. "hace 2 horas".
 */
export function tiempoRelativo(
  fecha: string | Date,
  ahora: Date = new Date(),
): string {
  const formateador = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
  const segundos = (new Date(fecha).getTime() - ahora.getTime()) / 1000;
  const entrada =
    UNIDADES.find((u) => Math.abs(segundos) < u.limite) ??
    UNIDADES[UNIDADES.length - 1];
  const valor = Math.round(segundos / entrada.div);
  return formateador.format(valor, entrada.unidad);
}

/**
 * Fecha y hora absolutas en la zona de visualizacion (America/Santiago),
 * p.ej. "23 oct, 14:32".
 */
export function fechaHoraSantiago(fecha: string | Date): string {
  return new Intl.DateTimeFormat("es-CL", {
    timeZone: ZONA,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(fecha));
}

export function horasDesde(
  fecha: string | Date,
  ahora: Date = new Date(),
): number {
  return (ahora.getTime() - new Date(fecha).getTime()) / 3_600_000;
}
