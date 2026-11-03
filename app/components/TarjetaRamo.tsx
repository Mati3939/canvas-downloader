import Link from "next/link";
import { colorRamo } from "@/lib/colores";
import type { Curso } from "@/lib/tipos";

/**
 * Tarjeta de un ramo en el inicio, con su color. Enlaza a la vista del ramo
 * dentro de la app; marca los ramos donde el rol es ayudante.
 */
export function TarjetaRamo({ curso }: { curso: Curso }) {
  return (
    <Link
      href={`/ramo/${curso.canvas_id}`}
      className="group flex items-center justify-between gap-2 overflow-hidden rounded-xl border border-borde bg-superficie py-3 pr-4 pl-0 transition-colors hover:border-borde-fuerte hover:bg-superficie-2"
    >
      <span className="flex min-w-0 items-center gap-3">
        <span
          aria-hidden
          className="h-8 w-1 shrink-0 rounded-r-full"
          style={{ backgroundColor: colorRamo(curso) }}
        />
        <span className="truncate text-sm font-medium text-texto">
          {curso.name}
        </span>
      </span>
      {curso.role === "ta" ? (
        <span className="shrink-0 rounded-full bg-aviso-suave px-2 py-0.5 text-xs font-medium text-aviso">
          Ayudante
        </span>
      ) : (
        <span
          aria-hidden
          className="text-texto-3 transition-transform group-hover:translate-x-0.5"
        >
          ›
        </span>
      )}
    </Link>
  );
}
