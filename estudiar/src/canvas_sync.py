"""Sincronización incremental de Canvas hacia la carpeta de Drive.

Usa la clase `Canvas` del núcleo (canvas_descargar.py) solo para leer la API.
Lo propio de este módulo:
  - manifest (id + modified_at + tamaño) para bajar solo lo nuevo o cambiado;
  - reintentos con backoff ante rate limit (429 / 403 throttle), 5xx y red;
  - destino <DRIVE_ROOT>/<semestre>/<Curso>/canvas/, ordenado por módulo;
  - syllabus.md con módulos, ítems y fechas de las tareas.
Todas las llamadas a la API son GET.
"""
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import html as _html
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils import (STATE_DIR, ErrorFatal, carpeta_curso, escribir_si_cambia,
                   guardar_json_atomico, leer_env, limpiar)
from canvas_descargar import Canvas

MANIFEST_FILE = STATE_DIR / "manifest.json"
REINTENTOS = 5
HILOS = 6  # consultas simultaneas a la API


# ---------------------------------------------------------------- HTTP

class _SesionConTimeout(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", (15, 120))
        return super().request(*args, **kwargs)


def conectar():
    env = leer_env()
    base = env.get("CANVAS_BASE_URL") or env.get("CANVAS_URL")
    token = env.get("CANVAS_TOKEN")
    if not base or not token:
        raise ErrorFatal("Faltan CANVAS_URL (o CANVAS_BASE_URL) y CANVAS_TOKEN en el .env.")
    api = Canvas(base.rstrip("/"), token)
    s = _SesionConTimeout()
    s.headers.update(api.s.headers)
    reintento = Retry(total=REINTENTOS, connect=REINTENTOS, read=3, backoff_factor=1.5,
                      status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=frozenset({"GET", "HEAD"}),
                      respect_retry_after_header=True, raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=reintento))
    s.mount("http://", HTTPAdapter(max_retries=reintento))
    api.s = s
    return api


def _get(api, url, **kwargs):
    """GET con reintento extra para el 403 de throttling de Canvas (el adaptador
    ya cubre 429, 5xx y errores de conexión)."""
    for intento in range(REINTENTOS):
        r = api.s.get(url, **kwargs)
        if r.status_code == 403 and re.search(r"rate limit|throttl", r.text, re.I):
            r.close()
            time.sleep(2 * (intento + 1))
            continue
        return r
    return r


def _get_json(api, path):
    r = _get(api, f"{api.base}{path}")
    r.raise_for_status()
    return r.json()


def _meta_archivo(api, cid, fid):
    try:
        return _get_json(api, f"/api/v1/courses/{cid}/files/{fid}")
    except requests.HTTPError:
        # En algunos cursos el archivo solo se resuelve por su id global.
        return _get_json(api, f"/api/v1/files/{fid}")


def _descargar(api, url, destino):
    """Baja a un .part y lo renombra al terminar: nunca quedan archivos a medias."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")
    ultimo = None
    for intento in range(3):
        try:
            with _get(api, url, stream=True) as r:
                r.raise_for_status()
                with open(parcial, "wb") as fh:
                    for chunk in r.iter_content(65536):
                        fh.write(chunk)
            os.replace(parcial, destino)
            return
        except (requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            ultimo = e
            time.sleep(3 * (intento + 1))
        finally:
            if parcial.exists():
                try:
                    parcial.unlink()
                except OSError:
                    pass
    raise ultimo


# ---------------------------------------------------------------- manifest

class Manifest:
    def __init__(self, path=MANIFEST_FILE):
        import json
        self.path = Path(path)
        self.datos = {"version": 1, "cursos": {}}
        if self.path.exists():
            self.datos = json.loads(self.path.read_text(encoding="utf-8"))

    def curso(self, cid):
        c = self.datos["cursos"].setdefault(str(cid), {})
        c.setdefault("archivos", {})
        c.setdefault("paginas", {})
        return c

    def guardar(self):
        guardar_json_atomico(self.path, self.datos)


# ---------------------------------------------------------------- sync

class _SyncCurso:
    def __init__(self, api, manifest, curso, dir_curso, fuentes, log, dry_run):
        self.api = api
        self.manifest = manifest
        self.cfg = curso
        self.cid = curso["canvas_course_id"]
        self.dir_curso = Path(dir_curso)
        self.dir_canvas = self.dir_curso / "canvas"
        self.fuentes = set(fuentes)
        self.log = log
        self.dry_run = dry_run
        self.estado = manifest.curso(self.cid)
        self.vistos = set()
        self.rutas_usadas = {}   # ruta relativa -> file id (esta ejecución)
        self.resumen = {"nuevos": [], "actualizados": [], "sin_cambios": 0,
                        "omitidos": [], "errores": []}
        self.indice = {"modulos": [], "tareas": [], "archivos_sueltos": []}
        self._metas = {}     # file id -> metadatos precargados
        self._paginas = {}   # page_url -> página precargada

    def _estado(self, texto):
        """Línea de avance que se sobrescribe (solo en terminal, no va al log)."""
        if sys.stdout.isatty():
            print(f"\r  {texto[:70]:<70}", end="", flush=True)

    def _limpiar_estado(self):
        if sys.stdout.isatty():
            print("\r" + " " * 72 + "\r", end="", flush=True)

    # ---- archivos

    def _ruta_libre(self, fid, rel):
        """Evita que dos archivos distintos con el mismo nombre se pisen."""
        otros = {str(k) for k, v in self.estado["archivos"].items()
                 if v.get("ruta") == rel and str(k) != str(fid)}
        usado = self.rutas_usadas.get(rel)
        if otros or (usado is not None and usado != fid):
            p = Path(rel)
            rel = p.with_name(f"{p.stem} ({fid}){p.suffix}").as_posix()
        self.rutas_usadas[rel] = fid
        return rel

    def archivo(self, fid, meta, subdir, contexto):
        """Procesa un archivo de Canvas. `subdir` es relativo a canvas/."""
        if fid in self.vistos:
            return None
        self.vistos.add(fid)
        try:
            if meta is None or "url" not in meta:
                meta = self._metas.get(fid) or _meta_archivo(self.api, self.cid, fid)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403, 404):
                self.resumen["omitidos"].append(f"archivo {fid} ({contexto}): sin acceso en Canvas")
            else:
                self.resumen["errores"].append(f"{contexto}: archivo {fid}: {e}")
            return None
        nombre = limpiar(meta.get("display_name") or meta.get("filename") or f"archivo_{fid}")
        clave = str(fid)
        previo = self.estado["archivos"].get(clave)
        firma = (meta.get("modified_at") or meta.get("updated_at"), meta.get("size"))

        if previo and (previo.get("modified_at"), previo.get("size")) == firma \
                and (self.dir_canvas / previo["ruta"]).exists():
            self.resumen["sin_cambios"] += 1
            self.rutas_usadas[previo["ruta"]] = fid
            return previo["ruta"]

        if not meta.get("url"):
            self.resumen["omitidos"].append(f"{nombre} ({contexto}): bloqueado o sin URL en Canvas")
            return None

        rel = previo["ruta"] if previo else self._ruta_libre(fid, (Path(subdir) / nombre).as_posix())
        tipo = "actualizados" if previo else "nuevos"
        entrada = {"ruta": rel, "modulo": contexto}
        if self.dry_run:
            self.resumen[tipo].append(entrada)
            self.log(f"  (dry-run) {'↻' if previo else '↓'} {rel}")
            return rel
        try:
            _descargar(self.api, meta["url"], self.dir_canvas / rel)
        except Exception as e:
            self.resumen["errores"].append(f"{rel}: {e}")
            self.log(f"  ✗ {rel}: {e}")
            return None
        self.estado["archivos"][clave] = {
            "ruta": rel, "modified_at": firma[0], "size": firma[1], "contexto": contexto,
            "descargado_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.manifest.guardar()
        self.resumen[tipo].append(entrada)
        self.log(f"  {'↻' if previo else '↓'} {rel}")
        return rel

    def archivos_embebidos(self, body, subdir, contexto):
        for fid in sorted({int(x) for x in re.findall(r"/files/(\d+)", body or "")}):
            self.archivo(fid, None, subdir, contexto)

    # ---- snapshots HTML (páginas y enunciados)

    def snapshot(self, clave, rel, titulo, body, actualizado):
        if not body:
            return
        previo = self.estado["paginas"].get(clave)
        destino = self.dir_canvas / rel
        if previo and previo.get("updated_at") == actualizado and destino.exists():
            return
        if self.dry_run:
            self.log(f"  (dry-run) ↓ [html] {rel}")
            return
        html = ('<!doctype html><html><head><meta charset="utf-8">'
                f"<title>{_html.escape(titulo)}</title></head><body>"
                f"<h1>{_html.escape(titulo)}</h1>{body}</body></html>")
        if escribir_si_cambia(destino, html):
            self.log(f"  ↓ [html] {rel}")
        self.estado["paginas"][clave] = {"ruta": rel, "updated_at": actualizado}
        self.manifest.guardar()

    # ---- fuentes

    def modulos(self, meta_por_id):
        try:
            mods = self.api.modulos(self.cid)
        except requests.HTTPError:
            self.log("  (sin Módulos accesibles)")
            return
        self._estado(f"leyendo {len(mods)} módulos…")
        items_por_modulo = self._precargar(mods, meta_por_id)
        for m, items in zip(mods, items_por_modulo):
            mname = limpiar(m.get("name", "modulo"))
            subdir = Path("Módulos") / mname
            ficha = {"nombre": m.get("name"), "desbloqueo": m.get("unlock_at"), "items": []}
            self.indice["modulos"].append(ficha)
            if items is None:
                continue
            for it in items:
                tipo = it.get("type")
                item = {"titulo": it.get("title"), "tipo": tipo, "ruta": None}
                ficha["items"].append(item)
                try:
                    if tipo == "File":
                        fid = it.get("content_id")
                        item["ruta"] = self.archivo(fid, meta_por_id.get(fid), subdir, m.get("name"))
                        if item["ruta"] is None and fid in self.vistos:
                            prev = self.estado["archivos"].get(str(fid))
                            item["ruta"] = prev and prev.get("ruta")
                    elif tipo == "Page":
                        pag = self._paginas.get(it["page_url"]) or _get_json(
                            self.api, f"/api/v1/courses/{self.cid}/pages/{it['page_url']}")
                        titulo = pag.get("title") or it.get("title") or "pagina"
                        rel = (subdir / f"{limpiar(titulo)}.html").as_posix()
                        self.snapshot(f"page:{pag.get('page_id') or it['page_url']}", rel,
                                      titulo, pag.get("body"), pag.get("updated_at"))
                        item["ruta"] = rel if pag.get("body") else None
                        self.archivos_embebidos(pag.get("body"), subdir, m.get("name"))
                    elif tipo == "ExternalUrl":
                        item["url"] = it.get("external_url")
                except (requests.HTTPError, KeyError) as e:
                    self.resumen["errores"].append(f"ítem '{it.get('title')}': {e}")

    def _precargar(self, mods, meta_por_id):
        """Pide en paralelo los ítems de cada módulo y luego los metadatos de
        archivos y páginas que hagan falta. Los errores se dejan para el
        recorrido normal, que los reporta."""
        def items(m):
            try:
                return self.api.items_modulo(self.cid, m["id"])
            except requests.HTTPError:
                return None

        def meta(fid):
            try:
                return fid, _meta_archivo(self.api, self.cid, fid)
            except requests.RequestException:
                return fid, None

        def pagina(url):
            try:
                return url, _get_json(self.api, f"/api/v1/courses/{self.cid}/pages/{url}")
            except requests.RequestException:
                return url, None

        with ThreadPoolExecutor(HILOS) as ex:
            por_modulo = list(ex.map(items, mods))
            todos = [it for its in por_modulo if its for it in its]
            fids = {it.get("content_id") for it in todos
                    if it.get("type") == "File" and it.get("content_id") not in meta_por_id}
            urls = {it["page_url"] for it in todos if it.get("type") == "Page" and it.get("page_url")}
            self._estado(f"revisando {len(fids)} archivos y {len(urls)} páginas…")
            self._metas.update((f, m) for f, m in ex.map(meta, fids) if m)
            self._paginas.update((u, p) for u, p in ex.map(pagina, urls) if p)
        return por_modulo

    def archivos_tab(self, meta_por_id, carpetas):
        """Archivos de la pestaña Archivos que no aparecen en ningún módulo."""
        for fid, a in meta_por_id.items():
            if fid in self.vistos:
                continue
            carpeta = re.sub(r"^course files/?", "", carpetas.get(a.get("folder_id"), ""))
            subdir = Path("Archivos", *[limpiar(p) for p in carpeta.split("/") if p])
            rel = self.archivo(fid, a, subdir, f"Archivos/{carpeta}".rstrip("/"))
            if rel:
                self.indice["archivos_sueltos"].append(rel)

    def tareas(self):
        try:
            tareas = self.api.tareas(self.cid)
        except requests.HTTPError:
            self.log("  (sin Tareas accesibles)")
            return
        for t in tareas:
            tname = limpiar(t.get("name", f"tarea_{t['id']}"))
            subdir = Path("Tareas") / tname
            self.indice["tareas"].append({"nombre": t.get("name"), "entrega": t.get("due_at"),
                                          "desbloqueo": t.get("unlock_at")})
            self.snapshot(f"assignment:{t['id']}", (subdir / "enunciado.html").as_posix(),
                          t.get("name") or tname, t.get("description"), t.get("updated_at"))
            self.archivos_embebidos(t.get("description"), subdir, f"Tarea: {t.get('name')}")

    # ---- orquestación

    def ejecutar(self):
        meta_por_id, carpetas = {}, {}
        if {"archivos", "modulos"} & self.fuentes:
            try:
                carpetas = self.api.carpetas(self.cid)
                meta_por_id = {a["id"]: a for a in self.api.archivos(self.cid)}
            except requests.HTTPError:
                pass  # pestaña Archivos oculta: se resuelve archivo por archivo
        if "modulos" in self.fuentes:
            self.modulos(meta_por_id)
            self._limpiar_estado()
        if "archivos" in self.fuentes:
            self.archivos_tab(meta_por_id, carpetas)
        if "tareas" in self.fuentes:
            self._estado("revisando tareas…")
            self.tareas()
            self._limpiar_estado()
        r = self.resumen
        self.log(f"  → {len(r['nuevos'])} nuevos, {len(r['actualizados'])} actualizados, "
                 f"{r['sin_cambios']} sin cambios")
        if not self.dry_run:
            self.escribir_syllabus()
            self.manifest.guardar()
        return self.resumen

    def escribir_syllabus(self):
        def fecha(iso):
            return iso[:10] if iso else "—"
        lineas = [f"# {self.cfg['nombre']} — índice de Canvas",
                  "",
                  "Generado automáticamente en cada sincronización. Las rutas son relativas a `canvas/`.",
                  ""]
        claves = re.compile(r"calendariz|programa|syllabus", re.I)
        destacados = [v["ruta"] for v in self.estado["archivos"].values()
                      if claves.search(Path(v["ruta"]).name)]
        if destacados:
            lineas += ["## Calendarización y programa", ""]
            lineas += [f"- `{r}`" for r in sorted(destacados)] + [""]
        lineas += ["## Módulos", ""]
        for m in self.indice["modulos"]:
            extra = f" (desde {fecha(m['desbloqueo'])})" if m.get("desbloqueo") else ""
            lineas.append(f"### {m['nombre']}{extra}")
            for it in m["items"]:
                if it["tipo"] == "SubHeader":
                    lineas.append(f"- **{it['titulo']}**")
                elif it.get("ruta"):
                    lineas.append(f"- {it['titulo']} — `{it['ruta']}`")
                elif it.get("url"):
                    lineas.append(f"- {it['titulo']} — enlace externo")
                else:
                    lineas.append(f"- {it['titulo']} ({it['tipo']})")
            lineas.append("")
        if self.indice["tareas"]:
            lineas += ["## Tareas y evaluaciones en Canvas", ""]
            orden = sorted(self.indice["tareas"], key=lambda t: t.get("entrega") or "9999")
            for t in orden:
                lineas.append(f"- {fecha(t.get('entrega'))} — {t['nombre']}")
            lineas.append("")
        if self.indice["archivos_sueltos"]:
            lineas += ["## Archivos fuera de módulos", ""]
            lineas += [f"- `{r}`" for r in sorted(self.indice["archivos_sueltos"])] + [""]
        escribir_si_cambia(self.dir_curso / "syllabus.md", "\n".join(lineas))


def sincronizar(cfg, cursos, drive_root, log, dry_run=False, manifest_path=MANIFEST_FILE):
    """Sincroniza los cursos indicados. Devuelve {nombre_curso: resumen}."""
    api = conectar()
    manifest = Manifest(manifest_path)
    resultados = {}
    for curso in cursos:
        log(f"\n=== {curso['nombre']} (Canvas {curso['canvas_course_id']}) ===")
        dir_curso = carpeta_curso(drive_root, cfg, curso)
        sync = _SyncCurso(api, manifest, curso, dir_curso, cfg["canvas"]["fuentes"], log, dry_run)
        try:
            resultados[curso["nombre"]] = sync.ejecutar()
        except requests.RequestException as e:
            log(f"  ✗ No se pudo sincronizar este curso: {e}")
            sync.resumen["errores"].append(f"curso completo: {e}")
            resultados[curso["nombre"]] = sync.resumen
        finally:
            if not dry_run:
                manifest.guardar()
    return resultados


def imprimir_resumen(resultados, log, dry_run=False):
    log("\n──────── Resumen de sincronización ────────")
    for nombre, r in resultados.items():
        verbo = "se bajarían" if dry_run else "nuevos"
        linea = (f"  {nombre}: {len(r['nuevos'])} {verbo}, {len(r['actualizados'])} actualizados, "
                 f"{r['sin_cambios']} sin cambios")
        if r["omitidos"]:
            linea += f", {len(r['omitidos'])} omitidos"
        if r["errores"]:
            linea += f", {len(r['errores'])} errores"
        log(linea)
        for e in r["errores"][:5]:
            log(f"      ✗ {e}")
