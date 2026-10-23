/**
 * Valida el `next` del callback de OAuth: solo rutas internas. Un valor
 * como "https://evil.com" o "//evil.com" redirigiria fuera del sitio.
 */
export function rutaSegura(next: string | null, porDefecto = "/"): string {
  if (!next) return porDefecto;
  if (!next.startsWith("/")) return porDefecto;
  if (next.startsWith("//") || next.startsWith("/\\")) return porDefecto;
  return next;
}
