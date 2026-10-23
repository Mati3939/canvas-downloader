import { describe, expect, test } from "vitest";
import { agruparMaterial, enlacePrincipal, formatearTamano } from "./material";
import type { Archivo } from "./tipos";

function archivo(datos: Partial<Archivo>): Archivo {
  return {
    user_id: "u1",
    canvas_id: 1,
    course_id: 100,
    name: "archivo.pdf",
    size: 1024,
    modified_at: "2026-10-18T10:00:00Z",
    source: "archivos",
    source_label: "Archivos",
    drive_url: null,
    canvas_url: "https://canvas.example/archivo/1",
    inicial: false,
    first_seen_at: "2026-10-20T09:00:00Z",
    ...datos,
  };
}

describe("enlacePrincipal", () => {
  test("usa drive_url si existe, si no canvas_url", () => {
    const conDrive = archivo({ drive_url: "https://drive.example/a" });
    const sinDrive = archivo({ drive_url: null });

    expect(enlacePrincipal(conDrive)).toEqual({
      href: "https://drive.example/a",
      tipo: "drive",
    });
    expect(enlacePrincipal(sinDrive)).toEqual({
      href: sinDrive.canvas_url,
      tipo: "canvas",
    });
  });
});

describe("agruparMaterial", () => {
  test("agrupa por source_label y ordena archivos por modified_at desc", () => {
    const grupos = agruparMaterial([
      archivo({
        canvas_id: 1,
        source: "modulos",
        source_label: "Semana 1",
        modified_at: "2026-10-01T00:00:00Z",
      }),
      archivo({
        canvas_id: 2,
        source: "modulos",
        source_label: "Semana 1",
        modified_at: "2026-10-05T00:00:00Z",
      }),
      archivo({
        canvas_id: 3,
        source: "modulos",
        source_label: "Semana 2",
        modified_at: "2026-10-03T00:00:00Z",
      }),
    ]);

    expect(grupos).toHaveLength(2);
    const semana1 = grupos.find((g) => g.etiqueta === "Semana 1");
    expect(semana1?.archivos.map((a) => a.canvas_id)).toEqual([2, 1]);
  });

  test("orden de grupos: anuncios, modulos, archivos, tareas, mensajes", () => {
    const grupos = agruparMaterial([
      archivo({ canvas_id: 1, source: "mensajes", source_label: "Mensajes" }),
      archivo({ canvas_id: 2, source: "tareas", source_label: "Tareas" }),
      archivo({ canvas_id: 3, source: "archivos", source_label: "Archivos" }),
      archivo({ canvas_id: 4, source: "modulos", source_label: "Modulos" }),
      archivo({ canvas_id: 5, source: "anuncios", source_label: "Anuncios" }),
    ]);

    expect(grupos.map((g) => g.source)).toEqual([
      "anuncios",
      "modulos",
      "archivos",
      "tareas",
      "mensajes",
    ]);
  });
});

describe("formatearTamano", () => {
  test("bytes sin decimales, KB/MB/GB con un decimal y coma", () => {
    expect(formatearTamano(512)).toBe("512 B");
    expect(formatearTamano(1536)).toBe("1,5 KB");
    expect(formatearTamano(1_258_291)).toBe("1,2 MB");
    expect(formatearTamano(2 * 1024 * 1024 * 1024)).toBe("2,0 GB");
  });
});
