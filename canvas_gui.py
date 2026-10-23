#!/usr/bin/env python3
"""
Interfaz web local para el Descargador de Canvas LMS.

Levanta un servidor HTTP (solo librería estándar, sin dependencias nuevas) que
sirve una página (gui.html) desde la cual se pueden elegir cursos y carpetas,
lanzar la descarga y ver el progreso en vivo. Reutiliza toda la lógica de
canvas_descargar.py (config, cliente de la API y la descarga en sí).

USO:
  python canvas_gui.py

Abre automáticamente el navegador en http://127.0.0.1:8765/ (o el puerto que
haya quedado libre si ese estaba ocupado). El botón "Sincronizar ramos" lanza,
si ramos.yaml y DRIVE_ROOT están configurados, el sync incremental hacia la
carpeta de Drive (sync_ramos.py).
"""
import os
import sys
import json
import threading
import webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, unquote

from canvas_descargar import cargar_config, Canvas, descargar_curso, limpiar, DEFAULT_DEST

# La consola de Windows (cp1252) no puede imprimir acentos ni símbolos:
# forzamos UTF-8 en la salida para evitar UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
GUI_HTML = HERE / "gui.html"
ESCANEAR_HTML = HERE / "escanear.html"
PREFS_FILE = HERE / "canvas_gui_prefs.json"   # preferencias (ocultos/orden) por usuario
PUERTO_PREFERIDO = 8765
LIMITE_CUERPO_ESCANEO = 40 * 1024 * 1024   # 40 MB, para /api/escaneo/analizar y /capturar


def _preparar_sync(escribir):
    """(cfg, raiz) listos para sincronizar, o ErrorFatal/ImportError con el motivo.
    sync_ramos usa PyYAML, que se importa recién acá: la descarga manual funciona
    aunque el sync no esté configurado."""
    import sync_ramos
    cfg = sync_ramos.cargar_config()
    raiz = sync_ramos.resolver_drive_root(sync_ramos.leer_env())
    sync_ramos.verificar_drive_root(raiz, escribir=escribir)
    return cfg, raiz


def _estado_sync():
    try:
        cfg, raiz = _preparar_sync(escribir=False)
    except ImportError as e:
        if getattr(e, "name", "") == "yaml":
            motivo = "Falta PyYAML: python -m pip install pyyaml"
        else:
            motivo = f"No se pudo cargar el sync: {e}"
        return {"ok": False, "motivo": motivo, "carpeta": None}
    except Exception as e:  # ErrorFatal del sync: falta ramos.yaml, DRIVE_ROOT, etc.
        return {"ok": False, "motivo": str(e).splitlines()[0], "carpeta": None}
    return {"ok": True, "motivo": None, "carpeta": str(Path(raiz) / cfg["semestre"])}

# ---------------------------------------------------------------------------
# Estado compartido entre requests (protegido por locks porque
# ThreadingHTTPServer atiende cada request en su propio hilo).
# ---------------------------------------------------------------------------
_state_lock = threading.RLock()
_canvas = None                 # instancia perezosa de Canvas
_cursos_cache = None           # {"activos": [...], "pasados": [...]} (crudo de la API)
_cursos_by_id = {}             # id -> dict de curso (crudo), para resolver durante la descarga
_carpetas_cache = {}           # cid -> lista de carpetas (crudo de carpetas_detalle)
_modulos_cache = {}            # cid -> lista de módulos (crudo de la API)

_descarga_lock = threading.Lock()
_descarga_activa = False
_log_lock = threading.Lock()
_log_lineas = []
_resumen = None
_dest_actual = ""              # se completa recién cuando arranca una descarga

_escaneo = None                # instancia perezosa de escaneo_sesion.GestorEscaneo
_escaneo_lock = threading.Lock()


def _gestor_escaneo():
    """GestorEscaneo perezoso: importa escaneo_sesion (que a su vez importa
    cv2/numpy/img2pdf de forma perezosa) recién cuando hace falta, para que
    la GUI arranque sin esas dependencias instaladas."""
    global _escaneo
    with _escaneo_lock:
        if _escaneo is None:
            import escaneo_sesion
            _escaneo = escaneo_sesion.GestorEscaneo()
        return _escaneo


def _try_cargar_config():
    """cargar_config() hace sys.exit si falta la config; lo atrapamos."""
    try:
        return cargar_config()
    except SystemExit:
        return None
    except BaseException:
        return None


def get_canvas():
    global _canvas
    with _state_lock:
        if _canvas is None:
            base, token = cargar_config()  # puede levantar SystemExit -> lo atrapa el caller
            _canvas = Canvas(base, token)
        return _canvas


def _resumen_curso(c):
    term = c.get("term") or {}
    return {
        "id": c["id"],
        "name": c.get("name", "(sin nombre)"),
        "term": term.get("name", "") if isinstance(term, dict) else "",
    }


def _obtener_cursos(recargar=False):
    global _cursos_cache, _cursos_by_id
    with _state_lock:
        if _cursos_cache is None or recargar:
            api = get_canvas()
            activos = api.cursos()
            pasados = api.cursos_pasados()
            _cursos_cache = {"activos": activos, "pasados": pasados}
            _cursos_by_id = {c["id"]: c for c in activos + pasados}
        return _cursos_cache


def _obtener_carpetas(cid):
    with _state_lock:
        if cid not in _carpetas_cache:
            api = get_canvas()
            _carpetas_cache[cid] = api.carpetas_detalle(cid)
        return _carpetas_cache[cid]


def _obtener_modulos(cid):
    import requests
    with _state_lock:
        if cid not in _modulos_cache:
            api = get_canvas()
            try:
                _modulos_cache[cid] = api.modulos(cid)
            except requests.HTTPError:
                _modulos_cache[cid] = []
        return _modulos_cache[cid]


def _log(linea):
    with _log_lock:
        _log_lineas.append(str(linea))


# ---------------------------------------------------------------------------
# Preferencias por usuario (cursos ocultos y orden de tarjetas)
# ---------------------------------------------------------------------------
_user_id = None
_prefs_lock = threading.Lock()


def _obtener_user_id():
    """Id del usuario de Canvas, para guardar preferencias por usuario."""
    global _user_id
    with _state_lock:
        if _user_id is None:
            try:
                api = get_canvas()
                r = api.s.get(f"{api.base}/api/v1/users/self")
                r.raise_for_status()
                _user_id = str(r.json().get("id", "default"))
            except Exception:
                _user_id = "default"
        return _user_id


def _leer_prefs():
    uid = _obtener_user_id()
    with _prefs_lock:
        datos = {}
        if PREFS_FILE.exists():
            try:
                datos = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
            except Exception:
                datos = {}
        return datos.get(uid) or {"ocultos": [], "orden": {}}


def _guardar_prefs(prefs):
    uid = _obtener_user_id()
    with _prefs_lock:
        datos = {}
        if PREFS_FILE.exists():
            try:
                datos = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
            except Exception:
                datos = {}
        datos[uid] = {
            "ocultos": [int(x) for x in (prefs.get("ocultos") or []) if isinstance(x, (int, float, str)) and str(x).lstrip("-").isdigit()],
            "orden": prefs.get("orden") or {},
        }
        PREFS_FILE.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _ejecutar_descarga(cursos_sel, fuentes, dest, por_termino=False):
    global _descarga_activa, _resumen
    total_n = total_s = errores = 0
    try:
        try:
            api = get_canvas()
        except SystemExit as e:
            _log(f"✗ configuración inválida: {e}")
            _resumen = {"nuevos": 0, "saltados": 0, "errores": len(cursos_sel) or 1}
            return

        with _state_lock:
            cache_ids = dict(_cursos_by_id)

        for sel in cursos_sel:
            try:
                cid = int(sel.get("id"))
            except (TypeError, ValueError):
                errores += 1
                _log(f"✗ selección inválida: {sel!r}")
                continue
            # None = "todo"; lista (aun vacía) = solo esos ids
            carpetas_ids = sel.get("carpetas")
            carpetas_ids_set = None if carpetas_ids is None else set(carpetas_ids)
            modulos_ids = sel.get("modulos")
            modulos_ids_set = None if modulos_ids is None else set(modulos_ids)
            curso = cache_ids.get(cid) or {"id": cid, "name": f"curso_{cid}"}
            try:
                n, s = descargar_curso(
                    api, curso, dest, fuentes,
                    carpetas_ids=carpetas_ids_set, log=_log, por_termino=por_termino,
                    modulos_ids=modulos_ids_set,
                )
                total_n += n
                total_s += s
            except Exception as e:
                errores += 1
                _log(f"✗ curso {curso.get('name', cid)}: {e}")
        _resumen = {"nuevos": total_n, "saltados": total_s, "errores": errores}
    finally:
        with _descarga_lock:
            _descarga_activa = False


def _tiene_config_supabase():
    """True si .env/entorno tienen lo que necesita worker.run para publicar
    en Supabase (sin lanzar la corrida)."""
    try:
        import sync_ramos
        import worker.run as worker_run
        worker_run._config_supabase(sync_ramos.leer_env())
        return True
    except Exception:
        return False


def _ejecutar_sync():
    global _descarga_activa, _resumen, _dest_actual
    errores = nuevos = sin_cambios = 0
    try:
        try:
            import sync_ramos
            cfg, raiz = _preparar_sync(escribir=True)
        except Exception as e:
            _log(f"✗ {e}")
            _resumen = {"nuevos": 0, "saltados": 0, "errores": 1}
            return

        def log(msg=""):
            _log(sync_ramos.sanitizar(msg))

        _dest_actual = str(Path(raiz) / cfg["semestre"])
        log(f"Carpeta de ramos: {_dest_actual}")

        if _tiene_config_supabase():
            # Config de Supabase presente: la corrida completa del
            # trabajador (sync + publicación) reemplaza al sync solo.
            import worker.run as worker_run
            manifest = os.environ.get("SYNC_MANIFEST")
            try:
                resultados = worker_run.correr(log=log, manifest_path=manifest)
            except Exception as e:
                log(f"✗ {e}")
                _resumen = {"nuevos": 0, "saltados": 0, "errores": 1}
                return
            for nombre, r in resultados.items():
                if r.get("ok"):
                    log(f"  {nombre}: publicado en Supabase")
                else:
                    errores += 1
                    log(f"  ✗ {nombre}: {r.get('error')}")
            _resumen = {"nuevos": nuevos, "saltados": sin_cambios, "errores": errores}
            return

        manifest = os.environ.get("SYNC_MANIFEST") or sync_ramos.MANIFEST_FILE
        try:
            resultados = sync_ramos.sincronizar(cfg, cfg["cursos"], raiz, log,
                                                manifest_path=manifest)
            sync_ramos.imprimir_resumen(resultados, log)
        except Exception as e:
            log(f"✗ {e}")
            errores += 1
            resultados = {}
        for r in resultados.values():
            nuevos += len(r["nuevos"]) + len(r["actualizados"])
            sin_cambios += r["sin_cambios"]
            errores += len(r["errores"])
        _resumen = {"nuevos": nuevos, "saltados": sin_cambios, "errores": errores}
    finally:
        with _descarga_lock:
            _descarga_activa = False


class CanvasGUIHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ---- helpers de respuesta ----
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, texto, status=200):
        body = texto.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body_json(self):
        largo = int(self.headers.get("Content-Length", 0) or 0)
        crudo = self.rfile.read(largo) if largo else b"{}"
        return json.loads(crudo.decode("utf-8") or "{}")

    def _body_binaria(self):
        """Cuerpo crudo (JPEG) con tope de 40 MB. None si ya se respondió un
        413: el caller debe cortar ahí sin seguir procesando la request."""
        largo = int(self.headers.get("Content-Length", 0) or 0)
        if largo > LIMITE_CUERPO_ESCANEO:
            self.close_connection = True  # no drenamos el cuerpo: cerramos la conexión
            self._send_json({"error": "Imagen demasiado grande (máximo 40 MB)."}, 413)
            return None
        return self.rfile.read(largo) if largo else b""

    def _responder_escaneo(self, func, *args, **kwargs):
        """Ejecuta un método de GestorEscaneo y manda el resultado como JSON.
        ErrorEscaneo define el status; cualquier otra excepción es un 500
        sin tumbar el servidor."""
        import escaneo_sesion
        try:
            resultado = func(*args, **kwargs)
        except escaneo_sesion.ErrorEscaneo as e:
            self._send_json({"error": e.mensaje}, e.status)
            return
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
            return
        self._send_json(resultado if resultado is not None else {"ok": True})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ---- ruteo ----
    def do_GET(self):
        partes = urlsplit(self.path)
        ruta = partes.path
        qs = parse_qs(partes.query)
        try:
            if ruta == "/" or ruta == "/index.html":
                self._get_index()
            elif ruta == "/escanear":
                self._get_escanear()
            elif ruta == "/api/estado":
                self._get_estado()
            elif ruta == "/api/cursos":
                self._get_cursos(qs)
            elif ruta == "/api/carpetas":
                self._get_carpetas(qs)
            elif ruta == "/api/modulos":
                self._get_modulos(qs)
            elif ruta == "/api/prefs":
                self._send_json(_leer_prefs())
            elif ruta == "/api/progreso":
                self._get_progreso(qs)
            elif ruta == "/api/escaneo/estado":
                self._responder_escaneo(_gestor_escaneo().estado)
            elif ruta.startswith("/api/escaneo/pagina/"):
                self._get_escaneo_pagina(unquote(ruta[len("/api/escaneo/pagina/"):]))
            else:
                self._send_json({"error": "no encontrado"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def do_POST(self):
        ruta = urlsplit(self.path).path
        qs = parse_qs(urlsplit(self.path).query)
        try:
            if ruta == "/api/descargar":
                self._post_descargar()
            elif ruta == "/api/sincronizar":
                self._post_sincronizar()
            elif ruta == "/api/prefs":
                _guardar_prefs(self._body_json())
                self._send_json({"ok": True})
            elif ruta == "/api/escaneo/sesion":
                datos = self._body_json()
                self._responder_escaneo(_gestor_escaneo().iniciar, datos.get("ramo"), datos.get("titulo"))
            elif ruta == "/api/escaneo/analizar":
                cuerpo = self._body_binaria()
                if cuerpo is not None:
                    self._responder_escaneo(_gestor_escaneo().analizar, cuerpo)
            elif ruta == "/api/escaneo/capturar":
                forzar = qs.get("forzar", ["0"])[0] == "1"
                cuerpo = self._body_binaria()
                if cuerpo is not None:
                    self._responder_escaneo(_gestor_escaneo().capturar, cuerpo, forzar)
            elif ruta == "/api/escaneo/terminar":
                datos = self._body_json()
                self._responder_escaneo(_gestor_escaneo().terminar, datos.get("titulo"))
            elif ruta == "/api/escaneo/cancelar":
                self._body_json()  # sin parámetros, pero hay que drenar el cuerpo si lo hay
                self._responder_escaneo(_gestor_escaneo().cancelar)
            elif ruta == "/api/escaneo/abrir_carpeta":
                self._body_json()  # ídem
                self._responder_escaneo(_gestor_escaneo().abrir_carpeta)
            else:
                self._send_json({"error": "no encontrado"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        ruta = urlsplit(self.path).path
        try:
            if ruta.startswith("/api/escaneo/pagina/"):
                id_ = unquote(ruta[len("/api/escaneo/pagina/"):])
                self._responder_escaneo(_gestor_escaneo().borrar, id_)
            else:
                self._send_json({"error": "no encontrado"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ---- handlers ----
    def _get_index(self):
        if not GUI_HTML.exists():
            self._send_html("<h1>Falta gui.html</h1>", 500)
            return
        self._send_html(GUI_HTML.read_text(encoding="utf-8"))

    def _get_escanear(self):
        if not ESCANEAR_HTML.exists():
            self._send_html("<h1>Falta escanear.html</h1>", 500)
            return
        self._send_html(ESCANEAR_HTML.read_text(encoding="utf-8"))

    def _get_escaneo_pagina(self, id_):
        import escaneo_sesion
        try:
            datos = _gestor_escaneo().pagina_jpeg(id_)
        except escaneo_sesion.ErrorEscaneo as e:
            self._send_json({"error": e.mensaje}, e.status)
            return
        except Exception as e:
            self._send_json({"error": str(e)}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _get_estado(self):
        cfg = _try_cargar_config()
        self._send_json({"config": cfg is not None, "sync": _estado_sync()})

    def _get_cursos(self, qs):
        recargar = qs.get("recargar", ["0"])[0] == "1"
        try:
            datos = _obtener_cursos(recargar=recargar)
        except SystemExit as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json({
            "activos": [_resumen_curso(c) for c in datos["activos"]],
            "pasados": [_resumen_curso(c) for c in datos["pasados"]],
        })

    def _get_carpetas(self, qs):
        valores = qs.get("curso")
        if not valores:
            self._send_json({"error": "falta parámetro 'curso'"}, 400)
            return
        try:
            cid = int(valores[0])
        except ValueError:
            self._send_json({"error": "'curso' debe ser numérico"}, 400)
            return
        try:
            carpetas = _obtener_carpetas(cid)
        except SystemExit as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json({
            "carpetas": [
                {
                    "id": f["id"],
                    "nombre": f.get("name", "carpeta"),
                    "parent_id": f.get("parent_folder_id"),
                }
                for f in carpetas
            ]
        })

    def _get_modulos(self, qs):
        valores = qs.get("curso")
        if not valores:
            self._send_json({"error": "falta parámetro 'curso'"}, 400)
            return
        try:
            cid = int(valores[0])
        except ValueError:
            self._send_json({"error": "'curso' debe ser numérico"}, 400)
            return
        try:
            modulos = _obtener_modulos(cid)
        except SystemExit as e:
            self._send_json({"error": str(e)}, 400)
            return
        self._send_json({
            "modulos": [
                {"id": m["id"], "nombre": m.get("name", "módulo")}
                for m in modulos if "id" in m
            ]
        })

    def _post_descargar(self):
        global _descarga_activa, _log_lineas, _resumen, _dest_actual
        with _descarga_lock:
            if _descarga_activa:
                self._send_json({"error": "descarga en curso"}, 409)
                return
            _descarga_activa = True

        try:
            data = self._body_json()
        except Exception as e:
            with _descarga_lock:
                _descarga_activa = False
            self._send_json({"error": f"JSON inválido: {e}"}, 400)
            return

        cursos_sel = data.get("cursos") or []
        fuentes = data.get("fuentes") or []
        dest_raw = (data.get("dest") or "").strip()
        dest = Path(dest_raw) if dest_raw else DEFAULT_DEST
        por_termino = bool(data.get("por_termino", False))

        with _log_lock:
            _log_lineas = []
        _resumen = None
        _dest_actual = str(dest)

        hilo = threading.Thread(
            target=_ejecutar_descarga, args=(cursos_sel, fuentes, dest, por_termino), daemon=True
        )
        hilo.start()
        self._send_json({"ok": True})

    def _post_sincronizar(self):
        global _descarga_activa, _log_lineas, _resumen, _dest_actual
        with _descarga_lock:
            if _descarga_activa:
                self._send_json({"error": "descarga en curso"}, 409)
                return
            _descarga_activa = True
        with _log_lock:
            _log_lineas = []
        _resumen = None
        _dest_actual = ""
        threading.Thread(target=_ejecutar_sync, daemon=True).start()
        self._send_json({"ok": True})

    def _get_progreso(self, qs):
        try:
            desde = int(qs.get("desde", ["0"])[0])
        except ValueError:
            desde = 0
        with _log_lock:
            total = len(_log_lineas)
            lineas = _log_lineas[desde:] if 0 <= desde < total else []
        with _descarga_lock:
            activo = _descarga_activa
        self._send_json({
            "activo": activo,
            "lineas": lineas,
            "total": total,
            "resumen": _resumen,
            "dest": _dest_actual,
        })


def _elegir_servidor():
    try:
        return ThreadingHTTPServer(("127.0.0.1", PUERTO_PREFERIDO), CanvasGUIHandler)
    except OSError:
        return ThreadingHTTPServer(("127.0.0.1", 0), CanvasGUIHandler)


def main():
    httpd = _elegir_servidor()
    puerto = httpd.server_address[1]
    url = f"http://127.0.0.1:{puerto}/"
    print(f"Descargador de Canvas: servidor iniciado en {url}")
    print("Presioná Ctrl+C para cerrar.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
