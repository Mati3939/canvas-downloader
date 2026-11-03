import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacidad - Better Canvas",
};

export default function PrivacidadPage() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-5 bg-fondo px-6 py-12 text-sm leading-6 text-texto">
      <h1 className="text-2xl font-semibold text-texto">
        Politica de privacidad
      </h1>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold text-texto">Que datos usa</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            Tu cuenta de Google (nombre, correo e identificador) para iniciar
            sesion.
          </li>
          <li>
            Contenido de tus cursos de Canvas (anuncios, tareas, modulos y
            nombres de archivos), que se obtiene con tu propio token de Canvas y
            solo en modo lectura.
          </li>
          <li>
            Metadatos de archivos de tu Google Drive (nombre, carpeta y enlace),
            solo para enlazar cada archivo del curso con su copia en Drive. No
            se lee ni se modifica el contenido de tus archivos.
          </li>
        </ul>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold text-texto">Como se guardan</h2>
        <p>
          Los datos se guardan en una base de datos asociada a tu cuenta, y cada
          usuario solo puede leer sus propias filas. Las credenciales (token de
          Canvas y permisos de Google) se guardan cifradas o solo en el equipo
          del usuario, nunca en el navegador.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold text-texto">Con quien se comparten</h2>
        <p>
          Con nadie. Los datos no se venden, no se usan para publicidad y no se
          comparten con terceros. El uso de datos recibidos de las APIs de
          Google cumple con la Google API Services User Data Policy, incluidos
          los requisitos de uso limitado.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="font-semibold text-texto">Como borrarlos</h2>
        <p>
          Puedes revocar el acceso de la app en la configuracion de seguridad de
          tu cuenta de Google y pedir el borrado de tus datos abriendo un issue
          en el{" "}
          <a
            href="https://github.com/Mati3939/canvas-downloader"
            className="text-acento underline"
          >
            repositorio del proyecto
          </a>
          .
        </p>
      </section>

      <Link href="/acerca" className="text-acento underline">
        Volver
      </Link>
    </main>
  );
}
