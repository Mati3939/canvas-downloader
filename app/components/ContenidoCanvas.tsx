/**
 * HTML de un anuncio o tarea ya pasado por `limpiarHtmlCanvas`.
 */
export function ContenidoCanvas({ html }: { html: string }) {
  if (!html.trim()) {
    return <p className="text-sm text-texto-2">Sin texto.</p>;
  }
  return (
    <div
      className="contenido-canvas text-sm leading-6 text-texto"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
