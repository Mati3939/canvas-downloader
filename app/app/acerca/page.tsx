import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Acerca de Better Canvas",
};

export default function AcercaPage() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 bg-zinc-50 px-6 py-12 text-zinc-800 dark:bg-black dark:text-zinc-200">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
        Better Canvas
      </h1>
      <p className="text-sm leading-6">
        Better Canvas es una aplicacion web personal que resume el contenido de
        los cursos de Canvas LMS: anuncios recientes con sus adjuntos, archivos
        nuevos, tareas y la estructura de modulos de cada curso, con enlaces
        directos a cada archivo en Google Drive y en Canvas.
      </p>
      <p className="text-sm leading-6">
        Se instala como app en el telefono y solo muestra datos de la cuenta
        con la que se inicia sesion. Nunca modifica nada en Canvas.
      </p>
      <div className="flex flex-col gap-3 text-sm">
        <Link
          href="/login"
          className="font-medium text-blue-600 underline dark:text-blue-400"
        >
          Entrar
        </Link>
        <Link
          href="/privacidad"
          className="text-blue-600 underline dark:text-blue-400"
        >
          Politica de privacidad
        </Link>
      </div>
    </main>
  );
}
