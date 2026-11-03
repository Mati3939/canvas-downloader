import { PuntoRamo } from "@/components/PuntoRamo";
import { claveDia, hora, nombreDia, type EventoResumen } from "@/lib/horario";

/**
 * Un evento del calendario: clase o evaluacion (destacada). Se apila en
 * vertical (hora y etiqueta arriba, titulo y sala abajo) para que se lea
 * bien tanto en listas anchas como en columnas angostas del horario.
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
  const horario = evento.all_day
    ? "Todo el dia"
    : `${hora(evento.start_at)}–${hora(evento.end_at)}`;

  const contenido = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-xs text-texto-2 tabular-nums">
          {conDia ? (
            <span className="font-medium text-texto capitalize">
              {nombreDia(claveDia(evento.start_at))} ·{" "}
            </span>
          ) : null}
          {horario}
        </span>
        {esEvaluacion ? (
          <span className="shrink-0 rounded-md bg-aviso-suave px-1.5 py-0.5 text-[11px] font-semibold text-aviso">
            Evaluacion
          </span>
        ) : enCurso ? (
          <span className="shrink-0 rounded-md bg-exito-suave px-1.5 py-0.5 text-[11px] font-semibold text-exito">
            Ahora
          </span>
        ) : null}
      </div>
      <div className="flex items-start gap-2">
        {colorRamo ? (
          <span className="mt-1.5">
            <PuntoRamo color={colorRamo} />
          </span>
        ) : null}
        <span
          className={`min-w-0 text-sm leading-snug font-medium break-words ${
            pasado ? "text-texto-2" : "text-texto"
          }`}
        >
          {evento.title || "Sin titulo"}
        </span>
      </div>
      {evento.location ? (
        <span className="text-xs leading-snug text-texto-2">
          {evento.location}
        </span>
      ) : null}
    </>
  );

  const clase = `flex flex-col gap-1.5 rounded-xl border bg-superficie p-3 ${
    esEvaluacion ? "border-aviso/40" : "border-borde"
  }`;
  return (
    <li className="min-w-0">
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
