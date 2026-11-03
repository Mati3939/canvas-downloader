/**
 * HTML de un anuncio o tarea ya pasado por `limpiarHtmlCanvas`.
 */
export function ContenidoCanvas({ html }: { html: string }) {
  if (!html.trim()) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">Sin texto.</p>
    );
  }
  return (
    <div
      className="contenido-canvas text-sm leading-6 text-zinc-800 dark:text-zinc-200"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
