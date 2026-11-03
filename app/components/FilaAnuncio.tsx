import Link from "next/link";
import { fechaHoraSantiago } from "@/lib/fechas";

export type AnuncioResumen = {
  canvas_id: number;
  title: string;
  posted_at: string;
  attachment_ids: number[];
};

export const COLUMNAS_ANUNCIO_RESUMEN = "canvas_id, title, posted_at, attachment_ids";

/** Fila de anuncio en la lista del ramo. */
export function FilaAnuncio({ anuncio }: { anuncio: AnuncioResumen }) {
  const n = anuncio.attachment_ids.length;
  return (
    <li>
      <Link
        href={`/anuncio/${anuncio.canvas_id}`}
        className="flex flex-col gap-1 rounded-xl border border-zinc-200 bg-white p-4 transition-colors hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
      >
        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
          {anuncio.title || "Sin titulo"}
        </span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          {fechaHoraSantiago(anuncio.posted_at)}
          {n > 0 ? ` · ${n} ${n === 1 ? "adjunto" : "adjuntos"}` : ""}
        </span>
      </Link>
    </li>
  );
}
