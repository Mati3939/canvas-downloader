import Link from "next/link";

/** Barra superior comun a las paginas con sesion. */
export function Encabezado() {
  return (
    <header className="sticky top-0 z-10 border-b border-borde bg-fondo/85 backdrop-blur">
      <div className="mx-auto flex h-12 w-full max-w-6xl items-center px-4 lg:px-8">
        <Link
          href="/"
          className="flex items-center gap-2 text-sm font-semibold text-texto"
        >
          <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-acento" />
          Better Canvas
        </Link>
      </div>
    </header>
  );
}
