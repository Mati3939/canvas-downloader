import { expect, test } from "vitest";
import { colorRamo, PALETA_RAMOS } from "./colores";

test("ramos con posiciones seguidas tienen colores distintos", () => {
  const colores = PALETA_RAMOS.map((_, i) =>
    colorRamo({ canvas_id: 1, position: i }),
  );
  expect(new Set(colores).size).toBe(PALETA_RAMOS.length);
});

test("sin posicion usa el id", () => {
  expect(colorRamo({ canvas_id: 9, position: null })).toBe(PALETA_RAMOS[1]);
});
