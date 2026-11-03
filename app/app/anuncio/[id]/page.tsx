import { notFound } from "next/navigation";
import { ContenidoCanvas } from "@/components/ContenidoCanvas";
import { EnlaceVolver } from "@/components/EnlaceVolver";
import { ListaAdjuntos } from "@/components/ListaAdjuntos";
import { MensajeError } from "@/components/MensajeError";
import { prepararContenido } from "@/lib/detalle";
import { fechaLarga } from "@/lib/fechas";
import { createClient } from "@/lib/supabase/server";
import type { Anuncio } from "@/lib/tipos";

const MENSAJE_ERROR = "No se pudo cargar el anuncio. Intenta de nuevo mas tarde.";

export default async function PaginaAnuncio({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const anuncioId = Number(id);
  if (!Number.isInteger(anuncioId) || id.trim() === "") notFound();

  const supabase = await createClient();
  const anuncioRes = await supabase
    .from("announcements")
    .select("canvas_id, course_id, title, message_html, posted_at, canvas_url, attachment_ids")
    .eq("canvas_id", anuncioId)
    .maybeSingle();
  if (anuncioRes.error) {
    console.error("Error de Supabase cargando el anuncio:", anuncioRes.error.message);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }
  if (!anuncioRes.data) notFound();
  const anuncio = anuncioRes.data as Pick<
    Anuncio,
    "canvas_id" | "course_id" | "title" | "message_html" | "posted_at" | "canvas_url" | "attachment_ids"
  >;

  const cursoRes = await supabase
    .from("courses")
    .select("name, canvas_url")
    .eq("canvas_id", anuncio.course_id)
    .maybeSingle();
  if (cursoRes.error) {
    console.error("Error de Supabase cargando el ramo del anuncio:", cursoRes.error.message);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }
  const curso = cursoRes.data as { name: string; canvas_url: string } | null;
  const baseCanvas = new URL(curso?.canvas_url ?? anuncio.canvas_url).origin;

  const contenido = await prepararContenido(
    supabase,
    anuncio.message_html,
    baseCanvas,
    anuncio.attachment_ids,
  );
  if (contenido.error) {
    console.error("Error de Supabase cargando adjuntos del anuncio:", contenido.error);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 bg-zinc-50 px-4 py-6 dark:bg-black">
      <EnlaceVolver
        href={`/ramo/${anuncio.course_id}?tab=anuncios`}
        texto={curso?.name ?? "Ramo"}
      />
      <header className="flex flex-col gap-1">
        <span className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Anuncio
        </span>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          {anuncio.title || "Sin titulo"}
        </h1>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          {fechaLarga(anuncio.posted_at)}
        </p>
      </header>
      <article className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <ContenidoCanvas html={contenido.html} />
      </article>
      <ListaAdjuntos archivos={contenido.adjuntos} />
      <a
        href={anuncio.canvas_url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-400"
      >
        Ver en Canvas
      </a>
    </main>
  );
}
