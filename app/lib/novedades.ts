import type { Anuncio, Archivo, Tarea } from "@/lib/tipos";

/** Columnas de `announcements` que necesita `armarNovedades`. */
export type AnuncioParaNovedades = Pick<
  Anuncio,
  | "canvas_id"
  | "course_id"
  | "title"
  | "posted_at"
  | "canvas_url"
  | "attachment_ids"
  | "inicial"
>;

/** Lista de columnas para `select()`, en el mismo orden que el Pick de arriba. */
export const COLUMNAS_ANUNCIO_PARA_NOVEDADES =
  "canvas_id, course_id, title, posted_at, canvas_url, attachment_ids, inicial";

/** Columnas de `assignments` que necesita `armarNovedades`. */
export type TareaParaNovedades = Pick<
  Tarea,
  "canvas_id" | "course_id" | "name" | "canvas_url" | "inicial" | "first_seen_at"
>;

/** Lista de columnas para `select()`, en el mismo orden que el Pick de arriba. */
export const COLUMNAS_TAREA_PARA_NOVEDADES =
  "canvas_id, course_id, name, canvas_url, inicial, first_seen_at";

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
 * ramo, no son novedades) y las que quedaron fuera de `desde`, y ordena de
 * mas nuevo a mas viejo.
 *
 * Un archivo que es adjunto de un anuncio aparece colgado de ese anuncio
 * (`adjuntos`) en vez de como novedad suelta, pero solo cuando ese anuncio
 * tambien pasa los filtros (no `inicial`, fecha dentro de `desde`): un
 * adjunto de un anuncio que quedo fuera de la ventana se muestra suelto.
 */
export function armarNovedades(
  anuncios: AnuncioParaNovedades[],
  tareas: TareaParaNovedades[],
  archivos: Archivo[],
  desde: Date,
): Novedad[] {
  const anunciosEnVentana = anuncios.filter(
    (a) => !a.inicial && new Date(a.posted_at) >= desde,
  );
  const tareasEnVentana = tareas.filter(
    (t) => !t.inicial && new Date(t.first_seen_at) >= desde,
  );
  const archivosEnVentana = archivos.filter(
    (f) => !f.inicial && new Date(f.first_seen_at) >= desde,
  );

  // Solo los anuncios que efectivamente van a aparecer como novedad pueden
  // "esconder" sus adjuntos; si el anuncio quedo fuera por `inicial` o por
  // `desde`, sus adjuntos se muestran como archivos sueltos.
  const idsAdjuntos = new Set<number>();
  for (const anuncio of anunciosEnVentana) {
    for (const id of anuncio.attachment_ids) {
      idsAdjuntos.add(id);
    }
  }

  // El detalle del archivo adjunto (nombre, enlace) se busca entre todos los
  // archivos no `inicial`, sin exigirles estar en la ventana: el anuncio que
  // los referencia puede ser reciente aunque el archivo en si sea viejo.
  const archivosPorId = new Map<number, Archivo>();
  for (const archivo of archivos.filter((f) => !f.inicial)) {
    archivosPorId.set(archivo.canvas_id, archivo);
  }

  const novedades: Novedad[] = [];

  for (const anuncio of anunciosEnVentana) {
    const adjuntos = anuncio.attachment_ids
      .map((id) => archivosPorId.get(id))
      .filter((archivo): archivo is Archivo => archivo !== undefined);

    novedades.push({
      tipo: "anuncio",
      id: anuncio.canvas_id,
      courseId: anuncio.course_id,
      titulo: anuncio.title,
      fecha: anuncio.posted_at,
      href: `/anuncio/${anuncio.canvas_id}`,
      adjuntos,
    });
  }

  for (const tarea of tareasEnVentana) {
    novedades.push({
      tipo: "tarea",
      id: tarea.canvas_id,
      courseId: tarea.course_id,
      titulo: tarea.name,
      fecha: tarea.first_seen_at,
      href: `/tarea/${tarea.canvas_id}`,
    });
  }

  for (const archivo of archivosEnVentana) {
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

  return novedades.sort(
    (a, b) => new Date(b.fecha).getTime() - new Date(a.fecha).getTime(),
  );
}
