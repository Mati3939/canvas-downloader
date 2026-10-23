import type { Anuncio, Archivo, Tarea } from "@/lib/tipos";

export type Novedad = {
  tipo: "anuncio" | "archivo" | "tarea";
  id: number;
  courseId: number;
  titulo: string;
  fecha: string;
  href: string;
  adjuntos?: Archivo[];
};

function hrefArchivo(archivo: Archivo): string {
  return archivo.drive_url ?? archivo.canvas_url;
}

/**
 * Arma la lista de "lo nuevo" a partir de anuncios, tareas y archivos ya
 * publicados. Descarta las filas marcadas `inicial` (la primera foto del
 * ramo, no son novedades), corta en `desde` y ordena de mas nuevo a mas
 * viejo. Un archivo que es adjunto de alguno de los anuncios entregados
 * aparece colgado de ese anuncio (`adjuntos`) en vez de como novedad suelta.
 */
export function armarNovedades(
  anuncios: Anuncio[],
  tareas: Tarea[],
  archivos: Archivo[],
  desde: Date,
): Novedad[] {
  const anunciosVigentes = anuncios.filter((a) => !a.inicial);
  const tareasVigentes = tareas.filter((t) => !t.inicial);
  const archivosVigentes = archivos.filter((f) => !f.inicial);

  const idsAdjuntos = new Set<number>();
  for (const anuncio of anunciosVigentes) {
    for (const id of anuncio.attachment_ids) {
      idsAdjuntos.add(id);
    }
  }

  const archivosPorId = new Map<number, Archivo>();
  for (const archivo of archivosVigentes) {
    archivosPorId.set(archivo.canvas_id, archivo);
  }

  const novedades: Novedad[] = [];

  for (const anuncio of anunciosVigentes) {
    const adjuntos = anuncio.attachment_ids
      .map((id) => archivosPorId.get(id))
      .filter((archivo): archivo is Archivo => archivo !== undefined);

    novedades.push({
      tipo: "anuncio",
      id: anuncio.canvas_id,
      courseId: anuncio.course_id,
      titulo: anuncio.title,
      fecha: anuncio.posted_at,
      href: anuncio.canvas_url,
      adjuntos,
    });
  }

  for (const tarea of tareasVigentes) {
    novedades.push({
      tipo: "tarea",
      id: tarea.canvas_id,
      courseId: tarea.course_id,
      titulo: tarea.name,
      fecha: tarea.first_seen_at,
      href: tarea.canvas_url,
    });
  }

  for (const archivo of archivosVigentes) {
    if (idsAdjuntos.has(archivo.canvas_id)) {
      continue;
    }
    novedades.push({
      tipo: "archivo",
      id: archivo.canvas_id,
      courseId: archivo.course_id,
      titulo: archivo.name,
      fecha: archivo.first_seen_at,
      href: hrefArchivo(archivo),
    });
  }

  return novedades
    .filter((n) => new Date(n.fecha) >= desde)
    .sort((a, b) => new Date(b.fecha).getTime() - new Date(a.fecha).getTime());
}
