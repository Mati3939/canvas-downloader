/**
 * Enlace equivalente que abre la app Canvas Student en iOS
 * (`canvas-courses://<host>/<ruta>`), o null si la URL no es de Canvas.
 */
export function enlaceAppCanvas(href: string): string | null {
  let url: URL;
  try {
    url = new URL(href);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" || !url.hostname.endsWith(".instructure.com")) {
    return null;
  }
  return `canvas-courses://${url.host}${url.pathname}${url.search}`;
}

/** iPhone, iPod o iPad (iPadOS se presenta como Mac con pantalla tactil). */
export function esIOS(userAgent: string, puntosTactiles: number): boolean {
  return (
    /iPhone|iPad|iPod/.test(userAgent) ||
    (/Macintosh/.test(userAgent) && puntosTactiles > 1)
  );
}
