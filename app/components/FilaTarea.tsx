import Link from "next/link";
import { fechaEntrega, tiempoRelativo } from "@/lib/fechas";
import type { TareaResumen } from "@/lib/tareas";

/** Fila de tarea: nombre, (ramo) y fecha de entrega. */
export function FilaTarea({
  tarea,
  ahora,
  nombreRamo,
}: {
  tarea: TareaResumen;
  ahora: Date;
  nombreRamo?: string;
}) {
  const vencida = tarea.canvas_due_at ? new Date(tarea.canvas_due_at) < ahora : false;
  return (
    <li>
      <Link
        href={`/tarea/${tarea.canvas_id}`}
        className="flex items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 transition-colors hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
      >
        <div className="flex min-w-0 flex-col gap-0.5">
          {nombreRamo ? (
            <span className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {nombreRamo}
            </span>
          ) : null}
          <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
            {tarea.name || "Sin titulo"}
          </span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5 text-right">
          {tarea.canvas_due_at ? (
            <>
              <span className={vencida ? "text-xs text-zinc-500 dark:text-zinc-400" : "text-xs font-medium text-zinc-900 dark:text-zinc-50"}>
                {fechaEntrega(tarea.canvas_due_at)}
              </span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                {tiempoRelativo(tarea.canvas_due_at, ahora)}
              </span>
            </>
          ) : (
            <span className="text-xs text-zinc-500 dark:text-zinc-400">Sin fecha</span>
          )}
        </div>
      </Link>
    </li>
  );
}
