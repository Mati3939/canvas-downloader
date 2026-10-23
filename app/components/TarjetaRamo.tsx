import Link from "next/link";
import type { Curso } from "@/lib/tipos";

/**
 * Tarjeta de un ramo en el inicio. Enlaza a la vista del ramo dentro de la
 * app; marca los ramos donde el rol es ayudante.
 */
export function TarjetaRamo({ curso }: { curso: Curso }) {
  return (
    <Link
      href={`/ramo/${curso.canvas_id}`}
      className="flex items-center justify-between gap-2 rounded-xl border border-zinc-200 bg-white p-4 transition-colors hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
    >
      <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
        {curso.name}
      </span>
      {curso.role === "ta" ? (
        <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
          Ayudante
        </span>
      ) : null}
    </Link>
  );
}
