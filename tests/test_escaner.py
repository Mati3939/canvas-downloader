"""Tests de escaner.py (visión pura, sin HTTP). Todo con imágenes sintéticas
generadas en tests/sinteticas.py."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import escaner  # noqa: E402
from escaner import (  # noqa: E402
    Detector, Diagnostico, armar_pdf, codificar_jpeg, decodificar_jpeg,
    detectar_hoja, distancia_huellas, enderezar, huella, miniatura_jpeg,
    nitidez, ordenar_esquinas, procesar_pagina, realzar,
)
from tests.sinteticas import esquinas_centradas, hoja_sintetica  # noqa: E402


def _secuencia(detector, esquinas_por_t, img_por_t=None, texto="Apuntes de prueba",
               desenfoque=0, tam=(1280, 720), lineas=1):
    """Corre detector.analizar para cada (t, esquinas) y devuelve la lista de
    Diagnostico. Si `img_por_t` no se da, genera la hoja con esas esquinas."""
    resultados = []
    for i, (t, esquinas) in enumerate(esquinas_por_t):
        if img_por_t is not None:
            img = img_por_t[i]
        else:
            img = hoja_sintetica(esquinas, tam=tam, texto=texto, desenfoque=desenfoque, lineas=lineas)
        resultados.append(detector.analizar(img, t))
    return resultados


class TestDetectarHoja(unittest.TestCase):
    def test_encuentra_hoja_centrada_1280x720(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.5, tam=tam)
        img = hoja_sintetica(esquinas, tam=tam)
        detectadas = detectar_hoja(img)
        self.assertIsNotNone(detectadas)
        esperado = ordenar_esquinas(esquinas)
        self.assertTrue(np.allclose(detectadas, esperado, atol=0.03 * max(tam)),
                        f"{detectadas} vs {esperado}")

    def test_encuentra_hoja_centrada_1920x1080(self):
        tam = (1920, 1080)
        esquinas = esquinas_centradas(0.5, tam=tam)
        img = hoja_sintetica(esquinas, tam=tam)
        detectadas = detectar_hoja(img)
        self.assertIsNotNone(detectadas)
        esperado = ordenar_esquinas(esquinas)
        self.assertTrue(np.allclose(detectadas, esperado, atol=0.03 * max(tam)),
                        f"{detectadas} vs {esperado}")

    def test_sin_hoja_devuelve_none(self):
        img = np.full((720, 1280, 3), 60, dtype=np.uint8)
        self.assertIsNone(detectar_hoja(img))

    def test_bajo_contraste_no_lanza_excepcion(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.5, tam=tam)
        img = hoja_sintetica(esquinas, tam=tam, fondo=190, papel=200)
        try:
            detectar_hoja(img)  # puede ser None o no; lo que importa es que no explote
        except Exception as e:  # pragma: no cover
            self.fail(f"detectar_hoja lanzó excepción con bajo contraste: {e}")


class TestOrdenarEsquinas(unittest.TestCase):
    def test_ordena_puntos_desordenados(self):
        desordenado = np.array([[100, 100], [0, 0], [100, 0], [0, 100]], dtype=np.float32)
        ordenado = ordenar_esquinas(desordenado)
        esperado = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
        self.assertTrue(np.allclose(ordenado, esperado))


class TestEncuadre(unittest.TestCase):
    def _un_frame(self, esquinas, tam=(1280, 720)):
        det = Detector()
        img = hoja_sintetica(esquinas, tam=tam)
        return det.analizar(img, 0.0)

    def test_hoja_se_sale_por_la_izquierda(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.5, tam=tam)
        objetivo_x0 = escaner.MARGEN * tam[0] * 0.5  # bien adentro del margen
        esquinas[:, 0] -= (esquinas[:, 0].min() - objetivo_x0)
        diag = self._un_frame(esquinas, tam=tam)
        self.assertEqual(diag.estado, "encuadre")
        self.assertIn("izquierda", diag.mensaje)

    def test_hoja_chica_pide_acercar(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.30, tam=tam)
        diag = self._un_frame(esquinas, tam=tam)
        self.assertEqual(diag.estado, "encuadre")
        self.assertIn("Acerc", diag.mensaje)

    def test_hoja_grande_pide_alejar(self):
        # Geométricamente, limpiar el margen (2%) en ambos ejes y a la vez
        # superar AREA_MAX (90%) deja un margen de maniobra de menos de un
        # píxel en 1280x720: no alcanza para absorber el ruido de
        # detectar_hoja. Se prueba la lógica de encuadre directamente,
        # reemplazando detectar_hoja por esquinas exactas (sin pasar por la
        # detección real, que ya se cubre en TestDetectarHoja).
        tam = (1280, 720)
        margen = escaner.MARGEN
        mx, my = margen * tam[0] * 1.2, margen * tam[1] * 1.2
        esquinas = np.array([[mx, my], [tam[0] - mx, my],
                             [tam[0] - mx, tam[1] - my], [mx, tam[1] - my]], dtype=np.float32)
        area_frac = ((tam[0] - 2 * mx) * (tam[1] - 2 * my)) / (tam[0] * tam[1])
        self.assertGreater(area_frac, escaner.AREA_MAX)
        with mock.patch.object(escaner, "detectar_hoja", return_value=esquinas):
            det = Detector()
            diag = det.analizar(np.zeros((tam[1], tam[0], 3), dtype=np.uint8), 0.0)
        self.assertEqual(diag.estado, "encuadre")
        self.assertIn("Alej", diag.mensaje)

    def test_trapecio_fuerte_pide_paralelo(self):
        tam = (1280, 720)
        base = esquinas_centradas(0.5, tam=tam)
        # angosta mucho el lado superior: trapecio fuerte, misma área aprox.
        ancho_total = base[1, 0] - base[0, 0]
        achique = ancho_total * 0.35
        esquinas = base.copy()
        esquinas[0, 0] += achique / 2
        esquinas[1, 0] -= achique / 2
        diag = self._un_frame(esquinas, tam=tam)
        self.assertEqual(diag.estado, "encuadre")
        self.assertIn("paralelo", diag.mensaje)


class TestQuieto(unittest.TestCase):
    def test_quieto_hasta_cubrir_quieto_seg(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.5, tam=tam)
        det = Detector()
        resultados = _secuencia(det, [(0.0, esquinas), (0.2, esquinas), (0.4, esquinas)], tam=tam)
        for r in resultados:
            self.assertEqual(r.estado, "quieto")
        r = det.analizar(hoja_sintetica(esquinas, tam=tam), 0.6)
        self.assertNotEqual(r.estado, "quieto")

    def test_salto_grande_reinicia_quieto(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.5, tam=tam)
        det = Detector()
        _secuencia(det, [(0.0, esquinas), (0.2, esquinas), (0.4, esquinas)], tam=tam)
        r = det.analizar(hoja_sintetica(esquinas, tam=tam), 0.6)
        self.assertNotEqual(r.estado, "quieto")  # ya estable

        saltada = esquinas.copy()
        saltada[:, 0] += 0.05 * tam[0]  # salto de 5% del ancho
        r = det.analizar(hoja_sintetica(saltada, tam=tam), 0.8)
        self.assertEqual(r.estado, "quieto")  # se reinició


class TestEnfoque(unittest.TestCase):
    def _hasta_listo(self, tam=(1280, 720), desenfoque=0):
        esquinas = esquinas_centradas(0.5, tam=tam)
        det = Detector()
        tiempos = [round(0.2 * i, 2) for i in range(5)]  # 0, .2, .4, .6, .8
        resultados = _secuencia(det, [(t, esquinas) for t in tiempos], tam=tam, desenfoque=desenfoque)
        return resultados[-1]

    def test_secuencia_nitida_llega_a_listo(self):
        r = self._hasta_listo(desenfoque=0)
        self.assertEqual(r.estado, "listo")

    def test_secuencia_borrosa_queda_desenfocada(self):
        r = self._hasta_listo(desenfoque=21)
        self.assertEqual(r.estado, "desenfocado")


class TestCaptura(unittest.TestCase):
    def test_captura_una_sola_vez(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.5, tam=tam)
        det = Detector()
        tiempos = [round(0.2 * i, 2) for i in range(11)]  # 0.0 .. 2.0
        resultados = _secuencia(det, [(t, esquinas) for t in tiempos], tam=tam)
        capturas = [r for r in resultados if r.capturar]
        self.assertEqual(len(capturas), 1)
        self.assertEqual(resultados[-1].estado, "pasa_pagina")


class TestAntiDuplicado(unittest.TestCase):
    # Nota sobre `lineas`: la huella (32x32) normaliza casi todo el encuadre y
    # promedia el detalle fino, así que una sola palabra distinta en un
    # renglón casi no cambia la huella. Para simular una "página distinta" de
    # verdad (bastante más o menos contenido) se usan varios renglones más.

    def _capturar(self, det, tam=(1280, 720), texto="Apuntes de prueba", lineas=1):
        esquinas = esquinas_centradas(0.5, tam=tam)
        tiempos = [round(0.2 * i, 2) for i in range(8)]
        resultados = _secuencia(det, [(t, esquinas) for t in tiempos], tam=tam, texto=texto,
                                lineas=lineas)
        self.assertTrue(any(r.capturar for r in resultados), "no llegó a capturar")
        return tiempos[-1], esquinas

    def test_misma_pagina_tras_moverse_no_vuelve_a_capturar(self):
        tam = (1280, 720)
        det = Detector()
        t_ult, esquinas = self._capturar(det, tam=tam)

        t = t_ult + 0.2
        sin_hoja = np.full((tam[1], tam[0], 3), 60, dtype=np.uint8)
        r = det.analizar(sin_hoja, t)
        self.assertEqual(r.estado, "pasa_pagina")

        tiempos = [round(t + 0.2 + 0.2 * i, 2) for i in range(12)]
        resultados = _secuencia(det, [(tt, esquinas) for tt in tiempos], tam=tam)
        self.assertFalse(any(r.capturar for r in resultados),
                         "no debería recapturar la misma página")
        self.assertTrue(all(r.estado == "pasa_pagina" for r in resultados))

    def test_pagina_distinta_vuelve_a_capturar(self):
        tam = (1280, 720)
        det = Detector()
        t_ult, esquinas = self._capturar(det, tam=tam, texto="Pagina uno", lineas=1)

        t = t_ult + 0.2
        sin_hoja = np.full((tam[1], tam[0], 3), 60, dtype=np.uint8)
        det.analizar(sin_hoja, t)

        tiempos = [round(t + 0.2 + 0.2 * i, 2) for i in range(12)]
        resultados = _secuencia(det, [(tt, esquinas) for tt in tiempos], tam=tam, texto="Pagina dos",
                                lineas=8)
        self.assertTrue(any(r.capturar for r in resultados),
                         "debería capturar la página distinta")

    def test_sin_movimiento_pagina_distinta_no_captura(self):
        tam = (1280, 720)
        det = Detector()
        t_ult, esquinas = self._capturar(det, tam=tam, texto="Pagina uno", lineas=1)

        # sin pasar por "sin hoja": misma posición, pero con bastante más texto
        tiempos = [round(t_ult + 0.2 + 0.2 * i, 2) for i in range(8)]
        resultados = _secuencia(det, [(tt, esquinas) for tt in tiempos], tam=tam, texto="Pagina dos",
                                lineas=8)
        self.assertFalse(any(r.capturar for r in resultados),
                         "sin movimiento no debería capturar aunque la página cambió")
        self.assertTrue(all(r.estado == "pasa_pagina" for r in resultados))

    def test_fijar_ultima_huella_none_permite_recapturar(self):
        tam = (1280, 720)
        det = Detector()
        t_ult, esquinas = self._capturar(det, tam=tam)

        t = t_ult + 0.2
        sin_hoja = np.full((tam[1], tam[0], 3), 60, dtype=np.uint8)
        det.analizar(sin_hoja, t)
        det.fijar_ultima_huella(None)  # como si se hubiera borrado la única página

        tiempos = [round(t + 0.2 + 0.2 * i, 2) for i in range(12)]
        resultados = _secuencia(det, [(tt, esquinas) for tt in tiempos], tam=tam)
        self.assertTrue(any(r.capturar for r in resultados),
                         "tras fijar_ultima_huella(None) debería volver a capturar")


class TestRealzar(unittest.TestCase):
    def setUp(self):
        self.tam = (1280, 720)
        self.esquinas = esquinas_centradas(0.6, tam=self.tam)
        self.img = hoja_sintetica(self.esquinas, tam=self.tam)
        self.enderezada = enderezar(self.img, ordenar_esquinas(self.esquinas))
        self.realzada = realzar(self.enderezada)

    def test_papel_queda_casi_blanco(self):
        alto, ancho = self.realzada.shape[:2]
        centro = self.realzada[alto // 2 - 5:alto // 2 + 5, 20:40]
        self.assertGreater(np.median(centro), 235)

    def test_tinta_sigue_oscura(self):
        # región donde hoja_sintetica dibuja el texto (tinta oscura)
        caja = self.realzada[0:80, 0:300]
        self.assertLess(float(np.min(caja)), 90)

    def test_trazo_amarillo_conserva_saturacion(self):
        # el trazo resaltador queda alrededor de (y0+70, x0..x1) en origen;
        # tras enderezar, aprox en la misma franja relativa a la hoja.
        franja = self.realzada[60:80, 20:300]
        hsv = cv2.cvtColor(franja, cv2.COLOR_BGR2HSV)
        self.assertGreater(float(hsv[:, :, 1].max()) / 255.0, 0.4)

    def test_cuadricula_atenuada(self):
        # franja vertical que cae sobre una línea de cuadrícula (cada 20 px),
        # evitando la zona de texto/resaltador (filas 0-80)
        franja = self.realzada[100:400, 98:103]
        self.assertGreater(float(np.mean(franja)), 215)


class TestDecodificarCodificar(unittest.TestCase):
    def test_vacio_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            decodificar_jpeg(b"")

    def test_basura_lanza_valueerror(self):
        with self.assertRaises(ValueError):
            decodificar_jpeg(b"esto no es un jpeg")

    def test_codificar_decodificar_viaja_ida_y_vuelta(self):
        img = np.full((40, 40, 3), 128, dtype=np.uint8)
        datos = codificar_jpeg(img)
        de_vuelta = decodificar_jpeg(datos)
        self.assertEqual(de_vuelta.shape, img.shape)


class TestMiniatura(unittest.TestCase):
    def test_miniatura_respeta_ancho(self):
        img = np.full((300, 600, 3), 200, dtype=np.uint8)
        datos = miniatura_jpeg(img, ancho=240)
        de_vuelta = decodificar_jpeg(datos)
        self.assertEqual(de_vuelta.shape[1], 240)
        self.assertEqual(de_vuelta.shape[0], 120)


class TestProcesarPagina(unittest.TestCase):
    def test_con_esquinas_endereza_y_realza(self):
        tam = (1280, 720)
        esquinas = esquinas_centradas(0.6, tam=tam)
        img = hoja_sintetica(esquinas, tam=tam)
        salida = procesar_pagina(img, ordenar_esquinas(esquinas))
        self.assertNotEqual(salida.shape[:2], img.shape[:2])
        self.assertGreater(np.median(salida), 150)


class TestArmarPdf(unittest.TestCase):
    def test_arma_pdf_con_tres_paginas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rutas = []
            for i in range(3):
                img = np.full((100, 80, 3), 200, dtype=np.uint8)
                ruta = tmp / f"p{i}.jpg"
                ruta.write_bytes(codificar_jpeg(img))
                rutas.append(ruta)
            destino = tmp / "salida.pdf"
            armar_pdf(rutas, destino)
            self.assertTrue(destino.exists())
            self.assertFalse(destino.with_name(destino.name + ".tmp").exists())
            contenido = destino.read_bytes()
            self.assertIn(b"/Count 3", contenido)


if __name__ == "__main__":
    unittest.main()
