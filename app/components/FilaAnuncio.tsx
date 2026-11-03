import Link from "next/link";
import { fechaHoraSantiago } from "@/lib/fechas";

export type AnuncioResumen = {
  canvas_id: number;
  title: string;
  posted_at: string;
  attachment_ids: number[];
};

export const COLUMNAS_ANUNCIO_RESUMEN =
  "canvas_id, title, posted_at, attachment_ids";

/** Fila de anuncio en la lista del ramo. */
export function FilaAnuncio({ anuncio }: { anuncio: AnuncioResumen }) {
  const n = anuncio.attachment_ids.length;
  return (
    <li>
      <Link
        href={`/anuncio/${anuncio.canvas_id}`}
        className="flex flex-col gap-1 rounded-xl border border-borde bg-superficie p-4 transition-colors hover:border-borde-fuerte hover:bg-superficie-2"
      >
        <span className="text-sm font-medium text-texto">
          {anuncio.title || "Sin titulo"}
        </span>
        <span className="text-xs text-texto-2">
          {fechaHoraSantiago(anuncio.posted_at)}
          {n > 0 ? ` · ${n} ${n === 1 ? "adjunto" : "adjuntos"}` : ""}
        </span>
      </Link>
    </li>
  );
}
