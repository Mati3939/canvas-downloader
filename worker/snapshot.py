"""Snapshot de un ramo desde Canvas: lee el curso, sus anuncios, tareas,
módulos/ítems y los archivos ya bajados (del manifest de sync_ramos), y arma
las filas que worker/supabase.py publica en Supabase.

Todas las llamadas a la API son GET (vía canvas_descargar.Canvas).
"""
from pathlib import PurePosixPath

import requests

# Primer tramo de la ruta del manifest (relativa a canvas/) -> columna `source`.
_ORIGEN_POR_CARPETA = {
    "Módulos": "modulos",
    "Anuncios": "anuncios",
    "Archivos": "archivos",
    "Tareas": "tareas",
    "Mensajes": "mensajes",
}

_ROLES_AYUDANTIA = {"teacher", "ta", "designer"}


class LecturaFallida(Exception):
    """Falló leer módulos, tareas o anuncios del ramo por algo distinto de una
    pestaña oculta (401/403/404). El worker no debe podar el ramo en Supabase
    con datos parciales: hay que reintentar."""


def _listar_o_vacio(fn):
    """Ejecuta un listado de Canvas. Un 401/403/404 significa que esa pestaña
    está oculta para este usuario -> lista vacía. Cualquier otro error HTTP o
    de red es una lectura fallida real."""
    try:
        return fn()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status in (401, 403, 404):
            return []
        raise LecturaFallida(str(e)) from e
    except requests.RequestException as e:
        raise LecturaFallida(str(e)) from e


def _rol(enrollments):
    tipos = {e.get("type") for e in (enrollments or [])}
    return "ta" if tipos & _ROLES_AYUDANTIA else "student"


def _fila_curso(curso_canvas, curso_cfg, cid, base_url):
    return {
        "canvas_id": cid,
        "name": curso_cfg["nombre"],
        "role": _rol(curso_canvas.get("enrollments")),
        "canvas_url": f"{base_url}/courses/{cid}",
        "position": curso_cfg.get("position"),
    }


def _fila_anuncio(topic, cid):
    return {
        "canvas_id": topic["id"],
        "course_id": cid,
        "title": topic.get("title") or "",
        "message_html": topic.get("message") or "",
        "posted_at": topic.get("posted_at"),
        "canvas_url": topic.get("html_url"),
        "attachment_ids": [a["id"] for a in (topic.get("attachments") or [])],
    }


def _fila_tarea(t, cid):
    return {
        "canvas_id": t["id"],
        "course_id": cid,
        "name": t.get("name") or "",
        "description_html": t.get("description") or "",
        "canvas_due_at": t.get("due_at"),
        "unlock_at": t.get("unlock_at"),
        "canvas_created_at": t.get("created_at"),
        "canvas_url": t.get("html_url"),
    }


def _fila_modulo(m, cid):
    return {
        "canvas_id": m["id"],
        "course_id": cid,
        "name": m.get("name") or "",
        "position": m.get("position"),
        "unlock_at": m.get("unlock_at"),
    }


def _fila_item_modulo(item, mid, cid):
    tipo = item.get("type")
    return {
        "canvas_id": item["id"],
        "course_id": cid,
        "module_id": mid,
        "position": item.get("position"),
        "title": item.get("title") or "",
        "type": tipo,
        "file_id": item.get("content_id") if tipo == "File" else None,
        "external_url": item.get("external_url") if tipo == "ExternalUrl" else None,
        "canvas_url": item.get("html_url") or None,
    }


def _fila_archivo(fid, entrada, cid, base_url):
    ruta = entrada["ruta"]
    carpeta = PurePosixPath(ruta).parts[0]
    source = _ORIGEN_POR_CARPETA.get(carpeta, carpeta.lower())
    return {
        "canvas_id": fid,
        "course_id": cid,
        "name": PurePosixPath(ruta).name,
        "size": entrada.get("size"),
        "modified_at": entrada.get("modified_at"),
        "source": source,
        "source_label": entrada.get("contexto"),
        "canvas_url": f"{base_url}/courses/{cid}/files/{fid}",
        "ruta": ruta,
    }


def snapshot_curso(api, manifest, curso_cfg, base_url):
    """Lee de Canvas y del manifest todo lo necesario para publicar un ramo.
    Devuelve un dict con las filas (listas de dict, sin user_id/inicial/
    first_seen_at/drive_url) para `course`, `announcements`, `assignments`,
    `modules`, `module_items` y `files`.
    """
    cid = curso_cfg["canvas_course_id"]

    curso_canvas = api.curso(cid)
    course = _fila_curso(curso_canvas, curso_cfg, cid, base_url)

    topics = _listar_o_vacio(lambda: api.discusiones(cid, solo_anuncios=True))
    # Un anuncio demorado (delayed_post_at futuro) tiene posted_at null hasta
    # que se publica; el rol ayudante lo ve igual en Canvas, pero la columna
    # posted_at de Supabase es not null.
    announcements = [_fila_anuncio(t, cid) for t in topics if t.get("posted_at")]

    tareas = _listar_o_vacio(lambda: api.tareas(cid))
    assignments = [_fila_tarea(t, cid) for t in tareas]

    mods = _listar_o_vacio(lambda: api.modulos(cid))
    modules = [_fila_modulo(m, cid) for m in mods]
    module_items = []
    for m in mods:
        mid = m["id"]
        items = _listar_o_vacio(lambda mid=mid: api.items_modulo(cid, mid))
        for it in items:
            module_items.append(_fila_item_modulo(it, mid, cid))

    entradas = manifest.curso(cid).get("archivos", {})
    files = [_fila_archivo(int(fid), entrada, cid, base_url)
             for fid, entrada in entradas.items()
             if entrada.get("size") is not None and entrada.get("modified_at")]

    return {
        "course": course,
        "announcements": announcements,
        "assignments": assignments,
        "modules": modules,
        "module_items": module_items,
        "files": files,
    }
