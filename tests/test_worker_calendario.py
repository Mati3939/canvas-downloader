import unittest
from datetime import datetime, timezone

from worker import calendario


def _evento(**kw):
    base = {
        "id": "e1",
        "summary": "Clase",
        "start": {"dateTime": "2026-11-03T08:30:00-03:00"},
        "end": {"dateTime": "2026-11-03T10:00:00-03:00"},
    }
    base.update(kw)
    return base


class TestClasificar(unittest.TestCase):
    def test_marca_en_descripcion_es_clase(self):
        self.assertEqual(
            calendario.clasificar(_evento(description="[Horario Semestre 4]"), "[Horario"),
            "clase",
        )

    def test_palabras_de_evaluacion(self):
        for titulo in ("Certamen 2 TOPD", "Prueba 1 Calculo", "Control 3",
                       "Examen final", "Evaluacion grupal", "Entrega informe"):
            self.assertEqual(calendario.clasificar(_evento(summary=titulo), "[Horario"),
                             "evaluacion", titulo)

    def test_otro_evento_no_se_publica(self):
        self.assertIsNone(calendario.clasificar(_evento(summary="Almuerzo"), "[Horario"))
        self.assertIsNone(calendario.clasificar(_evento(summary="Controlador"), "[Horario"))


class TestFilaEvento(unittest.TestCase):
    def test_fila_con_hora(self):
        fila = calendario.fila_evento(
            _evento(summary="Certamen 2", location="Sala 1", htmlLink="https://cal/x"),
            "[Horario",
        )
        self.assertEqual(fila["google_id"], "e1")
        self.assertEqual(fila["kind"], "evaluacion")
        self.assertEqual(fila["start_at"], "2026-11-03T08:30:00-03:00")
        self.assertFalse(fila["all_day"])
        self.assertEqual(fila["location"], "Sala 1")

    def test_dia_completo(self):
        fila = calendario.fila_evento(
            _evento(summary="Entrega proyecto", start={"date": "2026-11-06"},
                    end={"date": "2026-11-07"}),
            "[Horario",
        )
        self.assertTrue(fila["all_day"])
        self.assertEqual(fila["start_at"], "2026-11-06T04:00:00Z")

    def test_cancelado_se_omite(self):
        self.assertIsNone(calendario.fila_evento(
            _evento(summary="Certamen", status="cancelled"), "[Horario"))


class _Servicio:
    def __init__(self, paginas):
        self.paginas = paginas
        self.llamadas = []

    def events(self):
        return self

    def list(self, **kw):
        self.llamadas.append(kw)
        return self

    def execute(self):
        return self.paginas[len(self.llamadas) - 1]


class TestLeerEventos(unittest.TestCase):
    def test_pagina_y_filtra(self):
        servicio = _Servicio([
            {"items": [_evento(id="a", description="[Horario"), _evento(id="b")],
             "nextPageToken": "t2"},
            {"items": [_evento(id="c", summary="Certamen")]},
        ])
        desde = datetime(2026, 11, 1, tzinfo=timezone.utc)
        hasta = datetime(2026, 12, 1, tzinfo=timezone.utc)
        filas = calendario.leer_eventos(servicio, desde, hasta, "[Horario")
        self.assertEqual([f["google_id"] for f in filas], ["a", "c"])
        self.assertEqual(servicio.llamadas[0]["calendarId"], "primary")
        self.assertTrue(servicio.llamadas[0]["singleEvents"])
        self.assertEqual(servicio.llamadas[1]["pageToken"], "t2")


if __name__ == "__main__":
    unittest.main()
