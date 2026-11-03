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
      <p className="text-xs text-texto-2">
        Todavia no hay una sincronizacion registrada.
      </p>
    );
  }

  const horas = horasDesde(corrida.finished_at, ahora);

  return (
    <div className="flex flex-col gap-1 text-xs text-texto-2">
      <p>Actualizado {tiempoRelativo(corrida.finished_at, ahora)}</p>
      {corrida.ok === false ? (
        <p className="font-medium text-aviso">
          La ultima sincronizacion tuvo errores.
        </p>
      ) : null}
      {horas > LIMITE_HORAS_AVISO ? (
        <p className="font-medium text-aviso">
          El PC no ha sincronizado desde{" "}
          {fechaHoraSantiago(corrida.finished_at)}.
        </p>
      ) : null}
    </div>
  );
}
