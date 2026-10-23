/**
 * Pantalla completa para cuando una consulta a Supabase falla: muestra un
 * error en vez de dejar un estado vacio que se confundiria con "no hay
 * nada". `mensaje` deja personalizar el texto segun la pagina.
 */
export function MensajeError({
  mensaje = "No se pudo cargar la informacion. Intenta de nuevo mas tarde.",
}: {
  mensaje?: string;
}) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-2 bg-zinc-50 px-6 text-center dark:bg-black">
      <p className="text-sm text-red-600 dark:text-red-400">{mensaje}</p>
    </main>
  );
}
