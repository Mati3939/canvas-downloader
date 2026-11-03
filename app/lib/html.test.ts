import { describe, expect, test } from "vitest";
import { idsArchivosEnHtml, limpiarHtmlCanvas, type ArchivoEnlazable } from "./html";

const BASE = "https://canvas.ejemplo.cl";
const ARCHIVOS = new Map<number, ArchivoEnlazable>([
  [11, { drive_url: "https://drive.google.com/file/d/abc/view", canvas_url: `${BASE}/courses/1/files/11` }],
  [12, { drive_url: null, canvas_url: `${BASE}/courses/1/files/12` }],
]);

describe("limpiarHtmlCanvas", () => {
  test("enlace a archivo con copia en Drive apunta a Drive", () => {
    const html = `<a class="x" data-api-endpoint="y" href="${BASE}/courses/1/files/11?verifier=v&wrap=1">guia.pdf</a>`;
    const limpio = limpiarHtmlCanvas(html, BASE, ARCHIVOS);
    expect(limpio).toContain('href="https://drive.google.com/file/d/abc/view"');
    expect(limpio).toContain('target="_blank"');
    expect(limpio).not.toContain("data-api-endpoint");
    expect(limpio).not.toContain("class=");
  });

  test("enlace a archivo sin Drive queda en Canvas, absoluto", () => {
    const limpio = limpiarHtmlCanvas('<a href="/courses/1/files/12/download">x</a>', BASE, ARCHIVOS);
    expect(limpio).toContain(`href="${BASE}/courses/1/files/12/download"`);
  });

  test("quita scripts, estilos y enlaces javascript", () => {
    const limpio = limpiarHtmlCanvas(
      '<p style="color:red" onclick="x()">hola</p><script>alert(1)</script><a href="javascript:alert(1)">mal</a>',
      BASE,
      ARCHIVOS,
    );
    expect(limpio).toBe("<p>hola</p><span>mal</span>");
  });

  test("imagen de Canvas se reemplaza por un enlace", () => {
    const limpio = limpiarHtmlCanvas(`<img src="/courses/1/files/12/preview" alt="grafico">`, BASE, ARCHIVOS);
    expect(limpio).toContain("<a ");
    expect(limpio).toContain("[Imagen: grafico]");
    expect(limpio).not.toContain("<img");
  });

  test("imagen externa se mantiene", () => {
    const limpio = limpiarHtmlCanvas('<img src="https://otro.cl/a.png" alt="">', BASE, ARCHIVOS);
    expect(limpio).toContain('<img src="https://otro.cl/a.png"');
  });
});

test("idsArchivosEnHtml encuentra ids sin repetir", () => {
  const html = `<a href="${BASE}/courses/1/files/11?x=1">a</a><a href="/courses/1/files/11">b</a><img src="/files/12/preview">`;
  expect(idsArchivosEnHtml(html).sort()).toEqual([11, 12]);
});
