"""Tests de canvas_gui._ejecutar_sync: cuando hay config de Supabase, delega
en worker.run.correr (sin red: sync_ramos y worker.run se inyectan con
mock.patch, como en tests/test_escaneo_api.py)."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import canvas_gui  # noqa: E402
import worker.run as _worker_run  # noqa: E402


class TestEjecutarSyncConSupabase(unittest.TestCase):
    def setUp(self):
        canvas_gui._resumen = None
        canvas_gui._dest_actual = ""

    def _correr(self, manifest_env):
        cfg = {"semestre": "S1", "cursos": []}
        raiz = Path("Z:/Mi unidad/Campus")
        llamadas = {}

        def correr_falso(log, manifest_path=None):
            llamadas["manifest_path"] = manifest_path
            return {}

        entorno = {"SYNC_MANIFEST": manifest_env} if manifest_env else {}
        with mock.patch.object(canvas_gui, "_preparar_sync", return_value=(cfg, raiz)), \
                mock.patch.object(canvas_gui, "_tiene_config_supabase", return_value=True), \
                mock.patch.object(_worker_run, "correr", side_effect=correr_falso), \
                mock.patch.dict(os.environ, entorno, clear=False):
            canvas_gui._ejecutar_sync()
        return llamadas

    def test_pasa_sync_manifest_del_entorno_a_correr(self):
        llamadas = self._correr("Z:/tmp/manifest_prueba.json")
        self.assertEqual(llamadas["manifest_path"], "Z:/tmp/manifest_prueba.json")

    def test_sin_sync_manifest_no_manda_override(self):
        os.environ.pop("SYNC_MANIFEST", None)
        llamadas = self._correr(None)
        self.assertIsNone(llamadas["manifest_path"])


if __name__ == "__main__":
    unittest.main()
