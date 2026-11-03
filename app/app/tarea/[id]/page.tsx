import { notFound } from "next/navigation";
import { ContenidoCanvas } from "@/components/ContenidoCanvas";
import { EnlaceVolver } from "@/components/EnlaceVolver";
import { ListaAdjuntos } from "@/components/ListaAdjuntos";
import { MensajeError } from "@/components/MensajeError";
import { prepararContenido } from "@/lib/detalle";
import { fechaLarga, tiempoRelativo } from "@/lib/fechas";
import { createClient } from "@/lib/supabase/server";
import type { Tarea } from "@/lib/tipos";

const MENSAJE_ERROR = "No se pudo cargar la tarea. Intenta de nuevo mas tarde.";

export default async function PaginaTarea({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const tareaId = Number(id);
  if (!Number.isInteger(tareaId) || id.trim() === "") notFound();

  const supabase = await createClient();
  const tareaRes = await supabase
    .from("assignments")
    .select("canvas_id, course_id, name, description_html, canvas_due_at, unlock_at, canvas_url")
    .eq("canvas_id", tareaId)
    .maybeSingle();
  if (tareaRes.error) {
    console.error("Error de Supabase cargando la tarea:", tareaRes.error.message);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }
  if (!tareaRes.data) notFound();
  const tarea = tareaRes.data as Pick<
    Tarea,
    "canvas_id" | "course_id" | "name" | "description_html" | "canvas_due_at" | "unlock_at" | "canvas_url"
  >;

  const cursoRes = await supabase
    .from("courses")
    .select("name, canvas_url")
    .eq("canvas_id", tarea.course_id)
    .maybeSingle();
  if (cursoRes.error) {
    console.error("Error de Supabase cargando el ramo de la tarea:", cursoRes.error.message);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }
  const curso = cursoRes.data as { name: string; canvas_url: string } | null;
  const baseCanvas = new URL(curso?.canvas_url ?? tarea.canvas_url).origin;

  const contenido = await prepararContenido(supabase, tarea.description_html, baseCanvas, []);
  if (contenido.error) {
    console.error("Error de Supabase cargando archivos de la tarea:", contenido.error);
    return <MensajeError mensaje={MENSAJE_ERROR} />;
  }

  const ahora = new Date();
  const vencida = tarea.canvas_due_at ? new Date(tarea.canvas_due_at) < ahora : false;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-5 bg-zinc-50 px-4 py-6 dark:bg-black">
      <EnlaceVolver
        href={`/ramo/${tarea.course_id}?tab=tareas`}
        texto={curso?.name ?? "Ramo"}
      />
      <header className="flex flex-col gap-1">
        <span className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          Tarea
        </span>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          {tarea.name || "Sin titulo"}
        </h1>
        <p className="text-sm text-zinc-700 dark:text-zinc-300">
          {tarea.canvas_due_at ? (
            <>
              Entrega: {fechaLarga(tarea.canvas_due_at)}{" "}
              <span className={vencida ? "text-zinc-500" : "font-medium text-emerald-700 dark:text-emerald-400"}>
                ({tiempoRelativo(tarea.canvas_due_at, ahora)})
              </span>
            </>
          ) : (
            "Sin fecha de entrega en Canvas"
          )}
        </p>
      </header>
      <article className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <ContenidoCanvas html={contenido.html} />
      </article>
      <ListaAdjuntos archivos={contenido.adjuntos} />
      <a
        href={tarea.canvas_url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-400"
      >
        Ver en Canvas
      </a>
    </main>
  );
}
