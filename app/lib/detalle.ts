import { idsArchivosEnHtml, limpiarHtmlCanvas } from "@/lib/html";
import type { createClient } from "@/lib/supabase/server";
import type { Archivo } from "@/lib/tipos";

type Cliente = Awaited<ReturnType<typeof createClient>>;

/**
 * Carga los archivos que referencia un anuncio o tarea (adjuntos e ids
 * enlazados en su HTML) y devuelve el HTML limpio junto con los adjuntos.
 */
export async function prepararContenido(
  supabase: Cliente,
  html: string,
  baseCanvas: string,
  idsAdjuntos: number[],
): Promise<{ html: string; adjuntos: Archivo[]; error: string | null }> {
  const ids = [...new Set([...idsAdjuntos, ...idsArchivosEnHtml(html)])];
  let archivos: Archivo[] = [];
  if (ids.length > 0) {
    const res = await supabase.from("files").select("*").in("canvas_id", ids);
    if (res.error) return { html: "", adjuntos: [], error: res.error.message };
    archivos = (res.data ?? []) as Archivo[];
  }
  const porId = new Map(archivos.map((a) => [a.canvas_id, a]));
  return {
    html: limpiarHtmlCanvas(html, baseCanvas, porId),
    adjuntos: idsAdjuntos
      .map((id) => porId.get(id))
      .filter((a): a is Archivo => a !== undefined),
    error: null,
  };
}
