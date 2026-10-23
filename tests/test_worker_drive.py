"""Tests de worker.drive: ruta_en_mi_unidad() y EnlacesDrive (sin red: un
servicio de Drive falso, como FakeApi en tests/test_worker_snapshot.py)."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.drive import (  # noqa: E402
    DriveNoAutorizado,
    EnlacesDrive,
    conectar_drive,
    ruta_en_mi_unidad,
)

_MIME_CARPETA = "application/vnd.google-apps.folder"
_PATRON_Q = re.compile(
    r"^'(?P<padre>[^']*)' in parents and name = '(?P<nombre>.*)' and trashed = false$"
)


def _desescapar(nombre):
    return nombre.replace("\\'", "'").replace("\\\\", "\\")


class ServicioDriveFalso:
    """Reemplazo sin red de la API de Drive v3, con solo
    `files().list(q=..., fields=..., pageSize=...).execute()`."""

    def __init__(self, items):
        # items: [{"id", "name", "mimeType", "webViewLink", "parent"}, ...]
        self._items = items
        self.consultas = []

    def files(self):
        return self

    def list(self, q, fields=None, pageSize=None):
        self.consultas.append(q)
        m = _PATRON_Q.match(q)
        padre = m.group("padre")
        nombre = _desescapar(m.group("nombre"))
        coincidencias = [
            it for it in self._items if it["parent"] == padre and it["name"] == nombre
        ]
        return _EjecutableFalso(coincidencias)


class _EjecutableFalso:
    def __init__(self, archivos):
        self._archivos = archivos

    def execute(self):
        return {
            "files": [
                {
                    "id": a["id"],
                    "name": a["name"],
                    "mimeType": a["mimeType"],
                    "webViewLink": a.get("webViewLink"),
                }
                for a in self._archivos
            ]
        }


def _arbol_de_prueba():
    return [
        {"id": "campus", "name": "Campus", "mimeType": _MIME_CARPETA, "parent": "root",
         "webViewLink": "https://drive/campus"},
        {"id": "s4", "name": "S4", "mimeType": _MIME_CARPETA, "parent": "campus",
         "webViewLink": "https://drive/s4"},
        {"id": "ramo", "name": "Ramo", "mimeType": _MIME_CARPETA, "parent": "s4",
         "webViewLink": "https://drive/ramo"},
        {"id": "canvas", "name": "canvas", "mimeType": _MIME_CARPETA, "parent": "ramo",
         "webViewLink": "https://drive/canvas"},
        {"id": "modulos", "name": "Módulos", "mimeType": _MIME_CARPETA, "parent": "canvas",
         "webViewLink": "https://drive/modulos"},
        {"id": "a", "name": "a.pdf", "mimeType": "application/pdf", "parent": "modulos",
         "webViewLink": "https://drive/a"},
        {"id": "b", "name": "b.pdf", "mimeType": "application/pdf", "parent": "modulos",
         "webViewLink": "https://drive/b"},
    ]


class TestRutaEnMiUnidad(unittest.TestCase):
    def test_ruta_en_mi_unidad(self):
        self.assertEqual(
            ruta_en_mi_unidad(Path(r"G:\Mi unidad\Campus")), ["Campus"]
        )

    def test_ruta_en_my_drive(self):
        self.assertEqual(
            ruta_en_mi_unidad(Path(r"G:\My Drive\Campus\S4")), ["Campus", "S4"]
        )

    def test_sin_mi_unidad_lanza_value_error(self):
        with self.assertRaises(ValueError):
            ruta_en_mi_unidad(Path(r"G:\OtraCosa\Campus"))


class TestEnlacesDrive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache_path = Path(self.tmp) / "drive_cache.json"
        self.servicio = ServicioDriveFalso(_arbol_de_prueba())
        self.e = EnlacesDrive(self.servicio, self.cache_path)

    def test_resuelve_por_carpetas_y_cachea(self):
        self.assertEqual(
            self.e.enlace(["Campus", "S4", "Ramo", "canvas", "Módulos", "a.pdf"]),
            "https://drive/a",
        )
        consultas_tras_primera = len(self.servicio.consultas)

        # Segunda hoja del mismo árbol: no debe volver a listar las carpetas
        # comunes (Campus, S4, Ramo, canvas, Módulos), solo buscar b.pdf.
        self.assertEqual(
            self.e.enlace(["Campus", "S4", "Ramo", "canvas", "Módulos", "b.pdf"]),
            "https://drive/b",
        )
        self.assertEqual(len(self.servicio.consultas), consultas_tras_primera + 1)

    def test_inexistente_devuelve_none_y_no_cachea(self):
        self.assertIsNone(
            self.e.enlace(["Campus", "S4", "Ramo", "canvas", "Módulos", "no-existe.pdf"])
        )
        self.e.guardar()
        datos = self.cache_path.read_text(encoding="utf-8")
        self.assertNotIn("no-existe.pdf", datos)

        # Al no cachearse, una segunda consulta vuelve a buscar la misma hoja.
        consultas_previas = len(self.servicio.consultas)
        self.e.enlace(["Campus", "S4", "Ramo", "canvas", "Módulos", "no-existe.pdf"])
        self.assertEqual(len(self.servicio.consultas), consultas_previas + 1)

    def test_nombre_con_comilla_se_escapa_en_query(self):
        servicio = ServicioDriveFalso([
            {"id": "g", "name": "Guía d'Alembert.pdf", "mimeType": "application/pdf",
             "parent": "root", "webViewLink": "https://drive/galembert"},
        ])
        e = EnlacesDrive(servicio, Path(self.tmp) / "otra_cache.json")
        self.assertEqual(e.enlace(["Guía d'Alembert.pdf"]), "https://drive/galembert")
        self.assertIn("Gu\u00eda d\\'Alembert.pdf", servicio.consultas[-1])

    def test_guardar_y_recargar_cache(self):
        self.e.enlace(["Campus", "S4", "Ramo", "canvas", "Módulos", "a.pdf"])
        self.e.guardar()

        servicio_nuevo = ServicioDriveFalso(_arbol_de_prueba())
        e2 = EnlacesDrive(servicio_nuevo, self.cache_path)
        self.assertEqual(
            e2.enlace(["Campus", "S4", "Ramo", "canvas", "Módulos", "a.pdf"]),
            "https://drive/a",
        )
        # Ya estaba cacheado por ruta completa: no hizo falta consultar.
        self.assertEqual(len(servicio_nuevo.consultas), 0)


class TestConectarDrive(unittest.TestCase):
    def test_sin_token_y_no_interactivo_lanza_excepcion(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DriveNoAutorizado):
                conectar_drive(Path(tmp), interactivo=False)


if __name__ == "__main__":
    unittest.main()
