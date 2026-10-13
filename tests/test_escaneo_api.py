"""Tests de la API HTTP de escaneo (escaneo_sesion.py + rutas de canvas_gui.py).
Levanta el servidor real en un puerto libre, con ramos.yaml y DRIVE_ROOT de
prueba (parcheados): nunca toca el Drive real ni el ramos.yaml del usuario."""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import date
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import canvas_gui  # noqa: E402
import sync_ramos  # noqa: E402
from tests.sinteticas import esquinas_centradas, hoja_sintetica  # noqa: E402


def _jpeg_hoja(tam=(640, 480), texto="Apuntes de prueba", lineas=1):
    esquinas = esquinas_centradas(0.6, tam=tam)
    img = hoja_sintetica(esquinas, tam=tam, texto=texto, lineas=lineas)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


class TestEscaneoAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_drive = tempfile.mkdtemp(prefix="escaneo_drive_")
        cls.tmp_cfg_dir = tempfile.mkdtemp(prefix="escaneo_cfg_")
        cls.config_file = Path(cls.tmp_cfg_dir) / "ramos.yaml"
        cls.config_file.write_text(
            'semestre: "S"\n'
            'cursos:\n'
            '  - {nombre: "Ramo X", canvas_course_id: 1, carpeta: "Ramo X"}\n',
            encoding="utf-8",
        )
        cls._parches = [
            mock.patch.object(sync_ramos, "CONFIG_FILE", cls.config_file),
            mock.patch.dict(os.environ, {"DRIVE_ROOT": cls.tmp_drive}),
        ]
        for p in cls._parches:
            p.start()
        # Puerto 0 (no el preferido de canvas_gui): no queremos competir con
        # una instancia real de la GUI que ya pueda estar corriendo.
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), canvas_gui.CanvasGUIHandler)
        cls.port = cls.httpd.server_address[1]
        cls.hilo = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        for p in cls._parches:
            p.stop()
        shutil.rmtree(cls.tmp_drive, ignore_errors=True)
        shutil.rmtree(cls.tmp_cfg_dir, ignore_errors=True)

    def setUp(self):
        canvas_gui._escaneo = None

    def tearDown(self):
        canvas_gui._escaneo = None

    # ---- helpers HTTP

    def _get(self, ruta):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", ruta)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def _post_json(self, ruta, datos):
        cuerpo = json.dumps(datos).encode("utf-8")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", ruta, body=cuerpo, headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def _post_bin(self, ruta, datos):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("POST", ruta, body=datos, headers={"Content-Type": "image/jpeg"})
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    def _delete(self, ruta):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("DELETE", ruta)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    # ---- tests

    def test_get_escanear_sirve_html(self):
        status, cuerpo = self._get("/escanear")
        self.assertEqual(status, 200)
        self.assertIn(b"Escanear apuntes", cuerpo)

    def test_estado_disponible_lista_ramos_sin_sesion(self):
        status, cuerpo = self._get("/api/escaneo/estado")
        self.assertEqual(status, 200)
        datos = json.loads(cuerpo)
        self.assertTrue(datos["disponible"])
        self.assertEqual(datos["ramos"], [{"nombre": "Ramo X"}])
        self.assertIsNone(datos["sesion"])

    def test_sesion_titulo_por_defecto_usa_fecha(self):
        status, cuerpo = self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": None})
        self.assertEqual(status, 200)
        sesion = json.loads(cuerpo)
        self.assertEqual(sesion["ramo"], "Ramo X")
        self.assertEqual(sesion["titulo"], f"Apuntes {date.today():%Y-%m-%d}")
        self.assertEqual(sesion["paginas"], [])

    def test_segunda_sesion_da_409(self):
        status, _ = self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Dup A"})
        self.assertEqual(status, 200)
        status2, cuerpo2 = self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Dup B"})
        self.assertEqual(status2, 409)
        self.assertIn("error", json.loads(cuerpo2))

    def test_sesion_ramo_inexistente_da_404(self):
        status, cuerpo = self._post_json("/api/escaneo/sesion", {"ramo": "No existe", "titulo": None})
        self.assertEqual(status, 404)
        self.assertIn("error", json.loads(cuerpo))

    def test_analizar_sin_sesion_da_409(self):
        status, cuerpo = self._post_bin("/api/escaneo/analizar", _jpeg_hoja())
        self.assertEqual(status, 409)
        self.assertIn("error", json.loads(cuerpo))

    def test_analizar_cuerpo_vacio_y_basura_dan_400_y_servidor_sigue_vivo(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Errores"})

        status, cuerpo = self._post_bin("/api/escaneo/analizar", b"")
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(cuerpo))

        status, cuerpo = self._post_bin("/api/escaneo/analizar", b"esto no es un jpeg")
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(cuerpo))

        status, _ = self._get("/api/escaneo/estado")
        self.assertEqual(status, 200)

    def test_analizar_devuelve_claves_esperadas(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Claves"})
        status, cuerpo = self._post_bin("/api/escaneo/analizar", _jpeg_hoja())
        self.assertEqual(status, 200)
        datos = json.loads(cuerpo)
        for clave in ("estado", "mensaje", "esquinas", "progreso", "capturar"):
            self.assertIn(clave, datos)

    def test_cuatro_hilos_analizando_a_la_vez(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Concurrencia"})
        jpeg = _jpeg_hoja()
        resultados = []
        lock = threading.Lock()

        def trabajo():
            status, _ = self._post_bin("/api/escaneo/analizar", jpeg)
            with lock:
                resultados.append(status)

        hilos = [threading.Thread(target=trabajo) for _ in range(4)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=15)
        self.assertEqual(resultados, [200, 200, 200, 200])

    def test_terminar_sin_paginas_da_400(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Sin Paginas"})
        status, cuerpo = self._post_json("/api/escaneo/terminar", {"titulo": None})
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(cuerpo))

    def test_terminar_con_drive_root_inexistente_da_500_y_conserva_sesion(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Drive Malo"})
        self._post_bin("/api/escaneo/capturar?forzar=1", _jpeg_hoja())
        drive_malo = os.path.join(self.tmp_cfg_dir, "no_existe")
        with mock.patch.dict(os.environ, {"DRIVE_ROOT": drive_malo}):
            status, cuerpo = self._post_json("/api/escaneo/terminar", {"titulo": None})
        self.assertEqual(status, 500)
        self.assertIn("error", json.loads(cuerpo))

        status, cuerpo = self._get("/api/escaneo/estado")
        datos = json.loads(cuerpo)
        self.assertEqual(len(datos["sesion"]["paginas"]), 1)

    def test_titulo_con_caracteres_invalidos_se_sanea(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "a/b:c?"})
        self._post_bin("/api/escaneo/capturar?forzar=1", _jpeg_hoja())
        status, cuerpo = self._post_json("/api/escaneo/terminar", {"titulo": None})
        self.assertEqual(status, 200)
        resultado = json.loads(cuerpo)
        destino = Path(resultado["pdf"])
        self.assertTrue(destino.exists())
        self.assertEqual(destino.parent.name, "Apuntes")

    def test_flujo_completo_borrar_terminar_y_duplicado(self):
        status, cuerpo = self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Flujo Completo"})
        self.assertEqual(status, 200)
        sesion = json.loads(cuerpo)
        self.assertEqual(sesion["paginas"], [])

        gestor = canvas_gui._gestor_escaneo()
        tmp_dir = gestor._sesion.tmp_dir

        jpeg1 = _jpeg_hoja(texto="Pagina uno", lineas=1)
        jpeg2 = _jpeg_hoja(texto="Pagina dos", lineas=8)

        status, cuerpo = self._post_bin("/api/escaneo/capturar?forzar=1", jpeg1)
        self.assertEqual(status, 200)
        pagina1 = json.loads(cuerpo)
        self.assertIn("id", pagina1)
        self.assertTrue(pagina1["miniatura"].startswith("data:image/jpeg;base64,"))

        status, cuerpo = self._post_bin("/api/escaneo/capturar?forzar=1", jpeg2)
        self.assertEqual(status, 200)
        pagina2 = json.loads(cuerpo)

        status, cuerpo = self._delete("/api/escaneo/pagina/" + pagina1["id"])
        self.assertEqual(status, 200)
        datos = json.loads(cuerpo)
        self.assertEqual([p["id"] for p in datos["paginas"]], [pagina2["id"]])
        self.assertTrue(datos["paginas"][0]["miniatura"].startswith("data:image/jpeg;base64,"))

        status, cuerpo = self._post_json("/api/escaneo/terminar", {"titulo": None})
        self.assertEqual(status, 200)
        resultado = json.loads(cuerpo)
        destino = Path(resultado["pdf"])
        esperado = Path(self.tmp_drive) / "S" / "Ramo X" / "Apuntes" / "Flujo Completo.pdf"
        self.assertEqual(destino, esperado)
        self.assertTrue(destino.exists())
        contenido = destino.read_bytes()
        self.assertIn(b"/Count 1", contenido)
        self.assertFalse(tmp_dir.exists())

        status, cuerpo = self._get("/api/escaneo/estado")
        datos = json.loads(cuerpo)
        self.assertIsNone(datos["sesion"])

        # Segundo flujo con el mismo título: debe sufijarse " (2)".
        status, _ = self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Flujo Completo"})
        self.assertEqual(status, 200)
        status, _ = self._post_bin("/api/escaneo/capturar?forzar=1", jpeg1)
        self.assertEqual(status, 200)
        status, cuerpo = self._post_json("/api/escaneo/terminar", {"titulo": None})
        self.assertEqual(status, 200)
        resultado2 = json.loads(cuerpo)
        destino2 = Path(resultado2["pdf"])
        self.assertEqual(destino2.name, "Flujo Completo (2).pdf")
        self.assertTrue(destino2.exists())

    def test_borrar_pagina_inexistente_da_404(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Borrar Inexistente"})
        status, cuerpo = self._delete("/api/escaneo/pagina/p999")
        self.assertEqual(status, 404)
        self.assertIn("error", json.loads(cuerpo))

    def test_pagina_jpeg_inexistente_da_404(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Pagina Inexistente"})
        status, cuerpo = self._get("/api/escaneo/pagina/p999")
        self.assertEqual(status, 404)
        self.assertIn("error", json.loads(cuerpo))

    def test_pagina_jpeg_devuelve_imagen(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Ver Pagina"})
        status, cuerpo = self._post_bin("/api/escaneo/capturar?forzar=1", _jpeg_hoja())
        pagina = json.loads(cuerpo)
        status, cuerpo = self._get("/api/escaneo/pagina/" + pagina["id"])
        self.assertEqual(status, 200)
        self.assertGreater(len(cuerpo), 0)
        arreglo = cv2.imdecode(np.frombuffer(cuerpo, dtype=np.uint8), cv2.IMREAD_COLOR)
        self.assertIsNotNone(arreglo)

    def test_cancelar_descarta_sesion_y_temporales(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Cancelar"})
        gestor = canvas_gui._gestor_escaneo()
        tmp_dir = gestor._sesion.tmp_dir
        status, _ = self._post_json("/api/escaneo/cancelar", {})
        self.assertEqual(status, 200)
        self.assertFalse(tmp_dir.exists())
        status, cuerpo = self._get("/api/escaneo/estado")
        datos = json.loads(cuerpo)
        self.assertIsNone(datos["sesion"])

    def test_abrir_carpeta_sin_pdf_da_404(self):
        status, cuerpo = self._post_json("/api/escaneo/abrir_carpeta", {})
        self.assertEqual(status, 404)
        self.assertIn("error", json.loads(cuerpo))

    def test_abrir_carpeta_con_pdf_llama_startfile(self):
        self._post_json("/api/escaneo/sesion", {"ramo": "Ramo X", "titulo": "Abrir Carpeta"})
        self._post_bin("/api/escaneo/capturar?forzar=1", _jpeg_hoja())
        self._post_json("/api/escaneo/terminar", {"titulo": None})
        with mock.patch("os.startfile", create=True) as llamada:
            status, _ = self._post_json("/api/escaneo/abrir_carpeta", {})
        self.assertEqual(status, 200)
        llamada.assert_called_once()

    def test_cuerpo_demasiado_grande_da_413(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest("POST", "/api/escaneo/analizar")
            conn.putheader("Content-Length", str(41 * 1024 * 1024))
            conn.endheaders()
            resp = conn.getresponse()
            status = resp.status
            resp.read()
        finally:
            conn.close()
        self.assertEqual(status, 413)
        # el servidor sigue respondiendo en una conexión nueva
        status, _ = self._get("/api/escaneo/estado")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
