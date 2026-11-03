import type { Archivo, ItemModulo, Modulo } from "@/lib/tipos";
import { enlacePrincipal } from "@/lib/material";

export type ModuloResumen = Pick<Modulo, "canvas_id" | "name" | "position">;
export type ItemModuloResumen = Pick<
  ItemModulo,
  | "canvas_id"
  | "module_id"
  | "position"
  | "title"
  | "type"
  | "file_id"
  | "external_url"
  | "canvas_url"
>;

function enlaceItem(
  item: ItemModuloResumen,
  archivosPorId: Map<number, Archivo>,
): string | null {
  if (item.file_id !== null) {
    const archivo = archivosPorId.get(item.file_id);
    if (archivo) {
      return enlacePrincipal(archivo).href;
    }
  }
  if (item.type === "ExternalUrl" && item.external_url) {
    return item.external_url;
  }
  return item.canvas_url ?? null;
}

/**
 * Modulos del ramo en su orden original, con sus items. Un item de tipo
 * archivo enlaza igual que en Material; paginas y otros tipos enlazan a
 * Canvas; los enlaces externos abren su URL.
 */
export function ListaModulos({
  modulos,
  items,
  archivosPorId,
}: {
  modulos: ModuloResumen[];
  items: ItemModuloResumen[];
  archivosPorId: Map<number, Archivo>;
}) {
  if (modulos.length === 0) {
    return (
      <p className="text-sm text-texto-2">
        Este ramo todavia no tiene modulos.
      </p>
    );
  }

  return (
    <ul className="columns-1 gap-3 lg:columns-2">
      {modulos.map((modulo) => {
        const itemsDelModulo = items
          .filter((item) => item.module_id === modulo.canvas_id)
          .sort((a, b) => a.position - b.position);

        return (
          <li
            key={modulo.canvas_id}
            className="mb-3 break-inside-avoid rounded-xl border border-borde bg-superficie p-4"
          >
            <details open>
              <summary className="cursor-pointer text-sm font-semibold text-texto">
                {modulo.name}
              </summary>
              <ul className="mt-2 flex flex-col gap-1.5 pl-1">
                {itemsDelModulo.map((item) => {
                  const href = enlaceItem(item, archivosPorId);
                  return (
                    <li key={item.canvas_id} className="text-sm">
                      {href ? (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-texto-2 underline-offset-2 hover:text-texto hover:underline"
                        >
                          {item.title}
                        </a>
                      ) : (
                        <span className="text-texto-3">{item.title}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </details>
          </li>
        );
      })}
    </ul>
  );
}
