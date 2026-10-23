"""Tests de worker.snapshot: snapshot_curso() a partir de Canvas + manifest
(sin red: api falsa, como SyncFalso en tests/test_sync_ramos.py)."""
import sys
import tempfile
import unittest
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sync_ramos import Manifest  # noqa: E402
from worker.snapshot import snapshot_curso, LecturaFallida  # noqa: E402

CID = 99
BASE = "https://canvas.example.edu"


def _http_error(status):
    resp = requests.Response()
    resp.status_code = status
    err = requests.HTTPError(f"{status} error de prueba")
    err.response = resp
    return err


class FakeApi:
    """Reemplazo sin red de canvas_descargar.Canvas, con solo lo que usa el worker."""

    def __init__(self, curso=None, tareas=None, anuncios=None, modulos=None,
                 items_por_modulo=None, error_tareas=None, error_modulos=None,
                 error_anuncios=None):
        self._curso = curso if curso is not None else {}
        self._tareas = tareas if tareas is not None else []
        self._anuncios = anuncios if anuncios is not None else []
        self._modulos = modulos if modulos is not None else []
        self._items_por_modulo = items_por_modulo or {}
        self._error_tareas = error_tareas
        self._error_modulos = error_modulos
        self._error_anuncios = error_anuncios

    def curso(self, cid):
        return self._curso

    def tareas(self, cid):
        if self._error_tareas:
            raise self._error_tareas
        return self._tareas

    def discusiones(self, cid, solo_anuncios=False):
        if self._error_anuncios:
            raise self._error_anuncios
        return self._anuncios

    def modulos(self, cid):
        if self._error_modulos:
            raise self._error_modulos
        return self._modulos

    def items_modulo(self, cid, mid):
        return self._items_por_modulo.get(mid, [])


class BaseSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.manifest = Manifest(Path(self.tmp) / "manifest.json")
        self.curso_cfg = {"nombre": "Ramo de prueba", "canvas_course_id": CID, "carpeta": "Ramo"}


class TestRol(BaseSnapshotTest):
    def test_rol_ayudante(self):
        api = FakeApi(curso={"enrollments": [{"type": "teacher"}]})
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["course"]["role"], "ta")

    def test_rol_alumno(self):
        api = FakeApi(curso={"enrollments": [{"type": "student"}]})
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["course"]["role"], "student")

    def test_curso_row_completa(self):
        self.curso_cfg["position"] = 2
        api = FakeApi(curso={"enrollments": [{"type": "student"}]})
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["course"], {
            "canvas_id": CID, "name": "Ramo de prueba", "role": "student",
            "canvas_url": f"{BASE}/courses/{CID}", "position": 2,
        })


class TestAnuncios(BaseSnapshotTest):
    def test_anuncio_con_adjuntos(self):
        url = f"{BASE}/courses/{CID}/discussion_topics/5"
        topic = {"id": 5, "title": "Guía 3", "html_url": url, "message": "<p>Hola</p>",
                 "attachments": [{"id": 77}], "posted_at": "2026-09-01T10:00:00Z"}
        api = FakeApi(anuncios=[topic])
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["announcements"][0], {
            "canvas_id": 5, "course_id": CID, "title": "Guía 3",
            "message_html": "<p>Hola</p>", "posted_at": "2026-09-01T10:00:00Z",
            "canvas_url": url, "attachment_ids": [77],
        })

    def test_anuncio_403_se_trata_como_pestana_oculta(self):
        api = FakeApi(error_anuncios=_http_error(403))
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["announcements"], [])

    def test_anuncio_con_posted_at_null_se_omite(self):
        # Un anuncio demorado (delayed_post_at futuro) tiene posted_at null
        # hasta que se publica; el rol ayudante lo ve igual en Canvas, pero
        # la columna posted_at de Supabase es not null.
        topic = {"id": 6, "title": "Pendiente", "html_url": "https://x",
                 "message": "<p>x</p>", "attachments": [], "posted_at": None}
        api = FakeApi(anuncios=[topic])
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["announcements"], [])

    def test_anuncio_sin_titulo_usa_texto_vacio(self):
        topic = {"id": 5, "title": None, "html_url": "https://x", "message": "<p>x</p>",
                 "attachments": [], "posted_at": "2026-09-01T10:00:00Z"}
        api = FakeApi(anuncios=[topic])
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["announcements"][0]["title"], "")


class TestAssignments(BaseSnapshotTest):
    def test_tarea_basica(self):
        t = {"id": 3, "name": "Tarea 1", "description": "<p>enunciado</p>",
             "due_at": "2026-10-01T23:59:00Z", "unlock_at": None,
             "created_at": "2026-09-01T00:00:00Z",
             "html_url": f"{BASE}/courses/{CID}/assignments/3"}
        api = FakeApi(tareas=[t])
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["assignments"][0], {
            "canvas_id": 3, "course_id": CID, "name": "Tarea 1",
            "description_html": "<p>enunciado</p>", "canvas_due_at": "2026-10-01T23:59:00Z",
            "unlock_at": None, "canvas_created_at": "2026-09-01T00:00:00Z",
            "canvas_url": f"{BASE}/courses/{CID}/assignments/3",
        })

    def test_error_en_tareas_lanza_lectura_fallida(self):
        api = FakeApi(error_tareas=_http_error(500))
        with self.assertRaises(LecturaFallida):
            snapshot_curso(api, self.manifest, self.curso_cfg, BASE)

    def test_tareas_404_se_trata_como_pestana_oculta(self):
        api = FakeApi(error_tareas=_http_error(404))
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["assignments"], [])

    def test_error_de_red_en_modulos_lanza_lectura_fallida(self):
        api = FakeApi(error_modulos=requests.ConnectionError("sin red"))
        with self.assertRaises(LecturaFallida):
            snapshot_curso(api, self.manifest, self.curso_cfg, BASE)

    def test_tarea_sin_nombre_usa_texto_vacio(self):
        t = {"id": 4, "name": None, "description": None, "due_at": None, "unlock_at": None,
             "created_at": "2026-09-01T00:00:00Z", "html_url": f"{BASE}/courses/{CID}/assignments/4"}
        api = FakeApi(tareas=[t])
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["assignments"][0]["name"], "")


class TestModuleItems(BaseSnapshotTest):
    def test_module_items_file_id(self):
        modulos = [{"id": 1, "name": "M1", "position": 1, "unlock_at": None}]
        items = [
            {"id": 10, "position": 1, "title": "Apunte", "type": "File", "content_id": 9,
             "html_url": f"{BASE}/courses/{CID}/modules/items/10"},
            {"id": 11, "position": 2, "title": "Link externo", "type": "ExternalUrl",
             "external_url": "https://ejemplo.com", "html_url": None},
        ]
        api = FakeApi(modulos=modulos, items_por_modulo={1: items})
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)

        self.assertEqual(snap["modules"][0], {
            "canvas_id": 1, "course_id": CID, "name": "M1", "position": 1, "unlock_at": None,
        })

        por_id = {i["canvas_id"]: i for i in snap["module_items"]}
        self.assertEqual(por_id[10], {
            "canvas_id": 10, "course_id": CID, "module_id": 1, "position": 1,
            "title": "Apunte", "type": "File", "file_id": 9, "external_url": None,
            "canvas_url": f"{BASE}/courses/{CID}/modules/items/10",
        })
        self.assertEqual(por_id[11], {
            "canvas_id": 11, "course_id": CID, "module_id": 1, "position": 2,
            "title": "Link externo", "type": "ExternalUrl", "file_id": None,
            "external_url": "https://ejemplo.com", "canvas_url": None,
        })

    def test_modulo_sin_nombre_usa_texto_vacio(self):
        modulos = [{"id": 1, "name": None, "position": 1, "unlock_at": None}]
        api = FakeApi(modulos=modulos, items_por_modulo={1: []})
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["modules"][0]["name"], "")

    def test_item_sin_titulo_usa_texto_vacio(self):
        modulos = [{"id": 1, "name": "M1", "position": 1, "unlock_at": None}]
        items = [{"id": 10, "position": 1, "title": None, "type": "SubHeader"}]
        api = FakeApi(modulos=modulos, items_por_modulo={1: items})
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual(snap["module_items"][0]["title"], "")


class TestFiles(BaseSnapshotTest):
    def test_files_desde_manifest(self):
        self.manifest.curso(CID)["archivos"]["77"] = {
            "ruta": "Anuncios/2026-09-01 - Guía 3/guia3.pdf", "size": 10,
            "modified_at": "2026-09-01T10:00:00Z", "contexto": "Anuncio: Guía 3",
            "descargado_at": "2026-09-01T10:05:00",
        }
        api = FakeApi()
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        f = snap["files"][0]
        self.assertEqual((f["canvas_id"], f["name"], f["source"], f["source_label"]),
                         (77, "guia3.pdf", "anuncios", "Anuncio: Guía 3"))
        self.assertEqual(f["canvas_url"], f"{BASE}/courses/{CID}/files/77")
        self.assertEqual(f["ruta"], "Anuncios/2026-09-01 - Guía 3/guia3.pdf")
        self.assertEqual(f["course_id"], CID)
        self.assertEqual(f["size"], 10)
        self.assertEqual(f["modified_at"], "2026-09-01T10:00:00Z")

    def test_entrada_sin_size_o_modified_at_se_omite(self):
        archivos = self.manifest.curso(CID)["archivos"]
        archivos["1"] = {"ruta": "Archivos/completo.pdf", "size": 10,
                         "modified_at": "2026-09-01T10:00:00Z", "contexto": "ctx"}
        archivos["2"] = {"ruta": "Archivos/sin_size.pdf", "size": None,
                         "modified_at": "2026-09-01T10:00:00Z", "contexto": "ctx"}
        archivos["3"] = {"ruta": "Archivos/sin_fecha.pdf", "size": 5,
                         "modified_at": None, "contexto": "ctx"}
        api = FakeApi()
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        self.assertEqual([f["canvas_id"] for f in snap["files"]], [1])

    def test_source_por_prefijo(self):
        archivos = self.manifest.curso(CID)["archivos"]
        casos = {
            "1": ("Módulos/Semana 1/apunte.pdf", "modulos"),
            "2": ("Archivos/Guías/guia.pdf", "archivos"),
            "3": ("Tareas/Tarea 1/enunciado.pdf", "tareas"),
            "4": ("Mensajes/2026-09-01 - Asunto/adjunto.pdf", "mensajes"),
        }
        for fid, (ruta, _esperado) in casos.items():
            archivos[fid] = {"ruta": ruta, "size": 1, "modified_at": "2026-09-01T10:00:00Z",
                             "contexto": "ctx"}
        api = FakeApi()
        snap = snapshot_curso(api, self.manifest, self.curso_cfg, BASE)
        por_id = {f["canvas_id"]: f for f in snap["files"]}
        for fid, (_ruta, esperado) in casos.items():
            self.assertEqual(por_id[int(fid)]["source"], esperado)


if __name__ == "__main__":
    unittest.main()
