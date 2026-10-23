import { describe, expect, test } from "vitest";
import { rutaSegura } from "./redireccion";

describe("rutaSegura", () => {
  test("acepta una ruta interna", () => {
    expect(rutaSegura("/ramo/1")).toBe("/ramo/1");
  });

  test("sin next, usa la ruta por defecto", () => {
    expect(rutaSegura(null)).toBe("/");
    expect(rutaSegura("")).toBe("/");
  });

  test("rechaza una URL absoluta a otro sitio", () => {
    expect(rutaSegura("https://evil.com")).toBe("/");
    expect(rutaSegura("http://evil.com/robo")).toBe("/");
  });

  test("rechaza un protocol-relative (//) que el navegador trata como otro host", () => {
    expect(rutaSegura("//evil.com")).toBe("/");
  });

  test("rechaza una ruta sin barra inicial", () => {
    expect(rutaSegura("evil.com")).toBe("/");
  });

  test("rechaza el truco de la barra invertida", () => {
    expect(rutaSegura("/\\evil.com")).toBe("/");
  });
});
