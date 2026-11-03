/** Punto de color que identifica a un ramo. */
export function PuntoRamo({ color }: { color: string }) {
  return (
    <span
      aria-hidden
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={{ backgroundColor: color }}
    />
  );
}
