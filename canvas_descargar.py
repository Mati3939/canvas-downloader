#!/usr/bin/env python3
"""
Descargador de archivos del Canvas LMS.
Baja archivos de tus cursos preservando la estructura, saltando lo ya descargado.
Funciona aunque el curso NO tenga pestaña "Archivos": también recorre los MÓDULOS
(items de tipo File y archivos embebidos en Páginas) y, opcionalmente, las TAREAS
(archivos adjuntos al enunciado y, si se pide, tus propias entregas), los ANUNCIOS
y las DISCUSIONES (adjuntos y archivos embebidos). Además guarda snapshots HTML del
contenido escrito (páginas, enunciados de tareas, mensajes de anuncios/discusiones).
Pensado para alimentar el banco de conocimiento (p. ej. Física, cuyo material vive
en Módulos).

USO:
  1. Generá un token en Canvas:
       Cuenta -> Configuración -> Tokens de acceso aprobados -> "+ Nuevo token de acceso"
  2. Configurá la conexión, con cualquiera de estas opciones (prioridad: variables de
     entorno > canvas_config.json > archivo .env en esta carpeta):
       CANVAS_BASE_URL = https://TU-INSTITUCION.instructure.com   (sin / final)
       CANVAS_TOKEN    = tu_token
  3. Listar cursos:              python canvas_descargar.py --listar
     Incluir cursos pasados:     python canvas_descargar.py --listar --incluir-pasados
     Descargar uno:              python canvas_descargar.py --curso 12345
     Descargar varios:           python canvas_descargar.py --curso 12345 67890
     Descargar todos:            python canvas_descargar.py --todos
     Filtrar por nombre:         python canvas_descargar.py --todos --filtro fisica
     Solo módulos:               python canvas_descargar.py --curso 12345 --solo-modulos
     Solo archivos:              python canvas_descargar.py --curso 12345 --solo-archivos
     Solo tareas:                python canvas_descargar.py --curso 12345 --solo-tareas
     Sumar tareas a lo demás:    python canvas_descargar.py --curso 12345 --tareas
     Sumar mis entregas:         python canvas_descargar.py --curso 12345 --entregas
     Sumar anuncios:             python canvas_descargar.py --curso 12345 --anuncios
     Sumar discusiones:          python canvas_descargar.py --curso 12345 --discusiones
     Organizar por término:      python canvas_descargar.py --todos --por-termino
  4. Interfaz gráfica:           python canvas_gui.py   (abre una interfaz web)

Por defecto descarga de AMBAS fuentes (archivos + módulos) sin duplicar.
Salida: ../Archivos oficiales/Canvas (descarga)/<Curso>/<carpetas>/...
"""
import os, sys, json, time, argparse, re
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Falta 'requests'. Instalá con:  pip install requests")

# La consola de Windows (cp1252) no puede imprimir acentos ni símbolos:
# forzamos UTF-8 en la salida para evitar UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "canvas_config.json"
DOTENV_FILE = HERE / ".env"
DEFAULT_DEST = HERE.parent / "Archivos oficiales" / "Canvas (descarga)"


def _leer_dotenv(path):
    """Parsea un archivo .env simple (líneas CLAVE=valor). No falla si no existe."""
    valores = {}
    if not path.exists():
        return valores
    for linea in path.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
            valor = valor[1:-1]
        if clave:
            valores[clave] = valor
    return valores


def cargar_config():
    # Prioridad: variables de entorno > canvas_config.json > .env
    # CANVAS_URL se acepta como alias de CANVAS_BASE_URL.
    base = os.environ.get("CANVAS_BASE_URL") or os.environ.get("CANVAS_URL")
    token = os.environ.get("CANVAS_TOKEN")
    if CONFIG_FILE.exists():
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        base = base or cfg.get("base_url")
        token = token or cfg.get("token")
    if not base or not token:
        dotenv = _leer_dotenv(DOTENV_FILE)
        base = base or dotenv.get("CANVAS_BASE_URL") or dotenv.get("CANVAS_URL")
        token = token or dotenv.get("CANVAS_TOKEN")
    if not base or not token:
        sys.exit(
            "Falta configuración. Definí CANVAS_BASE_URL y CANVAS_TOKEN como variables\n"
            f"de entorno, o creá {CONFIG_FILE} con:\n"
            '  {"base_url": "https://tu-institucion.instructure.com", "token": "xxxx"}\n'
            f"o creá {DOTENV_FILE} con:\n"
            "  CANVAS_BASE_URL=https://tu-institucion.instructure.com\n"
            "  CANVAS_TOKEN=xxxx"
        )
    return base.rstrip("/"), token


def limpiar(nombre):
    return re.sub(r'[<>:"/\\|?*]', "_", str(nombre)).strip() or "sin_nombre"


class Canvas:
    def __init__(self, base, token):
        self.base = base
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    # ---- HTTP con paginación y reintento por throttling ----
    def _paginar(self, url, params=None):
        params = dict(params or {})
        params.setdefault("per_page", 100)
        items = []
        while url:
            for intento in range(4):
                r = self.s.get(url, params=params)
                if r.status_code == 403 and "throttle" in r.text.lower():
                    time.sleep(2 * (intento + 1)); continue
                r.raise_for_status(); break
            else:
                r.raise_for_status()
            data = r.json()
            items.extend(data if isinstance(data, list) else [data])
            url, params = self._siguiente(r), None
        return items

    @staticmethod
    def _siguiente(r):
        for parte in r.headers.get("Link", "").split(","):
            m = re.search(r'<([^>]+)>;\s*rel="next"', parte)
            if m:
                return m.group(1)
        return None

    def _get_json(self, path):
        r = self.s.get(f"{self.base}{path}")
        r.raise_for_status()
        return r.json()

    # ---- Endpoints ----
    def cursos(self):
        return self._paginar(f"{self.base}/api/v1/courses",
                             {"enrollment_state": "active", "include[]": "term"})

    def cursos_pasados(self):
        """Cursos con inscripciones pasadas/concluidas (mismo formato que cursos())."""
        cursos = self._paginar(f"{self.base}/api/v1/courses",
                               {"enrollment_state": "completed", "include[]": "term",
                                "per_page": 100})
        resultado = []
        for c in cursos:
            if "id" not in c:
                continue
            if "name" not in c:
                # Canvas puede devolver cursos con acceso restringido por fecha,
                # sin nombre, p. ej. {"access_restricted_by_date": true, "id": ...}
                c["name"] = f"(curso restringido {c['id']})"
            resultado.append(c)
        return resultado

    def carpetas(self, cid):
        fs = self._paginar(f"{self.base}/api/v1/courses/{cid}/folders")
        return {f["id"]: f.get("full_name", "files") for f in fs}

    def carpetas_detalle(self, cid):
        """Lista cruda de carpetas del curso (id, name, full_name, parent_folder_id, ...)."""
        try:
            return self._paginar(f"{self.base}/api/v1/courses/{cid}/folders")
        except requests.HTTPError:
            return []

    def archivos(self, cid):
        return self._paginar(f"{self.base}/api/v1/courses/{cid}/files")

    def modulos(self, cid):
        return self._paginar(f"{self.base}/api/v1/courses/{cid}/modules")

    def items_modulo(self, cid, mid):
        return self._paginar(f"{self.base}/api/v1/courses/{cid}/modules/{mid}/items",
                             {"include[]": "content_details"})

    def archivo(self, cid, fid):
        return self._get_json(f"/api/v1/courses/{cid}/files/{fid}")

    def pagina(self, cid, page_url):
        return self._get_json(f"/api/v1/courses/{cid}/pages/{page_url}")

    def tareas(self, cid):
        return self._paginar(f"{self.base}/api/v1/courses/{cid}/assignments")

    def entrega(self, cid, aid):
        """Mi entrega (submission) de una tarea, con el historial de intentos."""
        r = self.s.get(f"{self.base}/api/v1/courses/{cid}/assignments/{aid}/submissions/self",
                       params={"include[]": "submission_history"})
        r.raise_for_status()
        return r.json()

    def discusiones(self, cid, solo_anuncios=False):
        """Temas de discusión del curso. Canvas modela los anuncios como
        discussion_topics con only_announcements=true; sin ese flag el endpoint
        devuelve SOLO discusiones (no incluye anuncios), así que no hay duplicados."""
        params = {"only_announcements": "true"} if solo_anuncios else None
        return self._paginar(f"{self.base}/api/v1/courses/{cid}/discussion_topics", params)


def bajar(api, url, destino, size=-1):
    """Descarga una URL a destino. Devuelve True si bajó, False si ya existía."""
    if not url:
        # Canvas devuelve url vacía cuando el archivo está bloqueado/restringido
        raise ValueError("archivo bloqueado o restringido (Canvas no da URL de descarga)")
    if destino.exists() and size >= 0 and destino.stat().st_size == size:
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    with api.s.get(url, stream=True) as r:
        r.raise_for_status()
        with open(destino, "wb") as fh:
            for chunk in r.iter_content(8192):
                fh.write(chunk)
    return True


def guardar_html(destino, titulo, body_html, log=print):
    """Guarda un snapshot HTML standalone del contenido escrito (página, enunciado,
    mensaje). No hace nada si el body está vacío o si el archivo ya existe con el
    mismo contenido. Los snapshots NO suman a los contadores bajados/saltados."""
    if not body_html:
        return
    html = ('<!doctype html><html><head><meta charset="utf-8">'
            f"<title>{titulo}</title></head><body><h1>{titulo}</h1>"
            f"{body_html}</body></html>")
    if destino.exists():
        try:
            if destino.read_text(encoding="utf-8") == html:
                return
        except Exception:
            pass  # si no se puede leer/comparar, lo reescribimos
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    log(f"  ↓ [html] {destino.name}")


def descargar_por_archivos(api, cid, cname, dest_root, vistos, carpetas_ids=None, log=print):
    bajados = saltados = 0
    try:
        rutas = api.carpetas(cid)
        archivos = api.archivos(cid)
    except requests.HTTPError:
        log("  (sin pestaña Archivos accesible)")
        return 0, 0
    for a in archivos:
        if carpetas_ids is not None and a.get("folder_id") not in carpetas_ids:
            continue
        carpeta = re.sub(r"^course files/?", "", rutas.get(a.get("folder_id"), "files"))
        subdir = dest_root / cname / Path(*[limpiar(p) for p in carpeta.split("/") if p])
        destino = subdir / limpiar(a.get("display_name", a["filename"]))
        try:
            if bajar(api, a["url"], destino, a.get("size", -1)):
                bajados += 1; log(f"  ↓ [archivos] {destino.relative_to(dest_root)}")
            else:
                saltados += 1
            # Solo se marca como visto si se pudo bajar (o ya estaba): si falló
            # (p. ej. archivo oculto sin URL), Módulos aún puede conseguirlo.
            vistos.add(a["id"])
        except Exception as e:
            log(f"  ✗ {a.get('display_name')}: {e}")
    return bajados, saltados


def descargar_por_modulos(api, cid, cname, dest_root, vistos, modulos_ids=None, log=print):
    bajados = saltados = 0
    try:
        mods = api.modulos(cid)
    except requests.HTTPError:
        log("  (sin Módulos accesibles)")
        return 0, 0
    for m in mods:
        if modulos_ids is not None and m.get("id") not in modulos_ids:
            continue
        mname = limpiar(m.get("name", "modulo"))
        base_dir = dest_root / cname / "Módulos" / mname
        try:
            items = api.items_modulo(cid, m["id"])
        except requests.HTTPError:
            continue
        for it in items:
            tipo = it.get("type")
            try:
                if tipo == "File":
                    fid = it.get("content_id")
                    if fid in vistos:
                        continue
                    cd = it.get("content_details") or {}
                    url = cd.get("url")
                    if not url:  # fallback: pedir metadata del archivo
                        meta = api.archivo(cid, fid); url = meta["url"]; cd = meta
                    name = limpiar(cd.get("display_name") or it.get("title"))
                    if bajar(api, url, base_dir / name, cd.get("size", -1)):
                        bajados += 1; log(f"  ↓ [módulo:{mname}] {name}")
                    else:
                        saltados += 1
                    vistos.add(fid)
                elif tipo == "Page":
                    # archivos embebidos dentro del cuerpo de la página
                    try:
                        pag = api.pagina(cid, it["page_url"])
                    except (requests.HTTPError, KeyError):
                        continue
                    body = pag.get("body") or ""
                    # snapshot HTML del contenido de la página
                    titulo = pag.get("title") or it.get("title") or "pagina"
                    guardar_html(base_dir / f"{limpiar(titulo)}.html", titulo, body, log)
                    for fid in {int(x) for x in re.findall(r"/files/(\d+)", body)}:
                        if fid in vistos:
                            continue
                        try:
                            meta = api.archivo(cid, fid)
                        except requests.HTTPError:
                            continue
                        name = limpiar(meta.get("display_name", meta.get("filename")))
                        if bajar(api, meta["url"], base_dir / name, meta.get("size", -1)):
                            bajados += 1; log(f"  ↓ [página:{mname}] {name}")
                        else:
                            saltados += 1
                        vistos.add(fid)
            except Exception as e:
                log(f"  ✗ item '{it.get('title')}': {e}")
    return bajados, saltados


def descargar_por_tareas(api, cid, cname, dest_root, vistos, incluir_entregas=False, log=print):
    bajados = saltados = 0
    try:
        tareas = api.tareas(cid)
    except requests.HTTPError:
        log("  (sin Tareas accesibles)")
        return 0, 0
    for t in tareas:
        tname = limpiar(t.get("name", f"tarea_{t['id']}"))
        base_dir = dest_root / cname / "Tareas" / tname

        # Snapshot HTML del enunciado (no suma a contadores)
        try:
            guardar_html(base_dir / "enunciado.html", tname, t.get("description"), log)
        except Exception as e:
            log(f"  ✗ [html:{tname}]: {e}")

        # Archivos adjuntos al enunciado
        try:
            desc = t.get("description") or ""
            for fid in {int(x) for x in re.findall(r"/files/(\d+)", desc)}:
                if fid in vistos:
                    continue
                try:
                    meta = api.archivo(cid, fid)
                except requests.HTTPError:
                    continue
                name = limpiar(meta.get("display_name", meta.get("filename")))
                if bajar(api, meta["url"], base_dir / name, meta.get("size", -1)):
                    bajados += 1; log(f"  ↓ [tarea:{tname}] {name}")
                else:
                    saltados += 1
                vistos.add(fid)
        except Exception as e:
            log(f"  ✗ tarea '{tname}': {e}")

        # Mi entrega (archivos que yo mismo subí), opcional
        if incluir_entregas:
            try:
                entrega = api.entrega(cid, t["id"])
            except requests.HTTPError:
                continue
            except Exception as e:
                log(f"  ✗ [entrega:{tname}]: {e}")
                continue
            try:
                adjuntos = {}
                for att in (entrega.get("attachments") or []):
                    if att and att.get("id") is not None:
                        adjuntos[att["id"]] = att
                for hist in (entrega.get("submission_history") or []):
                    if not hist:
                        continue
                    for att in (hist.get("attachments") or []):
                        if att and att.get("id") is not None:
                            adjuntos[att["id"]] = att
                carpeta_entrega = base_dir / "Mi entrega"
                for att in adjuntos.values():
                    name = limpiar(att.get("display_name") or att.get("filename")
                                   or f"archivo_{att['id']}")
                    if bajar(api, att["url"], carpeta_entrega / name, att.get("size", -1)):
                        bajados += 1; log(f"  ↓ [entrega:{tname}] {name}")
                    else:
                        saltados += 1
            except Exception as e:
                log(f"  ✗ [entrega:{tname}]: {e}")
    return bajados, saltados


def _descargar_topics(api, cid, cname, dest_root, vistos, topics, subcarpeta, etiqueta, log):
    """Lógica común para anuncios y discusiones: adjuntos del topic, archivos
    embebidos en el mensaje y snapshot HTML del mensaje."""
    bajados = saltados = 0
    for topic in topics:
        tname = limpiar(topic.get("title", f"tema_{topic['id']}"))
        base_dir = dest_root / cname / subcarpeta / tname
        try:
            # Snapshot HTML del mensaje (no suma a contadores)
            guardar_html(base_dir / f"{tname}.html", tname, topic.get("message"), log)
            # Adjuntos del topic
            for att in (topic.get("attachments") or []):
                name = limpiar(att.get("display_name") or att.get("filename")
                               or f"archivo_{att.get('id')}")
                if bajar(api, att["url"], base_dir / name, att.get("size", -1)):
                    bajados += 1; log(f"  ↓ [{etiqueta}:{tname}] {name}")
                else:
                    saltados += 1
            # Archivos embebidos en el mensaje
            msg = topic.get("message") or ""
            for fid in {int(x) for x in re.findall(r"/files/(\d+)", msg)}:
                if fid in vistos:
                    continue
                try:
                    meta = api.archivo(cid, fid)
                except requests.HTTPError:
                    continue
                name = limpiar(meta.get("display_name", meta.get("filename")))
                if bajar(api, meta["url"], base_dir / name, meta.get("size", -1)):
                    bajados += 1; log(f"  ↓ [{etiqueta}:{tname}] {name}")
                else:
                    saltados += 1
                vistos.add(fid)
        except Exception as e:
            log(f"  ✗ [{etiqueta}:{tname}]: {e}")
    return bajados, saltados


def descargar_por_anuncios(api, cid, cname, dest_root, vistos, log=print):
    try:
        topics = api.discusiones(cid, solo_anuncios=True)
    except requests.HTTPError:
        log("  (sin Anuncios accesibles)")
        return 0, 0
    return _descargar_topics(api, cid, cname, dest_root, vistos, topics,
                             "Anuncios", "anuncio", log)


def descargar_por_discusiones(api, cid, cname, dest_root, vistos, log=print):
    # Nota: sin only_announcements, Canvas NO incluye anuncios entre las
    # discusiones, así que no hay que filtrar duplicados.
    try:
        topics = api.discusiones(cid, solo_anuncios=False)
    except requests.HTTPError:
        log("  (sin Discusiones accesibles)")
        return 0, 0
    return _descargar_topics(api, cid, cname, dest_root, vistos, topics,
                             "Discusiones", "discusión", log)


def descargar_curso(api, curso, dest_root, fuentes, carpetas_ids=None, log=print,
                    por_termino=False, modulos_ids=None):
    # Compatibilidad con la firma anterior, que recibía un string "modo".
    if isinstance(fuentes, str):
        fuentes = {"archivos", "modulos"} if fuentes == "ambos" else {fuentes}
    else:
        fuentes = set(fuentes)

    cid = curso["id"]
    cname = limpiar(curso.get("name", f"curso_{cid}"))
    raiz = dest_root
    if por_termino:
        # Organiza la salida en <dest>/<término>/<curso>/... (los cursos de
        # cursos()/cursos_pasados() ya vienen con include[]=term).
        termino = limpiar((curso.get("term") or {}).get("name") or "Sin término")
        raiz = dest_root / termino
    log(f"\n=== {cname} (id {cid}) ===")
    vistos = set()  # file ids ya descargados, para no duplicar entre fuentes
    n = s = 0
    if "archivos" in fuentes:
        a, b = descargar_por_archivos(api, cid, cname, raiz, vistos, carpetas_ids, log)
        n += a; s += b
    if "modulos" in fuentes:
        a, b = descargar_por_modulos(api, cid, cname, raiz, vistos, modulos_ids, log)
        n += a; s += b
    if "tareas" in fuentes:
        a, b = descargar_por_tareas(api, cid, cname, raiz, vistos,
                                    "entregas" in fuentes, log)
        n += a; s += b
    if "anuncios" in fuentes:
        a, b = descargar_por_anuncios(api, cid, cname, raiz, vistos, log)
        n += a; s += b
    if "discusiones" in fuentes:
        a, b = descargar_por_discusiones(api, cid, cname, raiz, vistos, log)
        n += a; s += b
    log(f"  → {n} nuevos, {s} ya existían.")
    return n, s


def main():
    ap = argparse.ArgumentParser(
        description="Descargador de Canvas LMS (archivos + módulos + tareas + anuncios + discusiones)")
    ap.add_argument("--listar", action="store_true", help="lista tus cursos y sale")
    ap.add_argument("--curso", nargs="+", type=int, help="IDs de curso a descargar")
    ap.add_argument("--todos", action="store_true", help="descarga todos los cursos activos")
    ap.add_argument("--filtro", help="solo cursos cuyo nombre contenga este texto")
    ap.add_argument("--solo-modulos", action="store_true", help="bajar solo desde Módulos")
    ap.add_argument("--solo-archivos", action="store_true", help="bajar solo desde la pestaña Archivos")
    ap.add_argument("--solo-tareas", action="store_true", help="bajar solo desde Tareas")
    ap.add_argument("--tareas", action="store_true", help="sumar Tareas a las fuentes por defecto")
    ap.add_argument("--entregas", action="store_true",
                    help="sumar mis entregas de las tareas (implica --tareas)")
    ap.add_argument("--anuncios", action="store_true", help="sumar Anuncios a las fuentes")
    ap.add_argument("--discusiones", action="store_true", help="sumar Discusiones a las fuentes")
    ap.add_argument("--por-termino", action="store_true",
                    help="organizar la salida en <destino>/<término>/<curso>/...")
    ap.add_argument("--incluir-pasados", action="store_true",
                    help="incluir también cursos con inscripciones pasadas/concluidas")
    ap.add_argument("--dest", default=str(DEFAULT_DEST), help="carpeta destino")
    args = ap.parse_args()

    fuentes = {"archivos", "modulos"}
    if args.solo_modulos:
        fuentes = {"modulos"}
    elif args.solo_archivos:
        fuentes = {"archivos"}
    if args.solo_tareas:
        fuentes = {"tareas"}
    if args.tareas:
        fuentes.add("tareas")
    if args.entregas:
        fuentes.add("tareas")
        fuentes.add("entregas")
    if args.anuncios:
        fuentes.add("anuncios")
    if args.discusiones:
        fuentes.add("discusiones")

    base, token = cargar_config()
    api = Canvas(base, token)
    cursos = api.cursos()

    if args.incluir_pasados:
        existentes = {c["id"] for c in cursos}
        for c in api.cursos_pasados():
            if c["id"] not in existentes:
                c["_pasado"] = True
                cursos.append(c)
                existentes.add(c["id"])

    if args.filtro:
        f = args.filtro.lower()
        cursos = [c for c in cursos if f in c.get("name", "").lower()]

    if args.listar or not (args.curso or args.todos):
        print("Cursos disponibles:")
        for c in cursos:
            term = (c.get("term") or {}).get("name", "")
            etiqueta = " [pasado]" if c.get("_pasado") else ""
            print(f"  {c['id']:>8}  {c.get('name','(sin nombre)')}  [{term}]{etiqueta}")
        if not (args.curso or args.todos):
            print("\nUsá --curso <id> o --todos para descargar.")
        return

    if args.curso:
        ids = set(args.curso)
        cursos = [c for c in cursos if c["id"] in ids]

    dest = Path(args.dest)
    tn = ts = 0
    for c in cursos:
        n, s = descargar_curso(api, c, dest, fuentes, por_termino=args.por_termino)
        tn += n; ts += s
    print(f"\nTERMINADO: {tn} archivos nuevos, {ts} ya estaban. Destino: {dest}")


if __name__ == "__main__":
    main()
