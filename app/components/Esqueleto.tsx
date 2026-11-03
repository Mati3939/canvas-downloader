import { Encabezado } from "@/components/Encabezado";

/** Pantalla de carga: bloques grises mientras llegan los datos. */
export function Esqueleto({ ancho = "max-w-[1800px]" }: { ancho?: string }) {
  return (
    <>
      <Encabezado />
      <main
        aria-busy
        className={`mx-auto flex w-full ${ancho} flex-1 flex-col gap-4 px-4 py-6 lg:px-8 lg:py-8`}
      >
        <div className="h-6 w-1/3 animate-pulse rounded-md bg-superficie-2" />
        <div className="h-4 w-1/2 animate-pulse rounded-md bg-superficie-2" />
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 animate-pulse rounded-xl border border-borde bg-superficie"
          />
        ))}
      </main>
    </>
  );
}
