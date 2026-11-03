import { notFound } from "next/navigation";
import { ContenidoCanvas } from "@/components/ContenidoCanvas";
import { Encabezado } from "@/components/Encabezado";
import { EnlaceVolver } from "@/components/EnlaceVolver";
import { ListaAdjuntos } from "@/components/ListaAdjuntos";
import { MensajeError } from "@/components/MensajeError";
import { prepararContenido } from "@/lib/detalle";
import { fechaLarga } from "@/lib/fechas";
import { createClient } from "@/lib/supabase/server";
import type { Anuncio } from "@/lib/tipos";

const MENSAJE_ERROR =
  "No se pudo cargar el anuncio. Intenta de nuevo mas tarde.";

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
    .select(
      "canvas_id, course_id, title, message_html, posted_at, canvas_url, attachment_ids",
    )
    .eq("canvas_id", anuncioId)
    .maybeSingle();
  if (anuncioRes.error) {
    console.error(
      "Error de Supabase cargando el anuncio:",
      anuncioRes.error.message,
    );
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }
  if (!anuncioRes.data) notFound();
  const anuncio = anuncioRes.data as Pick<
    Anuncio,
    | "canvas_id"
    | "course_id"
    | "title"
    | "message_html"
    | "posted_at"
    | "canvas_url"
    | "attachment_ids"
  >;

  const cursoRes = await supabase
    .from("courses")
    .select("name, canvas_url")
    .eq("canvas_id", anuncio.course_id)
    .maybeSingle();
  if (cursoRes.error) {
    console.error(
      "Error de Supabase cargando el ramo del anuncio:",
      cursoRes.error.message,
    );
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
    console.error(
      "Error de Supabase cargando adjuntos del anuncio:",
      contenido.error,
    );
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  return (
    <>
      <Encabezado />
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-5 px-4 py-6 lg:py-10">
        <EnlaceVolver
          href={`/ramo/${anuncio.course_id}?tab=anuncios`}
          texto={curso?.name ?? "Ramo"}
        />
        <header className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-texto-2">
            Anuncio
          </span>
          <h1 className="text-xl font-semibold text-texto">
            {anuncio.title || "Sin titulo"}
          </h1>
          <p className="text-xs text-texto-2">
            {fechaLarga(anuncio.posted_at)}
          </p>
        </header>
        <article className="rounded-xl border border-borde bg-superficie p-4">
          <ContenidoCanvas html={contenido.html} />
        </article>
        <ListaAdjuntos archivos={contenido.adjuntos} />
        <a
          href={anuncio.canvas_url}
          target="_blank"
          rel="noopener noreferrer"
          className="self-start rounded-full border border-borde bg-superficie px-3 py-1.5 text-xs font-medium text-texto transition-colors hover:bg-superficie-2"
        >
          Ver en Canvas
        </a>
      </main>
    </>
  );
}
