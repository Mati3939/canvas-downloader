import Link from "next/link";
import type { Novedad as TipoNovedad } from "@/lib/novedades";
import { tiempoRelativo } from "@/lib/fechas";

const ETIQUETA_TIPO: Record<TipoNovedad["tipo"], string> = {
  anuncio: "Anuncio",
  tarea: "Tarea",
  archivo: "Archivo",
};

/**
 * Una fila de "lo nuevo": tipo + ramo, titulo con enlace (a Canvas o a
 * Drive, segun resolvio `armarNovedades`), fecha relativa y, si tiene,
 * los adjuntos del anuncio.
 */
export function Novedad({
  novedad,
  nombreRamo,
  ahora,
}: {
  novedad: TipoNovedad;
  nombreRamo: string;
  ahora: Date;
}) {
  return (
    <li className="flex flex-col gap-1 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          {ETIQUETA_TIPO[novedad.tipo]} · {nombreRamo}
        </span>
        <span className="shrink-0 text-xs text-zinc-400 dark:text-zinc-500">
          {tiempoRelativo(novedad.fecha, ahora)}
        </span>
      </div>
      {novedad.href.startsWith("/") ? (
        <Link
          href={novedad.href}
          className="text-sm font-medium text-zinc-900 underline-offset-2 hover:underline dark:text-zinc-50"
        >
          {novedad.titulo}
        </Link>
      ) : (
        <a
          href={novedad.href}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-medium text-zinc-900 underline-offset-2 hover:underline dark:text-zinc-50"
        >
          {novedad.titulo}
        </a>
      )}
      {novedad.adjuntos && novedad.adjuntos.length > 0 ? (
        <ul className="mt-1 flex flex-col gap-1">
          {novedad.adjuntos.map((adjunto) => (
            <li key={adjunto.canvas_id}>
              <a
                href={adjunto.drive_url ?? adjunto.canvas_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-400"
              >
                Adjunto: {adjunto.name}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}
