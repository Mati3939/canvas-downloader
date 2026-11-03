import Link from "next/link";
import { PuntoRamo } from "@/components/PuntoRamo";
import { tiempoRelativo } from "@/lib/fechas";
import type { Novedad as TipoNovedad } from "@/lib/novedades";

const TIPO: Record<TipoNovedad["tipo"], { etiqueta: string; clase: string }> = {
  anuncio: { etiqueta: "Anuncio", clase: "bg-acento-suave text-acento" },
  tarea: { etiqueta: "Tarea", clase: "bg-aviso-suave text-aviso" },
  archivo: { etiqueta: "Archivo", clase: "bg-exito-suave text-exito" },
};

/**
 * Una fila de "lo nuevo": tipo, ramo (con su color), titulo con enlace (a la
 * app, a Drive o a Canvas), fecha relativa y, si tiene, los adjuntos del
 * anuncio.
 */
export function Novedad({
  novedad,
  nombreRamo,
  colorRamo,
  ahora,
}: {
  novedad: TipoNovedad;
  nombreRamo: string;
  colorRamo: string;
  ahora: Date;
}) {
  const tipo = TIPO[novedad.tipo];
  const claseTitulo =
    "text-sm font-medium text-texto underline-offset-2 hover:underline";
  return (
    <li className="flex flex-col gap-1.5 rounded-xl border border-borde bg-superficie p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2 text-xs text-texto-2">
          <span
            className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${tipo.clase}`}
          >
            {tipo.etiqueta}
          </span>
          <PuntoRamo color={colorRamo} />
          <span className="truncate">{nombreRamo}</span>
        </span>
        <span className="shrink-0 text-xs text-texto-3">
          {tiempoRelativo(novedad.fecha, ahora)}
        </span>
      </div>
      {novedad.href.startsWith("/") ? (
        <Link href={novedad.href} className={claseTitulo}>
          {novedad.titulo}
        </Link>
      ) : (
        <a
          href={novedad.href}
          target="_blank"
          rel="noreferrer"
          className={claseTitulo}
        >
          {novedad.titulo}
        </a>
      )}
      {novedad.adjuntos && novedad.adjuntos.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {novedad.adjuntos.map((adjunto) => (
            <li key={adjunto.canvas_id}>
              <a
                href={adjunto.drive_url ?? adjunto.canvas_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-acento underline-offset-2 hover:underline"
              >
                📎 {adjunto.name}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}
