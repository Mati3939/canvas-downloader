import { expect, test } from "vitest";
import { ordenarTareas, proximasEntregas, type TareaResumen } from "./tareas";

const AHORA = new Date("2026-11-03T12:00:00Z");

function tarea(id: number, due: string | null, course = 1): TareaResumen {
  return { canvas_id: id, course_id: course, name: `T${id}`, canvas_due_at: due, canvas_url: "u" };
}

test("ordenarTareas separa proximas, sin fecha y pasadas", () => {
  const r = ordenarTareas(
    [
      tarea(1, "2026-11-10T00:00:00Z"),
      tarea(2, "2026-11-01T00:00:00Z"),
      tarea(3, null),
      tarea(4, "2026-11-05T00:00:00Z"),
      tarea(5, "2026-10-20T00:00:00Z"),
    ],
    AHORA,
  );
  expect(r.proximas.map((t) => t.canvas_id)).toEqual([4, 1]);
  expect(r.sinFecha.map((t) => t.canvas_id)).toEqual([3]);
  expect(r.pasadas.map((t) => t.canvas_id)).toEqual([2, 5]);
});

test("proximasEntregas filtra por ventana y por ramos de alumno", () => {
  const r = proximasEntregas(
    [
      tarea(1, "2026-11-09T00:00:00Z"),
      tarea(2, "2026-11-04T00:00:00Z"),
      tarea(3, "2026-11-04T00:00:00Z", 9),
      tarea(4, "2026-11-20T00:00:00Z"),
      tarea(5, "2026-11-02T00:00:00Z"),
      tarea(6, null),
    ],
    new Set([1]),
    AHORA,
    7,
  );
  expect(r.map((t) => t.canvas_id)).toEqual([2, 1]);
});
