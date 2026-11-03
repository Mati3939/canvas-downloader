/**
 * Paleta de colores de ramos: tonos medios que se leen bien sobre fondo
 * claro y oscuro.
 */
export const PALETA_RAMOS = [
  "#4f7cff",
  "#f08c2e",
  "#2fb380",
  "#a960e8",
  "#e8557f",
  "#16a9bd",
  "#d4a72c",
  "#ef5b5b",
] as const;

/**
 * Color de un ramo: por su posicion en la lista (asi dos ramos seguidos
 * nunca comparten color); si no tiene posicion, por su id.
 */
export function colorRamo(curso: {
  canvas_id: number;
  position: number | null;
}): string {
  const indice = curso.position ?? curso.canvas_id;
  return PALETA_RAMOS[Math.abs(indice) % PALETA_RAMOS.length];
}
