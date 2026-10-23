"""Tests de worker.supabase: Supabase publica snapshots via PostgREST (sin
red: una sesion falsa que registra cada llamada, como FakeApi en
tests/test_worker_snapshot.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.supabase import Supabase  # noqa: E402

URL = "https://proyecto.supabase.co"
KEY = "service-key-secreta"
USER = "11111111-1111-1111-1111-111111111111"
CID = 99


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=None):
        self.status_code = status_code
        self._data = data if data is not None else []
        self.text = text if text is not None else str(self._data)

    def json(self):
        return self._data


class FakeSession:
    """Reemplazo sin red de requests.Session: registra cada llamada y
    devuelve una respuesta programada (o 200 vacia por defecto)."""

    def __init__(self):
        self.llamadas = []
        self._por_metodo = {}

    def programar(self, metodo, respuesta):
        self._por_metodo.setdefault(metodo, []).append(respuesta)

    def _responder(self, metodo):
        cola = self._por_metodo.get(metodo)
        if cola:
            return cola.pop(0)
        return FakeResponse(200, [])

    def _llamar(self, metodo, url, json=None, headers=None, timeout=None):
        self.llamadas.append({
            "metodo": metodo, "url": url, "json": json,
            "headers": headers, "timeout": timeout,
        })
        return self._responder(metodo)

    def post(self, url, json=None, headers=None, timeout=None):
        return self._llamar("POST", url, json=json, headers=headers, timeout=timeout)

    def delete(self, url, headers=None, timeout=None):
        return self._llamar("DELETE", url, headers=headers, timeout=timeout)

    def get(self, url, headers=None, timeout=None):
        return self._llamar("GET", url, headers=headers, timeout=timeout)

    def patch(self, url, json=None, headers=None, timeout=None):
        return self._llamar("PATCH", url, json=json, headers=headers, timeout=timeout)


def _snap(**overrides):
    base = {
        "course": {
            "canvas_id": CID, "name": "Ramo", "role": "student",
            "canvas_url": f"https://canvas.example.edu/courses/{CID}", "position": 1,
        },
        "announcements": [],
        "assignments": [],
        "modules": [],
        "module_items": [],
        "files": [],
    }
    base.update(overrides)
    return base


class BaseSupabaseTest(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession()
        self.sb = Supabase(URL, KEY, USER, session=self.session)

    def _llamadas(self, metodo, tabla=None):
        out = [l for l in self.session.llamadas if l["metodo"] == metodo]
        if tabla is not None:
            out = [l for l in out if f"/rest/v1/{tabla}" in l["url"]]
        return out


class TestUpsert(BaseSupabaseTest):
    def test_upsert_con_merge_y_user_id(self):
        snap = _snap(files=[
            {"canvas_id": 1, "course_id": CID, "name": "a.pdf", "size": 1,
             "modified_at": "2026-01-01T00:00:00Z", "source": "archivos",
             "source_label": "ctx", "canvas_url": "https://x", "ruta": "Archivos/a.pdf"},
        ])
        self.sb.publicar_curso(snap, primera_vez=False)

        posts = self._llamadas("POST", "files")
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post["url"], f"{URL}/rest/v1/files?on_conflict=user_id,canvas_id")
        self.assertIn("resolution=merge-duplicates", post["headers"]["Prefer"])

        fila = post["json"][0]
        self.assertEqual(fila["user_id"], USER)
        self.assertNotIn("first_seen_at", fila)
        self.assertNotIn("ruta", fila)

    def test_mantiene_drive_url_si_esta_presente(self):
        # Task 5 agrega drive_url a cada fila de files (y al curso); este
        # modulo solo debe dejarlo pasar, nunca tocarlo.
        snap = _snap(files=[
            {"canvas_id": 1, "course_id": CID, "name": "a.pdf", "size": 1,
             "modified_at": "x", "source": "archivos", "source_label": "c",
             "canvas_url": "https://x", "ruta": "Archivos/a.pdf",
             "drive_url": "https://drive/a"},
        ])
        self.sb.publicar_curso(snap, primera_vez=False)
        fila = self._llamadas("POST", "files")[0]["json"][0]
        self.assertEqual(fila["drive_url"], "https://drive/a")
        self.assertNotIn("ruta", fila)

    def test_publicar_curso_devuelve_conteos(self):
        snap = _snap(files=[
            {"canvas_id": 1, "course_id": CID, "name": "a", "size": 1,
             "modified_at": "x", "source": "archivos", "source_label": "c",
             "canvas_url": "https://x"},
            {"canvas_id": 2, "course_id": CID, "name": "b", "size": 1,
             "modified_at": "x", "source": "archivos", "source_label": "c",
             "canvas_url": "https://y"},
        ])
        conteos = self.sb.publicar_curso(snap, primera_vez=False)
        self.assertEqual(conteos["courses"], 1)
        self.assertEqual(conteos["files"], 2)
        self.assertEqual(conteos["announcements"], 0)

    def test_orden_curso_antes_de_hijas(self):
        snap = _snap(files=[
            {"canvas_id": 1, "course_id": CID, "name": "a", "size": 1,
             "modified_at": "x", "source": "archivos", "source_label": "c",
             "canvas_url": "https://x"},
        ])
        self.sb.publicar_curso(snap, primera_vez=False)
        posts = self._llamadas("POST")
        tablas = [p["url"].split("/rest/v1/")[1].split("?")[0] for p in posts]
        self.assertEqual(tablas.index("courses"), 0)
        self.assertLess(tablas.index("courses"), tablas.index("files"))


class TestInicial(BaseSupabaseTest):
    def _fila_anuncio(self):
        return {"canvas_id": 5, "course_id": CID, "title": "t", "message_html": "m",
                "posted_at": "2026-01-01T00:00:00Z", "canvas_url": "https://x",
                "attachment_ids": []}

    def test_primera_vez_marca_inicial(self):
        snap = _snap(announcements=[self._fila_anuncio()])
        self.sb.publicar_curso(snap, primera_vez=True)
        fila = self._llamadas("POST", "announcements")[0]["json"][0]
        self.assertTrue(fila["inicial"])

    def test_siguientes_no_envian_inicial(self):
        snap = _snap(announcements=[self._fila_anuncio()])
        self.sb.publicar_curso(snap, primera_vez=False)
        fila = self._llamadas("POST", "announcements")[0]["json"][0]
        self.assertNotIn("inicial", fila)

    def test_inicial_no_se_marca_en_modules(self):
        # "inicial" solo existe en announcements/assignments/files.
        modulo = {"canvas_id": 1, "course_id": CID, "name": "M1", "position": 1,
                  "unlock_at": None}
        snap = _snap(modules=[modulo])
        self.sb.publicar_curso(snap, primera_vez=True)
        fila = self._llamadas("POST", "modules")[0]["json"][0]
        self.assertNotIn("inicial", fila)


class TestPoda(BaseSupabaseTest):
    def test_poda_lo_que_no_esta(self):
        snap = _snap(files=[
            {"canvas_id": 1, "course_id": CID, "name": "a", "size": 1,
             "modified_at": "x", "source": "archivos", "source_label": "c",
             "canvas_url": "https://x"},
            {"canvas_id": 2, "course_id": CID, "name": "b", "size": 1,
             "modified_at": "x", "source": "archivos", "source_label": "c",
             "canvas_url": "https://y"},
        ])
        self.sb.publicar_curso(snap, primera_vez=False)
        delete = self._llamadas("DELETE", "files")[0]
        self.assertEqual(
            delete["url"],
            f"{URL}/rest/v1/files?user_id=eq.{USER}&course_id=eq.{CID}&canvas_id=not.in.(1,2)",
        )

    def test_poda_con_lista_vacia_borra_todo_el_ramo(self):
        snap = _snap()  # sin files
        self.sb.publicar_curso(snap, primera_vez=False)
        delete = self._llamadas("DELETE", "files")[0]
        self.assertEqual(
            delete["url"], f"{URL}/rest/v1/files?user_id=eq.{USER}&course_id=eq.{CID}"
        )
        self.assertNotIn("not.in", delete["url"])

    def test_poda_corre_para_las_cinco_tablas_hijas(self):
        self.sb.publicar_curso(_snap(), primera_vez=False)
        for tabla in ("announcements", "assignments", "modules", "module_items", "files"):
            self.assertEqual(len(self._llamadas("DELETE", tabla)), 1)
        self.assertEqual(len(self._llamadas("DELETE", "courses")), 0)


class TestCurso(BaseSupabaseTest):
    def test_primera_vez_setea_initial_published_at(self):
        snap = _snap()
        self.sb.publicar_curso(snap, primera_vez=True)
        curso = self._llamadas("POST", "courses")[0]["json"][0]
        self.assertIn("initial_published_at", curso)
        self.assertIn("updated_at", curso)

    def test_siguientes_no_setean_initial_published_at(self):
        snap = _snap()
        self.sb.publicar_curso(snap, primera_vez=False)
        curso = self._llamadas("POST", "courses")[0]["json"][0]
        self.assertNotIn("initial_published_at", curso)
        self.assertIn("updated_at", curso)


class TestHeaders(BaseSupabaseTest):
    def test_headers_service_key(self):
        snap = _snap()
        self.sb.publicar_curso(snap, primera_vez=False)
        self.assertTrue(self.session.llamadas)
        for llamada in self.session.llamadas:
            self.assertEqual(llamada["headers"]["apikey"], KEY)
            self.assertEqual(llamada["headers"]["Authorization"], f"Bearer {KEY}")
            self.assertIsNotNone(llamada["timeout"])

    def test_key_no_aparece_en_excepcion(self):
        self.session.programar("POST", FakeResponse(500, text="boom"))
        with self.assertRaises(RuntimeError) as ctx:
            self.sb.publicar_curso(_snap(), primera_vez=False)
        self.assertNotIn(KEY, str(ctx.exception))

    def test_error_http_incluye_status_y_cuerpo(self):
        self.session.programar("POST", FakeResponse(400, text="feo"))
        with self.assertRaises(RuntimeError) as ctx:
            self.sb.publicar_curso(_snap(), primera_vez=False)
        self.assertIn("400", str(ctx.exception))
        self.assertIn("feo", str(ctx.exception))
        self.assertIn("courses", str(ctx.exception))


class TestCursoPublicado(BaseSupabaseTest):
    def test_existe_con_fecha(self):
        self.session.programar(
            "GET", FakeResponse(200, [{"initial_published_at": "2026-01-01T00:00:00Z"}])
        )
        self.assertTrue(self.sb.curso_publicado(CID))

    def test_existe_sin_fecha(self):
        self.session.programar("GET", FakeResponse(200, [{"initial_published_at": None}]))
        self.assertFalse(self.sb.curso_publicado(CID))

    def test_no_existe(self):
        self.session.programar("GET", FakeResponse(200, []))
        self.assertFalse(self.sb.curso_publicado(CID))

    def test_filtra_por_usuario_y_canvas_id(self):
        self.session.programar("GET", FakeResponse(200, []))
        self.sb.curso_publicado(CID)
        get = self._llamadas("GET")[0]
        self.assertIn(f"user_id=eq.{USER}", get["url"])
        self.assertIn(f"canvas_id=eq.{CID}", get["url"])


class TestCorridas(BaseSupabaseTest):
    def test_iniciar_corrida_devuelve_id(self):
        self.session.programar("POST", FakeResponse(201, [{"id": 42}]))
        run_id = self.sb.iniciar_corrida()
        self.assertEqual(run_id, 42)
        post = self._llamadas("POST", "worker_runs")[0]
        self.assertIn("return=representation", post["headers"]["Prefer"])

    def test_cerrar_corrida(self):
        self.sb.cerrar_corrida(42, True, {"files": 3})
        patch = self._llamadas("PATCH", "worker_runs")[0]
        self.assertIn("id=eq.42", patch["url"])
        self.assertEqual(patch["json"]["ok"], True)
        self.assertEqual(patch["json"]["summary"], {"files": 3})
        self.assertIn("finished_at", patch["json"])


if __name__ == "__main__":
    unittest.main()
