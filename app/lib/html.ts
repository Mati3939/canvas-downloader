import sanitizeHtml, { type Transformer } from "sanitize-html";

/** Lo minimo de un archivo que hace falta para reescribir un enlace. */
export type ArchivoEnlazable = { drive_url: string | null; canvas_url: string };

const PATRON_ARCHIVO = /\/files\/(\d+)/;

/**
 * Ids de archivos de Canvas que aparecen en enlaces o imagenes del HTML
 * (`.../files/123...`), para poder buscar sus enlaces de Drive.
 */
export function idsArchivosEnHtml(html: string): number[] {
  const ids = new Set<number>();
  for (const m of html.matchAll(/\/files\/(\d+)/g)) {
    ids.add(Number(m[1]));
  }
  return [...ids];
}

function resolverUrl(valor: string | undefined, base: string): URL | null {
  if (!valor) return null;
  try {
    const url = new URL(valor, base);
    return url.protocol === "http:" ||
      url.protocol === "https:" ||
      url.protocol === "mailto:"
      ? url
      : null;
  } catch {
    return null;
  }
}

/**
 * El destino de un enlace: si apunta a un archivo de Canvas que ya esta en
 * Drive, el enlace de Drive; si no, la URL absoluta original.
 */
function destino(
  url: URL,
  baseCanvas: string,
  archivos: Map<number, ArchivoEnlazable>,
): string {
  if (url.host === new URL(baseCanvas).host) {
    const m = url.pathname.match(PATRON_ARCHIVO);
    const archivo = m ? archivos.get(Number(m[1])) : undefined;
    if (archivo?.drive_url) return archivo.drive_url;
  }
  return url.toString();
}

/**
 * Limpia el HTML de un anuncio o tarea de Canvas para mostrarlo dentro de la
 * app: deja solo etiquetas de formato, abre los enlaces en otra pestana,
 * cambia los enlaces a archivos por su copia en Drive cuando existe y
 * reemplaza las imagenes de Canvas (que exigen sesion) por un enlace.
 */
export function limpiarHtmlCanvas(
  html: string,
  baseCanvas: string,
  archivos: Map<number, ArchivoEnlazable>,
): string {
  return sanitizeHtml(html, {
    allowedTags: [
      "p",
      "br",
      "hr",
      "div",
      "span",
      "strong",
      "b",
      "em",
      "i",
      "u",
      "s",
      "sub",
      "sup",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "ul",
      "ol",
      "li",
      "blockquote",
      "pre",
      "code",
      "a",
      "img",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
    ],
    allowedAttributes: {
      a: ["href", "target", "rel"],
      img: ["src", "alt"],
      td: ["colspan", "rowspan"],
      th: ["colspan", "rowspan"],
    },
    allowedSchemes: ["http", "https", "mailto"],
    transformTags: {
      a: ((_tag, attribs) => {
        const url = resolverUrl(attribs.href, baseCanvas);
        if (!url) return { tagName: "span", attribs: {} };
        return {
          tagName: "a",
          attribs: {
            href: destino(url, baseCanvas, archivos),
            target: "_blank",
            rel: "noopener noreferrer",
          },
        };
      }) as Transformer,
      img: ((_tag, attribs) => {
        const url = resolverUrl(attribs.src, baseCanvas);
        if (!url) return { tagName: "span", attribs: {} };
        const esDeCanvas = url.host === new URL(baseCanvas).host;
        if (!esDeCanvas) {
          return {
            tagName: "img",
            attribs: { src: url.toString(), alt: attribs.alt ?? "" },
          };
        }
        return {
          tagName: "a",
          attribs: {
            href: destino(url, baseCanvas, archivos),
            target: "_blank",
            rel: "noopener noreferrer",
          },
          text: attribs.alt ? `[Imagen: ${attribs.alt}]` : "[Imagen]",
        };
      }) as Transformer,
    },
  });
}
