import type { Archivo } from "@/lib/tipos";

export type EnlaceArchivo = { href: string; tipo: "drive" | "canvas" };

/**
 * El enlace principal de un archivo: Drive si ya se subio ahi, si no Canvas.
 */
export function enlacePrincipal(archivo: Archivo): EnlaceArchivo {
  if (archivo.drive_url) {
    return { href: archivo.drive_url, tipo: "drive" };
  }
  return { href: archivo.canvas_url, tipo: "canvas" };
}

export type GrupoMaterial = {
  source: Archivo["source"];
  etiqueta: string;
  archivos: Archivo[];
};

const ORDEN_SOURCE: Archivo["source"][] = [
  "anuncios",
  "modulos",
  "archivos",
  "tareas",
  "mensajes",
];

/**
 * Agrupa los archivos de un ramo por `source_label` (la etiqueta que se
 * muestra, p.ej. el nombre del modulo), manteniendo el `source` de cada
 * grupo. Los grupos se ordenan por `source` (anuncios, modulos, archivos,
 * tareas, mensajes) y, dentro del mismo `source`, por etiqueta. Los
 * archivos dentro de cada grupo quedan de mas nuevo a mas viejo.
 */
export function agruparMaterial(archivos: Archivo[]): GrupoMaterial[] {
  const grupos = new Map<string, GrupoMaterial>();

  for (const archivo of archivos) {
    const clave = `${archivo.source}::${archivo.source_label}`;
    let grupo = grupos.get(clave);
    if (!grupo) {
      grupo = {
        source: archivo.source,
        etiqueta: archivo.source_label,
        archivos: [],
      };
      grupos.set(clave, grupo);
    }
    grupo.archivos.push(archivo);
  }

  for (const grupo of grupos.values()) {
    grupo.archivos.sort(
      (a, b) =>
        new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime(),
    );
  }

  return Array.from(grupos.values()).sort((a, b) => {
    const ordenA = ORDEN_SOURCE.indexOf(a.source);
    const ordenB = ORDEN_SOURCE.indexOf(b.source);
    if (ordenA !== ordenB) {
      return ordenA - ordenB;
    }
    return a.etiqueta.localeCompare(b.etiqueta, "es");
  });
}

const UNIDADES_TAMANO = ["B", "KB", "MB", "GB"];

/**
 * Tamano de archivo en espanol, p.ej. "1,2 MB". Sin decimales en bytes.
 */
export function formatearTamano(bytes: number): string {
  let valor = bytes;
  let i = 0;
  while (valor >= 1024 && i < UNIDADES_TAMANO.length - 1) {
    valor /= 1024;
    i++;
  }
  const texto =
    i === 0 ? String(Math.round(valor)) : valor.toFixed(1).replace(".", ",");
  return `${texto} ${UNIDADES_TAMANO[i]}`;
}
