import { describe, expect, test } from "vitest";
import { armarNovedades } from "./novedades";
import type { Anuncio, Archivo, Tarea } from "./tipos";

function anuncio(datos: Partial<Anuncio>): Anuncio {
  return {
    user_id: "u1",
    canvas_id: 1,
    course_id: 100,
    title: "Anuncio",
    message_html: "<p>hola</p>",
    posted_at: "2026-10-20T10:00:00Z",
    canvas_url: "https://canvas.example/anuncio/1",
    attachment_ids: [],
    inicial: false,
    first_seen_at: "2026-10-20T10:05:00Z",
    ...datos,
  };
}

function tarea(datos: Partial<Tarea>): Tarea {
  return {
    user_id: "u1",
    canvas_id: 2,
    course_id: 100,
    name: "Tarea",
    description_html: "<p>hola</p>",
    canvas_due_at: null,
    unlock_at: null,
    canvas_created_at: "2026-10-19T10:00:00Z",
    canvas_url: "https://canvas.example/tarea/2",
    inicial: false,
    first_seen_at: "2026-10-20T11:00:00Z",
    ...datos,
  };
}

function archivo(datos: Partial<Archivo>): Archivo {
  return {
    user_id: "u1",
    canvas_id: 3,
    course_id: 100,
    name: "archivo.pdf",
    size: 1024,
    modified_at: "2026-10-18T10:00:00Z",
    source: "archivos",
    source_label: "Archivos",
    drive_url: null,
    canvas_url: "https://canvas.example/archivo/3",
    inicial: false,
    first_seen_at: "2026-10-20T09:00:00Z",
    ...datos,
  };
}

const desde = new Date("2026-10-01T00:00:00Z");

describe("armarNovedades", () => {
  test("excluye filas inicial=true", () => {
    const novedades = armarNovedades(
      [anuncio({ canvas_id: 1, inicial: true })],
      [tarea({ canvas_id: 2, inicial: true })],
      [archivo({ canvas_id: 3, inicial: true })],
      desde,
    );

    expect(novedades).toHaveLength(0);
  });

  test("anuncio usa posted_at; archivo y tarea usan first_seen_at", () => {
    const novedades = armarNovedades(
      [anuncio({ canvas_id: 1, posted_at: "2026-10-05T00:00:00Z" })],
      [tarea({ canvas_id: 2, first_seen_at: "2026-10-06T00:00:00Z" })],
      [archivo({ canvas_id: 3, first_seen_at: "2026-10-07T00:00:00Z" })],
      desde,
    );

    const porTipo = Object.fromEntries(novedades.map((n) => [n.tipo, n.fecha]));
    expect(porTipo.anuncio).toBe("2026-10-05T00:00:00Z");
    expect(porTipo.tarea).toBe("2026-10-06T00:00:00Z");
    expect(porTipo.archivo).toBe("2026-10-07T00:00:00Z");
  });

  test("archivo que es adjunto de un anuncio de la lista no aparece suelto, va en adjuntos del anuncio", () => {
    const unAnuncio = anuncio({ canvas_id: 1, attachment_ids: [3] });
    const unArchivo = archivo({ canvas_id: 3 });
    const otroArchivo = archivo({
      canvas_id: 4,
      canvas_url: "https://canvas.example/archivo/4",
    });

    const novedades = armarNovedades(
      [unAnuncio],
      [],
      [unArchivo, otroArchivo],
      desde,
    );

    const archivosSueltos = novedades.filter((n) => n.tipo === "archivo");
    expect(archivosSueltos.map((n) => n.id)).toEqual([4]);

    const anuncioNovedad = novedades.find((n) => n.tipo === "anuncio");
    expect(anuncioNovedad?.adjuntos).toHaveLength(1);
    expect(anuncioNovedad?.adjuntos?.[0].canvas_id).toBe(3);
  });

  test("ordena de mas nuevo a mas viejo y corta en desde", () => {
    const novedades = armarNovedades(
      [
        anuncio({ canvas_id: 1, posted_at: "2026-10-10T00:00:00Z" }),
        anuncio({ canvas_id: 2, posted_at: "2026-09-20T00:00:00Z" }),
      ],
      [tarea({ canvas_id: 3, first_seen_at: "2026-10-15T00:00:00Z" })],
      [],
      desde,
    );

    expect(novedades.map((n) => n.id)).toEqual([3, 1]);
  });

  test("un adjunto de un anuncio fuera de la ventana aparece suelto", () => {
    const anuncioFueraDeVentana = anuncio({
      canvas_id: 1,
      posted_at: "2026-08-01T00:00:00Z",
      attachment_ids: [3],
    });
    const archivoReciente = archivo({
      canvas_id: 3,
      first_seen_at: "2026-10-10T00:00:00Z",
    });

    const novedades = armarNovedades(
      [anuncioFueraDeVentana],
      [],
      [archivoReciente],
      desde,
    );

    expect(novedades).toHaveLength(1);
    expect(novedades[0]).toMatchObject({ tipo: "archivo", id: 3 });
  });

  test("incluye un item cuya fecha es exactamente igual a desde", () => {
    const novedades = armarNovedades(
      [anuncio({ canvas_id: 1, posted_at: desde.toISOString() })],
      [],
      [],
      desde,
    );

    expect(novedades.map((n) => n.id)).toEqual([1]);
  });
});
