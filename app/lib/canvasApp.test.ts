import { expect, test } from "vitest";
import { enlaceAppCanvas, esIOS } from "./canvasApp";

test("convierte una URL de Canvas al esquema de la app", () => {
  expect(
    enlaceAppCanvas(
      "https://uni.instructure.com/courses/1/discussion_topics/2",
    ),
  ).toBe("canvas-courses://uni.instructure.com/courses/1/discussion_topics/2");
  expect(
    enlaceAppCanvas("https://uni.instructure.com/courses/1/files/3?wrap=1"),
  ).toBe("canvas-courses://uni.instructure.com/courses/1/files/3?wrap=1");
});

test("ignora URLs que no son de Canvas", () => {
  expect(enlaceAppCanvas("https://drive.google.com/file/d/x")).toBeNull();
  expect(enlaceAppCanvas("/anuncio/1")).toBeNull();
  expect(enlaceAppCanvas("https://instructure.com.evil.cl/x")).toBeNull();
});

test("detecta iOS", () => {
  expect(
    esIOS("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)", 5),
  ).toBe(true);
  expect(esIOS("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", 5)).toBe(
    true,
  );
  expect(esIOS("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", 0)).toBe(
    false,
  );
  expect(esIOS("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", 0)).toBe(false);
});
