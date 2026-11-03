import { PuntoRamo } from "@/components/PuntoRamo";
import { hora, nombreDia, claveDia, type EventoResumen } from "@/lib/horario";

/**
 * Un evento del calendario: clase (hora, titulo, sala) o evaluacion
 * (destacada). Con `conDia`, muestra tambien el dia.
 */
export function FilaEvento({
  evento,
  colorRamo,
  ahora,
  conDia = false,
}: {
  evento: EventoResumen;
  colorRamo?: string;
  ahora: Date;
  conDia?: boolean;
}) {
  const esEvaluacion = evento.kind === "evaluacion";
  const enCurso =
    new Date(evento.start_at) <= ahora && ahora < new Date(evento.end_at);
  const pasado = new Date(evento.end_at) <= ahora;
  const contenido = (
    <>
      <div className="flex w-24 shrink-0 flex-col text-xs">
        {conDia ? (
          <span className="font-medium text-texto capitalize">
            {nombreDia(claveDia(evento.start_at))}
          </span>
        ) : null}
        <span className="text-texto-2 tabular-nums">
          {evento.all_day
            ? "Todo el dia"
            : `${hora(evento.start_at)}–${hora(evento.end_at)}`}
        </span>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-2">
          {colorRamo ? <PuntoRamo color={colorRamo} /> : null}
          <span
            className={`text-sm font-medium ${pasado ? "text-texto-2" : "text-texto"}`}
          >
            {evento.title || "Sin titulo"}
          </span>
        </span>
        {evento.location ? (
          <span className="truncate text-xs text-texto-2">
            {evento.location}
          </span>
        ) : null}
      </div>
      {esEvaluacion ? (
        <span className="shrink-0 self-start rounded-md bg-aviso-suave px-1.5 py-0.5 text-[11px] font-semibold text-aviso">
          Evaluacion
        </span>
      ) : enCurso ? (
        <span className="shrink-0 self-start rounded-md bg-exito-suave px-1.5 py-0.5 text-[11px] font-semibold text-exito">
          Ahora
        </span>
      ) : null}
    </>
  );
  const clase = `flex items-start gap-3 rounded-xl border bg-superficie p-3 ${
    esEvaluacion ? "border-aviso/40" : "border-borde"
  }`;
  return (
    <li>
      {evento.html_link ? (
        <a
          href={evento.html_link}
          target="_blank"
          rel="noopener noreferrer"
          className={`${clase} transition-colors hover:bg-superficie-2`}
        >
          {contenido}
        </a>
      ) : (
        <div className={clase}>{contenido}</div>
      )}
    </li>
  );
}
