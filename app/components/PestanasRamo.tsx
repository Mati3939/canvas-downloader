"use client";

import { useState, type ReactNode } from "react";

export type PestanaRamo = {
  valor: string;
  etiqueta: string;
  contenido: ReactNode;
};

/**
 * Pestanas del ramo. Todo el contenido llega ya renderizado desde el
 * servidor; cambiar de pestana es inmediato (no vuelve a pedir datos) y
 * solo actualiza `?tab=` en la URL para que volver atras o recargar
 * mantenga la pestana.
 */
export function PestanasRamo({
  pestanas,
  inicial,
}: {
  pestanas: PestanaRamo[];
  inicial: string;
}) {
  const [activa, setActiva] = useState(inicial);

  function elegir(valor: string) {
    setActiva(valor);
    const url = new URL(window.location.href);
    if (valor === pestanas[0].valor) url.searchParams.delete("tab");
    else url.searchParams.set("tab", valor);
    window.history.replaceState(window.history.state, "", url);
  }

  return (
    <>
      <nav
        role="tablist"
        className="-mx-4 flex gap-1 overflow-x-auto border-b border-borde px-4 lg:mx-0 lg:px-0"
      >
        {pestanas.map((p) => (
          <button
            key={p.valor}
            type="button"
            role="tab"
            aria-selected={p.valor === activa}
            onClick={() => elegir(p.valor)}
            className={
              p.valor === activa
                ? "shrink-0 border-b-2 border-acento px-3 py-2 text-sm font-semibold text-texto"
                : "shrink-0 border-b-2 border-transparent px-3 py-2 text-sm text-texto-2 hover:text-texto"
            }
          >
            {p.etiqueta}
          </button>
        ))}
      </nav>
      {pestanas.map((p) => (
        <div key={p.valor} role="tabpanel" hidden={p.valor !== activa}>
          {p.contenido}
        </div>
      ))}
    </>
  );
}
