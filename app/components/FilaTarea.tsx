import Link from "next/link";
import { PuntoRamo } from "@/components/PuntoRamo";
import { fechaEntrega, tiempoRelativo } from "@/lib/fechas";
import type { TareaResumen } from "@/lib/tareas";

/** Fila de tarea: nombre, (ramo) y fecha de entrega. */
export function FilaTarea({
  tarea,
  ahora,
  nombreRamo,
  colorRamo,
}: {
  tarea: TareaResumen;
  ahora: Date;
  nombreRamo?: string;
  colorRamo?: string;
}) {
  const vencida = tarea.canvas_due_at
    ? new Date(tarea.canvas_due_at) < ahora
    : false;
  return (
    <li>
      <Link
        href={`/tarea/${tarea.canvas_id}`}
        className="flex items-center justify-between gap-3 rounded-xl border border-borde bg-superficie p-4 transition-colors hover:border-borde-fuerte hover:bg-superficie-2"
      >
        <div className="flex min-w-0 flex-col gap-0.5">
          {nombreRamo ? (
            <span className="flex items-center gap-2 text-xs text-texto-2">
              {colorRamo ? <PuntoRamo color={colorRamo} /> : null}
              <span className="truncate">{nombreRamo}</span>
            </span>
          ) : null}
          <span className="text-sm font-medium text-texto">
            {tarea.name || "Sin titulo"}
          </span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-0.5 text-right">
          {tarea.canvas_due_at ? (
            <>
              <span
                className={
                  vencida
                    ? "text-xs text-texto-2"
                    : "rounded-md bg-aviso-suave px-1.5 py-0.5 text-xs font-semibold text-aviso"
                }
              >
                {fechaEntrega(tarea.canvas_due_at)}
              </span>
              <span className="text-xs text-texto-2">
                {tiempoRelativo(tarea.canvas_due_at, ahora)}
              </span>
            </>
          ) : (
            <span className="text-xs text-texto-2">Sin fecha</span>
          )}
        </div>
      </Link>
    </li>
  );
}
