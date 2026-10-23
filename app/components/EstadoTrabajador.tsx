import type { CorridaTrabajador } from "@/lib/tipos";
import { fechaHoraSantiago, horasDesde, tiempoRelativo } from "@/lib/fechas";

const LIMITE_HORAS_AVISO = 6;

/**
 * Pie de la pagina de inicio: cuando se sincronizo por ultima vez el
 * trabajador del PC. Si pasaron mas de `LIMITE_HORAS_AVISO` horas desde la
 * ultima corrida terminada, muestra un aviso.
 */
export function EstadoTrabajador({
  corrida,
  ahora,
}: {
  corrida: CorridaTrabajador | null;
  ahora: Date;
}) {
  if (!corrida || !corrida.finished_at) {
    return (
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        Todavia no hay una sincronizacion registrada.
      </p>
    );
  }

  const horas = horasDesde(corrida.finished_at, ahora);

  return (
    <div className="flex flex-col gap-1 text-xs text-zinc-500 dark:text-zinc-400">
      <p>Actualizado {tiempoRelativo(corrida.finished_at, ahora)}</p>
      {horas > LIMITE_HORAS_AVISO ? (
        <p className="font-medium text-amber-600 dark:text-amber-400">
          El PC no ha sincronizado desde {fechaHoraSantiago(corrida.finished_at)}.
        </p>
      ) : null}
    </div>
  );
}
