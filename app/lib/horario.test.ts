import { expect, test } from "vitest";
import {
  agruparPorDia,
  claveDia,
  hora,
  lunesDeLaSemana,
  ramoDeEvento,
  sumarDias,
} from "./horario";

test("claveDia usa la hora de Santiago", () => {
  // 02:00 UTC del 4 de nov = 23:00 del 3 de nov en Chile (UTC-3)
  expect(claveDia("2026-11-04T02:00:00Z")).toBe("2026-11-03");
});

test("lunesDeLaSemana y sumarDias", () => {
  expect(lunesDeLaSemana(new Date("2026-11-05T15:00:00Z"))).toBe("2026-11-02");
  expect(lunesDeLaSemana(new Date("2026-11-08T15:00:00Z"))).toBe("2026-11-02"); // domingo
  expect(lunesDeLaSemana(new Date("2026-11-02T15:00:00Z"))).toBe("2026-11-02");
  expect(sumarDias("2026-11-30", 1)).toBe("2026-12-01");
});

test("agruparPorDia ordena por hora", () => {
  const g = agruparPorDia([
    { id: 2, start_at: "2026-11-03T13:00:00-03:00" },
    { id: 1, start_at: "2026-11-03T08:30:00-03:00" },
    { id: 3, start_at: "2026-11-04T08:30:00-03:00" },
  ]);
  expect([...g.keys()]).toEqual(["2026-11-03", "2026-11-04"]);
  expect(g.get("2026-11-03")!.map((e) => e.id)).toEqual([1, 2]);
});

test("ramoDeEvento reconoce el ramo en el titulo", () => {
  const cursos = [
    { canvas_id: 1, name: "Base de Datos" },
    { canvas_id: 2, name: "Taller de Visualización de Datos" },
    { canvas_id: 3, name: "Probabilidades y Estadística" },
  ];
  expect(ramoDeEvento("Certamen 2 - Bases de Datos", cursos)?.canvas_id).toBe(
    1,
  );
  expect(
    ramoDeEvento("Certamen 2 - Probabilidad y Estadística", cursos)?.canvas_id,
  ).toBe(3);
  expect(
    ramoDeEvento("Certamen 2 - Visualización de Datos", cursos)?.canvas_id,
  ).toBe(2);
  expect(ramoDeEvento("Certamen 2 TOPD", cursos)).toBeNull();
});

test("hora usa 24 horas en Santiago", () => {
  expect(hora("2026-11-04T19:00:00Z")).toBe("16:00");
  expect(hora("2026-11-04T11:50:00Z")).toBe("08:50");
});
