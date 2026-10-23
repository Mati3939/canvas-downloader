import type { Archivo } from "@/lib/tipos";
import { enlacePrincipal, formatearTamano } from "@/lib/material";

/**
 * Una fila de archivo en Material: nombre, origen, tamano, enlace
 * principal (Drive o Canvas) y, si el principal es Drive, el enlace
 * secundario a Canvas.
 */
export function FilaArchivo({ archivo }: { archivo: Archivo }) {
  const enlace = enlacePrincipal(archivo);

  return (
    <li className="flex items-center justify-between gap-3 border-b border-zinc-100 py-2 last:border-0 dark:border-zinc-800">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">
          {archivo.name}
        </span>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          {archivo.source_label} · {formatearTamano(archivo.size)}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <a
          href={enlace.href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-zinc-900 underline-offset-2 hover:underline dark:text-zinc-50"
        >
          {enlace.tipo === "drive" ? "Drive" : "Canvas"}
        </a>
        {enlace.tipo === "drive" ? (
          <a
            href={archivo.canvas_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-400"
          >
            Canvas
          </a>
        ) : null}
      </div>
    </li>
  );
}
