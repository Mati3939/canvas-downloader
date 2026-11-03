"use client";

import { useEffect } from "react";
import { enlaceAppCanvas, esIOS } from "@/lib/canvasApp";

const ESPERA_RESPALDO_MS = 1500;

/**
 * En iOS, los enlaces a Canvas abren la app Canvas Student (con la sesion
 * ya iniciada) en vez de Safari. Si la app no responde, despues de un
 * momento se abre el enlace web como respaldo. En otros sistemas no hace
 * nada.
 */
export function AbrirEnAppCanvas() {
  useEffect(() => {
    if (!esIOS(navigator.userAgent, navigator.maxTouchPoints)) return;

    function alHacerClick(evento: MouseEvent) {
      if (evento.defaultPrevented || evento.button !== 0) return;
      const enlace = (evento.target as Element | null)?.closest?.("a[href]");
      if (!(enlace instanceof HTMLAnchorElement)) return;
      const app = enlaceAppCanvas(enlace.href);
      if (!app) return;

      evento.preventDefault();
      const web = enlace.href;
      let salio = false;
      const alOcultar = () => {
        if (document.visibilityState === "hidden") salio = true;
      };
      document.addEventListener("visibilitychange", alOcultar);
      window.setTimeout(() => {
        document.removeEventListener("visibilitychange", alOcultar);
        if (!salio && document.visibilityState === "visible") {
          window.open(web, "_blank", "noopener");
        }
      }, ESPERA_RESPALDO_MS);
      window.location.href = app;
    }

    document.addEventListener("click", alHacerClick);
    return () => document.removeEventListener("click", alHacerClick);
  }, []);

  return null;
}
