import { FilaArchivo } from "@/components/FilaArchivo";
import type { Archivo } from "@/lib/tipos";

export function ListaAdjuntos({ archivos }: { archivos: Archivo[] }) {
  if (archivos.length === 0) return null;
  return (
    <section className="flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
        Archivos
      </h2>
      <ul>
        {archivos.map((archivo) => (
          <FilaArchivo key={archivo.canvas_id} archivo={archivo} />
        ))}
      </ul>
    </section>
  );
}
