"""Publica el snapshot de un ramo (worker/snapshot.py) en Supabase vía
PostgREST, usando la service key del trabajador. Hace upsert del curso y de
sus hijas, y poda las filas de hijas que ya no están en el snapshot.

Todas las llamadas usan `apikey`/`Authorization: Bearer <service_key>`; nunca
se registra la key ni headers en los mensajes de error.
"""
from datetime import datetime, timezone

from urllib.parse import urlencode

import requests

# Tablas hijas de un curso, podadas por (user_id, course_id) tras el upsert.
_TABLAS_HIJAS = ("announcements", "assignments", "modules", "module_items", "files")
# `inicial` solo existe en estas tres tablas (ver 0001_etapa1.sql).
_TABLAS_CON_INICIAL = ("announcements", "assignments", "files")

_TIMEOUT = 30


def _ahora_iso():
    return datetime.now(timezone.utc).isoformat()


class Supabase:
    """Cliente mínimo de PostgREST para publicar un ramo. `session` es
    inyectable (una sesión falsa en los tests); por defecto usa un
    `requests.Session` real."""

    def __init__(self, url: str, service_key: str, user_id: str, session=None):
        self._url = url.rstrip("/")
        self._service_key = service_key
        self._user_id = user_id
        self._session = session if session is not None else requests.Session()

    def _headers(self, extra=None):
        headers = {
            "apikey": self._service_key,
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _revisar(self, resp, tabla):
        if resp.status_code >= 400:
            raise RuntimeError(f"Supabase {resp.status_code} en {tabla}: {resp.text}")
        return resp

    def _upsert(self, tabla, filas):
        """POST con merge-duplicates sobre (user_id, canvas_id). Sin filas,
        no hace la llamada (pero la poda sigue corriendo)."""
        if not filas:
            return
        resp = self._session.post(
            f"{self._url}/rest/v1/{tabla}?on_conflict=user_id,canvas_id",
            json=filas,
            headers=self._headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            timeout=_TIMEOUT,
        )
        self._revisar(resp, tabla)

    def _podar(self, tabla, course_id, ids_vivos):
        filtro = f"user_id=eq.{self._user_id}&course_id=eq.{course_id}"
        if ids_vivos:
            lista = ",".join(str(i) for i in ids_vivos)
            filtro += f"&canvas_id=not.in.({lista})"
        resp = self._session.delete(
            f"{self._url}/rest/v1/{tabla}?{filtro}",
            headers=self._headers(),
            timeout=_TIMEOUT,
        )
        self._revisar(resp, tabla)

    def publicar_eventos(self, filas: list[dict], desde: str, hasta: str) -> int:
        """Upsert de los eventos de calendario y poda de los que ya no estan
        dentro de la ventana [desde, hasta). Devuelve cuantos se publicaron."""
        if filas:
            resp = self._session.post(
                f"{self._url}/rest/v1/calendar_events?on_conflict=user_id,google_id",
                json=[{**f, "user_id": self._user_id} for f in filas],
                headers=self._headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
                timeout=_TIMEOUT,
            )
            self._revisar(resp, "calendar_events")
        params = [
            ("user_id", f"eq.{self._user_id}"),
            ("start_at", f"gte.{desde}"),
            ("start_at", f"lt.{hasta}"),
        ]
        if filas:
            ids = ",".join('"' + f["google_id"].replace('"', "") + '"' for f in filas)
            params.append(("google_id", f"not.in.({ids})"))
        resp = self._session.delete(
            f"{self._url}/rest/v1/calendar_events?{urlencode(params)}",
            headers=self._headers(),
            timeout=_TIMEOUT,
        )
        self._revisar(resp, "calendar_events")
        return len(filas)

    def publicar_curso(self, snap: dict, primera_vez: bool) -> dict:
        """Upsert del curso (sin marcarlo publicado todavia), luego de sus
        hijas, y poda de hijas por (user_id, course_id). Recien si todo eso
        sale bien se marca el curso como publicado (ver `_marcar_publicado`):
        si una hija fallara en el medio, la proxima corrida tiene que verlo
        otra vez como primera publicacion, no como si ya hubiera pasado.
        Devuelve {tabla: cantidad de filas enviadas}."""
        conteos = {}
        cid = snap["course"]["canvas_id"]
        ahora = _ahora_iso()

        curso = dict(snap["course"])
        curso["user_id"] = self._user_id
        curso["updated_at"] = ahora
        self._upsert("courses", [curso])
        conteos["courses"] = 1

        for tabla in _TABLAS_HIJAS:
            filas_crudas = snap.get(tabla, [])
            filas = []
            for fila in filas_crudas:
                f = dict(fila)
                f.pop("ruta", None)
                f["user_id"] = self._user_id
                if primera_vez and tabla in _TABLAS_CON_INICIAL:
                    f["inicial"] = True
                filas.append(f)

            self._upsert(tabla, filas)
            self._podar(tabla, cid, [fila["canvas_id"] for fila in filas_crudas])
            conteos[tabla] = len(filas)

        if primera_vez:
            self._marcar_publicado(cid, ahora)

        return conteos

    def _marcar_publicado(self, cid: int, ahora: str) -> None:
        """Pone `initial_published_at` solo si todavia esta null. El filtro
        `is.null` es lo que hace esto seguro de repetir: si dos corridas se
        solaparan, la segunda no pisa la fecha que puso la primera."""
        resp = self._session.patch(
            f"{self._url}/rest/v1/courses"
            f"?user_id=eq.{self._user_id}&canvas_id=eq.{cid}&initial_published_at=is.null",
            json={"initial_published_at": ahora},
            headers=self._headers(),
            timeout=_TIMEOUT,
        )
        self._revisar(resp, "courses")

    def curso_publicado(self, canvas_id: int) -> bool:
        """True si el curso ya tiene `initial_published_at` no nulo."""
        resp = self._session.get(
            f"{self._url}/rest/v1/courses"
            f"?select=initial_published_at&user_id=eq.{self._user_id}&canvas_id=eq.{canvas_id}",
            headers=self._headers(),
            timeout=_TIMEOUT,
        )
        self._revisar(resp, "courses")
        filas = resp.json()
        return bool(filas) and filas[0].get("initial_published_at") is not None

    def iniciar_corrida(self) -> int:
        """Crea la fila de worker_runs para esta corrida y devuelve su id."""
        resp = self._session.post(
            f"{self._url}/rest/v1/worker_runs",
            json={"user_id": self._user_id, "started_at": _ahora_iso()},
            headers=self._headers({"Prefer": "return=representation"}),
            timeout=_TIMEOUT,
        )
        self._revisar(resp, "worker_runs")
        return resp.json()[0]["id"]

    def cerrar_corrida(self, run_id: int, ok: bool, summary: dict) -> None:
        resp = self._session.patch(
            f"{self._url}/rest/v1/worker_runs?id=eq.{run_id}",
            json={"finished_at": _ahora_iso(), "ok": ok, "summary": summary},
            headers=self._headers(),
            timeout=_TIMEOUT,
        )
        self._revisar(resp, "worker_runs")
