"""Tests de las fuentes anuncios y mensajes del sync (sin red)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import utils  # noqa: E402
import canvas_sync  # noqa: E402
from canvas_sync import Manifest, _SyncCurso, _fecha_titulo, html_conversacion  # noqa: E402

STAFF = 10
ALUMNO = 20


def conv(cid=1, asunto="Guía 3", last="2026-09-02T10:00:00Z"):
    return {"id": cid, "subject": asunto, "last_message_at": last,
            "participants": [{"id": STAFF, "name": "Profe"}, {"id": ALUMNO, "name": "Alumno"}]}


def detalle(autor=STAFF, adjuntos=None, body="Hola\n<b>curso</b>"):
    return {"participants": [{"id": STAFF, "name": "Profe"}, {"id": ALUMNO, "name": "Alumno"}],
            "messages": [
                {"id": 2, "author_id": ALUMNO, "created_at": "2026-09-02T10:00:00Z",
                 "body": "Gracias", "attachments": []},
                {"id": 1, "author_id": autor, "created_at": "2026-09-01T09:00:00Z",
                 "body": body, "attachments": adjuntos or [],
                 "forwarded_messages": [{"id": 3, "author_id": STAFF,
                                         "created_at": "2026-08-30T08:00:00Z",
                                         "body": "Reenviado", "attachments": []}]},
            ]}


class SyncFalso(_SyncCurso):
    """_SyncCurso sin red: las consultas a Canvas se inyectan."""

    def __init__(self, tmp, dry_run=False, staff=frozenset({STAFF}), convs=(), detalles=None,
                 anuncios=()):
        manifest = Manifest(Path(tmp) / "manifest.json")
        curso = {"nombre": "Ramo", "canvas_course_id": 99, "carpeta": "Ramo"}
        super().__init__(api=None, manifest=manifest, curso=curso, dir_curso=Path(tmp) / "Ramo",
                         fuentes=["anuncios", "mensajes"], log=self.lineas_log, dry_run=dry_run)
        self._staff_fijo = staff
        self._convs = list(convs)
        self._detalles = detalles or {}
        self._anuncios = list(anuncios)
        self.pedidos_detalle = []
        self.archivos_pedidos = []
        self.log_lineas = []

    def lineas_log(self, msg):
        self.log_lineas.append(msg)

    def _staff(self):
        return None if self._staff_fijo is None else set(self._staff_fijo)

    def _conversaciones(self):
        return self._convs

    def _detalle(self, c):
        self.pedidos_detalle.append(c["id"])
        return self._detalles.get(c["id"])

    def _topics_anuncios(self):
        return self._anuncios

    def archivo(self, fid, meta, subdir, contexto):
        self.archivos_pedidos.append((fid, Path(subdir).as_posix(), contexto))
        return f"{Path(subdir).as_posix()}/{meta.get('display_name', fid) if meta else fid}"


class TestAyudantes(unittest.TestCase):
    def test_fecha_titulo_limpia_y_trunca(self):
        self.assertEqual(_fecha_titulo("2026-09-01T09:00:00Z", "Guía: 3/4?", "x"), "2026-09-01 - Guía_ 3_4_")
        self.assertEqual(_fecha_titulo(None, "", "sin asunto"), "sin fecha - sin asunto")
        largo = _fecha_titulo("2026-09-01T00:00:00Z", "a" * 200, "x")
        self.assertLessEqual(len(largo), len("2026-09-01 - ") + 80)

    def test_html_conversacion_ordena_escapa_y_nombra(self):
        h = html_conversacion(conv(), detalle())
        self.assertLess(h.index("Reenviado"), h.index("&lt;b&gt;curso&lt;/b&gt;"))
        self.assertLess(h.index("&lt;b&gt;curso&lt;/b&gt;"), h.index("Gracias"))
        self.assertIn("Hola<br>", h)
        self.assertIn("Profe", h)
        self.assertIn("Alumno", h)


class TestMensajes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_guarda_hilo_con_staff_y_sus_adjuntos(self):
        att = {"id": 555, "display_name": "pauta.pdf", "url": "https://x/f", "size": 1,
               "modified_at": "2026-09-01T09:00:00Z"}
        s = SyncFalso(self.tmp, convs=[conv()], detalles={1: detalle(adjuntos=[att])})
        s.mensajes()
        carpeta = "Mensajes/2026-08-30 - Guía 3"
        self.assertTrue((s.dir_canvas / carpeta / "mensaje.html").exists())
        self.assertIn((555, carpeta, "Mensaje: Guía 3"), s.archivos_pedidos)
        self.assertEqual(s.indice["mensajes"][0]["ruta"], f"{carpeta}/mensaje.html")
        self.assertEqual(s.estado["mensajes"]["1"]["carpeta"], carpeta)

    def test_ignora_hilos_sin_staff_y_no_los_vuelve_a_pedir(self):
        s = SyncFalso(self.tmp, staff={777}, convs=[conv()], detalles={1: detalle(autor=ALUMNO)})
        s.mensajes()
        self.assertFalse((s.dir_canvas / "Mensajes").exists())
        self.assertTrue(s.estado["mensajes"]["1"]["ignorada"])
        s.manifest.guardar()
        s2 = SyncFalso(self.tmp, staff={777}, convs=[conv()], detalles={1: detalle(autor=ALUMNO)})
        s2.mensajes()
        self.assertEqual(s2.pedidos_detalle, [])

    def test_sin_cambios_no_pide_detalle_y_mantiene_indice(self):
        s = SyncFalso(self.tmp, convs=[conv()], detalles={1: detalle()})
        s.mensajes()
        s.manifest.guardar()
        s2 = SyncFalso(self.tmp, convs=[conv()], detalles={1: detalle()})
        s2.mensajes()
        self.assertEqual(s2.pedidos_detalle, [])
        self.assertEqual(len(s2.indice["mensajes"]), 1)

    def test_mensaje_nuevo_en_hilo_reescribe_en_la_misma_carpeta(self):
        s = SyncFalso(self.tmp, convs=[conv()], detalles={1: detalle()})
        s.mensajes()
        s.manifest.guardar()
        s2 = SyncFalso(self.tmp, convs=[conv(asunto="Otro asunto", last="2026-09-05T00:00:00Z")],
                       detalles={1: detalle(body="Nuevo texto")})
        s2.mensajes()
        html = (s2.dir_canvas / "Mensajes/2026-08-30 - Guía 3/mensaje.html").read_text(encoding="utf-8")
        self.assertIn("Nuevo texto", html)

    def test_dry_run_no_escribe(self):
        s = SyncFalso(self.tmp, dry_run=True, convs=[conv()], detalles={1: detalle()})
        s.mensajes()
        self.assertFalse((s.dir_canvas / "Mensajes").exists())
        self.assertNotIn("1", s.estado["mensajes"])

    def test_sin_lista_de_staff_no_baja_mensajes(self):
        s = SyncFalso(self.tmp, staff=None, convs=[conv()], detalles={1: detalle()})
        s.mensajes()
        self.assertEqual(s.pedidos_detalle, [])
        self.assertTrue(any("profes" in l for l in s.log_lineas))

    def test_detalle_que_falla_va_a_errores(self):
        s = SyncFalso(self.tmp, convs=[conv()], detalles={})
        s.mensajes()
        self.assertEqual(len(s.resumen["errores"]), 1)


class TestAnuncios(unittest.TestCase):
    def test_snapshot_adjuntos_e_indice(self):
        tmp = tempfile.mkdtemp()
        topic = {"id": 7, "title": "Control 2", "posted_at": "2026-09-10T12:00:00Z",
                 "message": "<p>Materia</p>", "attachments": [
                     {"id": 8, "display_name": "temario.pdf", "url": "https://x", "size": 1}]}
        s = SyncFalso(tmp, anuncios=[topic])
        s.anuncios()
        sub = "Anuncios/2026-09-10 - Control 2"
        self.assertTrue((s.dir_canvas / sub / "anuncio.html").exists())
        self.assertIn((8, sub, "Anuncio: Control 2"), s.archivos_pedidos)
        self.assertEqual(s.indice["anuncios"][0]["ruta"], f"{sub}/anuncio.html")


class TestSyllabus(unittest.TestCase):
    def test_secciones_nuevas(self):
        tmp = tempfile.mkdtemp()
        topic = {"id": 7, "title": "Control 2", "posted_at": "2026-09-10T12:00:00Z",
                 "message": "<p>x</p>", "attachments": []}
        s = SyncFalso(tmp, convs=[conv()], detalles={1: detalle()}, anuncios=[topic])
        s.anuncios()
        s.mensajes()
        s.escribir_syllabus()
        texto = (s.dir_curso / "syllabus.md").read_text(encoding="utf-8")
        self.assertIn("## Anuncios", texto)
        self.assertIn("## Mensajes de profes", texto)
        self.assertIn("Guía 3", texto)


class TestConfig(unittest.TestCase):
    def _cargar(self, yaml_texto):
        tmp = Path(tempfile.mkdtemp()) / "config.yaml"
        tmp.write_text(yaml_texto, encoding="utf-8")
        with mock.patch.object(utils, "CONFIG_FILE", tmp):
            return utils.cargar_config()

    BASE = 'cursos:\n  - {nombre: R, canvas_course_id: 1, carpeta: R}\n'

    def test_default_incluye_nuevas(self):
        self.assertEqual(self._cargar(self.BASE)["canvas"]["fuentes"], list(utils.FUENTES_DEFAULT))

    def test_lista_explicita_recibe_nuevas(self):
        cfg = self._cargar(self.BASE + 'canvas:\n  fuentes: ["modulos"]\n')
        self.assertEqual(cfg["canvas"]["fuentes"], ["modulos", "anuncios", "mensajes"])

    def test_excluir(self):
        cfg = self._cargar(self.BASE + 'canvas:\n  excluir: ["mensajes"]\n')
        self.assertNotIn("mensajes", cfg["canvas"]["fuentes"])
        self.assertIn("anuncios", cfg["canvas"]["fuentes"])


if __name__ == "__main__":
    unittest.main()
