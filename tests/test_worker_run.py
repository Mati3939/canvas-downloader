"""Tests de worker.run: correr() encadena sync -> snapshot -> enlaces de
Drive -> Supabase, con lock de archivo (sin red: todo lo que toca Canvas,
Drive y Supabase es inyectable, como en tests/test_worker_snapshot.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.drive import DriveNoAutorizado  # noqa: E402
from worker.snapshot import LecturaFallida  # noqa: E402
import worker.run as run  # noqa: E402

CID_A = 10
CID_B = 20


def _cfg():
    return {
        "semestre": "S1",
        "cursos": [
            {"nombre": "Ramo A", "canvas_course_id": CID_A, "carpeta": "RamoA"},
            {"nombre": "Ramo B", "canvas_course_id": CID_B, "carpeta": "RamoB"},
        ],
    }


def _env(tmp):
    return {
        "SUPABASE_URL": "https://proyecto.supabase.co",
        "SUPABASE_SERVICE_KEY": "service-key-secreta",
        "BC_USER_ID": "11111111-1111-1111-1111-111111111111",
        "DRIVE_ROOT": str(Path(tmp) / "Mi unidad" / "Campus"),
    }


def _snap(cid, nombre, files=None):
    return {
        "course": {"canvas_id": cid, "name": nombre, "role": "student",
                   "canvas_url": f"https://canvas.example.edu/courses/{cid}", "position": 0},
        "announcements": [], "assignments": [], "modules": [], "module_items": [],
        "files": files or [],
    }


class FakeApi:
    base = "https://canvas.example.edu"


class FakeSupabase:
    """Reemplazo sin red de worker.supabase.Supabase: registra cada llamada."""

    def __init__(self):
        self.publicaciones = []   # (canvas_id, primera_vez, snap)
        self.ya_publicados = set()
        self.runs_iniciados = 0
        self.cerradas = []        # (run_id, ok, summary)

    def curso_publicado(self, canvas_id):
        return canvas_id in self.ya_publicados

    def publicar_curso(self, snap, primera_vez):
        cid = snap["course"]["canvas_id"]
        self.publicaciones.append((cid, primera_vez, snap))
        return {"courses": 1, "files": len(snap["files"])}

    def iniciar_corrida(self):
        self.runs_iniciados += 1
        return 42

    def cerrar_corrida(self, run_id, ok, summary):
        self.cerradas.append((run_id, ok, summary))


class FakeEnlacesDrive:
    """Registra cada partes pedida y devuelve un enlace previsible."""

    def __init__(self, servicio, cache_path):
        self.servicio = servicio
        self.cache_path = Path(cache_path)
        self.pedidos = []
        self.guardada = False

    def enlace(self, partes):
        self.pedidos.append(list(partes))
        return "https://drive/" + "/".join(partes)

    def guardar(self):
        self.guardada = True


class BaseRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.estado_dir = Path(self.tmp) / "worker_estado"
        self.manifest_path = Path(self.tmp) / "manifest.json"
        self.lineas = []
        self.env = _env(self.tmp)
        self.fake_sb = FakeSupabase()
        self.enlaces_creadas = []

        def enlaces_cls(servicio, cache_path):
            e = FakeEnlacesDrive(servicio, cache_path)
            self.enlaces_creadas.append(e)
            return e
        self._enlaces_cls = enlaces_cls

    def log(self, msg=""):
        self.lineas.append(str(msg))

    def _kwargs(self, snapshot_curso, **overrides):
        base = dict(
            estado_dir=self.estado_dir,
            leer_env=lambda: dict(self.env),
            cargar_config=_cfg,
            sincronizar=lambda *a, **k: self.fail("sincronizar no deberia llamarse (sync=False)"),
            conectar=lambda: FakeApi(),
            snapshot_curso=snapshot_curso,
            Supabase=lambda url, key, user: self.fake_sb,
            conectar_drive=lambda estado_dir: "servicio-falso",
            EnlacesDrive=self._enlaces_cls,
            manifest_path=self.manifest_path,
        )
        base.update(overrides)
        return base


class TestRamoQueFalla(BaseRunTest):
    def test_ramo_que_falla_no_se_publica_ni_poda(self):
        def snapshot_curso(api, manifest, curso_cfg, base_url):
            if curso_cfg["canvas_course_id"] == CID_A:
                raise LecturaFallida("boom")
            return _snap(CID_B, "Ramo B")

        resultados = run.correr(log=self.log, sync=False,
                                 **self._kwargs(snapshot_curso))

        self.assertFalse(resultados["Ramo A"]["ok"])
        self.assertIn("error", resultados["Ramo A"])
        self.assertTrue(resultados["Ramo B"]["ok"])
        ids_publicados = [cid for cid, _, _ in self.fake_sb.publicaciones]
        self.assertEqual(ids_publicados, [CID_B])

    def test_error_de_red_en_snapshot_se_trata_igual(self):
        def snapshot_curso(api, manifest, curso_cfg, base_url):
            if curso_cfg["canvas_course_id"] == CID_A:
                raise requests.ConnectionError("sin red")
            return _snap(CID_B, "Ramo B")

        resultados = run.correr(log=self.log, sync=False,
                                 **self._kwargs(snapshot_curso))
        self.assertFalse(resultados["Ramo A"]["ok"])
        self.assertTrue(resultados["Ramo B"]["ok"])


class TestPrimeraVez(BaseRunTest):
    def test_primera_vez_segun_supabase(self):
        self.fake_sb.ya_publicados.add(CID_A)

        def snapshot_curso(api, manifest, curso_cfg, base_url):
            return _snap(curso_cfg["canvas_course_id"], curso_cfg["nombre"])

        run.correr(log=self.log, sync=False, **self._kwargs(snapshot_curso))

        por_cid = {cid: pv for cid, pv, _ in self.fake_sb.publicaciones}
        self.assertFalse(por_cid[CID_A])   # ya publicado -> primera_vez False
        self.assertTrue(por_cid[CID_B])    # nunca publicado -> primera_vez True


class TestDriveUrl(BaseRunTest):
    def test_agrega_drive_url_a_files_y_course(self):
        archivo = {"canvas_id": 1, "course_id": CID_A, "name": "a.pdf", "size": 1,
                   "modified_at": "x", "source": "modulos", "source_label": "c",
                   "canvas_url": "https://x", "ruta": "Módulos/Semana 1/a.pdf"}

        def snapshot_curso(api, manifest, curso_cfg, base_url):
            if curso_cfg["canvas_course_id"] == CID_A:
                return _snap(CID_A, "Ramo A", files=[dict(archivo)])
            return _snap(CID_B, "Ramo B")

        run.correr(log=self.log, sync=False, **self._kwargs(snapshot_curso))

        _cid, _pv, snap_a = next(p for p in self.fake_sb.publicaciones if p[0] == CID_A)
        self.assertEqual(snap_a["course"]["drive_url"],
                         "https://drive/Campus/S1/RamoA")
        self.assertEqual(snap_a["files"][0]["drive_url"],
                         "https://drive/Campus/S1/RamoA/canvas/Módulos/Semana 1/a.pdf")

    def test_drive_no_disponible_publica_sin_enlaces(self):
        def falla_drive(estado_dir):
            raise DriveNoAutorizado("sin token")

        def snapshot_curso(api, manifest, curso_cfg, base_url):
            return _snap(curso_cfg["canvas_course_id"], curso_cfg["nombre"],
                        files=[{"canvas_id": 1, "course_id": curso_cfg["canvas_course_id"],
                                "name": "a.pdf", "size": 1, "modified_at": "x",
                                "source": "archivos", "source_label": "c",
                                "canvas_url": "https://x", "ruta": "Archivos/a.pdf"}])

        resultados = run.correr(log=self.log, sync=False,
                                 **self._kwargs(snapshot_curso, conectar_drive=falla_drive))

        self.assertTrue(all(r["ok"] for r in resultados.values()))
        for _cid, _pv, snap in self.fake_sb.publicaciones:
            self.assertIsNone(snap["course"]["drive_url"])
            self.assertIsNone(snap["files"][0]["drive_url"])
        self.assertTrue(any("worker.drive" in l for l in self.lineas))
        self.assertFalse(self.enlaces_creadas)  # no se llego a construir EnlacesDrive


class TestLock(BaseRunTest):
    def test_lock_impide_corridas_solapadas(self):
        self.estado_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.estado_dir / "corrida.lock"
        lock_path.write_text(str(os.getpid()), encoding="utf-8")

        def snapshot_curso(api, manifest, curso_cfg, base_url):
            self.fail("no deberia llegar a snapshot: el lock esta tomado")

        resultados = run.correr(log=self.log, sync=False,
                                 **self._kwargs(snapshot_curso))

        self.assertEqual(resultados, {})
        self.assertTrue(any("ya hay una corrida en curso" in l for l in self.lineas))
        self.assertEqual(lock_path.read_text(encoding="utf-8"), str(os.getpid()))

    def test_lock_liberado_toma_uno_nuevo_y_funciona(self):
        self.estado_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.estado_dir / "corrida.lock"
        lock_path.write_text("999999999", encoding="utf-8")   # pid muerto -> lock abandonado

        def snapshot_curso(api, manifest, curso_cfg, base_url):
            return _snap(curso_cfg["canvas_course_id"], curso_cfg["nombre"])

        resultados = run.correr(log=self.log, sync=False,
                                 **self._kwargs(snapshot_curso))

        self.assertTrue(resultados["Ramo A"]["ok"])
        self.assertFalse(lock_path.exists())  # se libero al terminar


class TestRegistraCorrida(BaseRunTest):
    def test_registra_worker_run_ok(self):
        def snapshot_curso(api, manifest, curso_cfg, base_url):
            return _snap(curso_cfg["canvas_course_id"], curso_cfg["nombre"])

        run.correr(log=self.log, sync=False, **self._kwargs(snapshot_curso))

        self.assertEqual(self.fake_sb.runs_iniciados, 1)
        self.assertEqual(len(self.fake_sb.cerradas), 1)
        run_id, ok, summary = self.fake_sb.cerradas[0]
        self.assertEqual(run_id, 42)
        self.assertTrue(ok)
        self.assertTrue(summary["Ramo A"]["ok"])

    def test_registra_worker_run_falla_si_algun_ramo_falla(self):
        def snapshot_curso(api, manifest, curso_cfg, base_url):
            if curso_cfg["canvas_course_id"] == CID_A:
                raise LecturaFallida("boom")
            return _snap(curso_cfg["canvas_course_id"], curso_cfg["nombre"])

        run.correr(log=self.log, sync=False, **self._kwargs(snapshot_curso))

        _run_id, ok, summary = self.fake_sb.cerradas[0]
        self.assertFalse(ok)
        self.assertFalse(summary["Ramo A"]["ok"])
        self.assertTrue(summary["Ramo B"]["ok"])


class TestSync(BaseRunTest):
    def test_sync_true_llama_sincronizar_y_sigue_si_falla(self):
        llamadas = []

        def sincronizar_falla(cfg, cursos, raiz, log, manifest_path=None):
            llamadas.append((cfg, cursos, raiz, manifest_path))
            raise RuntimeError("Canvas no responde")

        def snapshot_curso(api, manifest, curso_cfg, base_url):
            return _snap(curso_cfg["canvas_course_id"], curso_cfg["nombre"])

        kwargs = self._kwargs(snapshot_curso, sincronizar=sincronizar_falla,
                              verificar_drive_root=lambda raiz, escribir=True: None)
        resultados = run.correr(log=self.log, sync=True, **kwargs)

        self.assertEqual(len(llamadas), 1)
        self.assertTrue(resultados["Ramo A"]["ok"])  # sigue publicando con el manifest existente


class TestConfigFaltante(BaseRunTest):
    def test_sin_config_supabase_lanza_error_fatal(self):
        def snapshot_curso(api, manifest, curso_cfg, base_url):
            return _snap(curso_cfg["canvas_course_id"], curso_cfg["nombre"])

        kwargs = self._kwargs(snapshot_curso, leer_env=lambda: {"DRIVE_ROOT": self.env["DRIVE_ROOT"]})
        from sync_ramos import ErrorFatal
        with self.assertRaises(ErrorFatal):
            run.correr(log=self.log, sync=False, **kwargs)


if __name__ == "__main__":
    unittest.main()
