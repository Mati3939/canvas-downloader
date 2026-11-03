"""Corrida completa del trabajador: sincroniza Canvas -> Drive (sync_ramos)
y publica el snapshot de cada ramo en Supabase, con enlaces de Google Drive.

Pensado para ejecutarse sin atención, cada 2 horas, vía el Programador de
tareas de Windows (ver instalar_tarea.ps1). Un lock de archivo evita que dos
corridas se solapen (con otra corrida programada o con el botón "Sincronizar
ramos" de la GUI, que también llama a `correr`).

USO:
  python -m worker.run [--sin-sync]
"""
import argparse
import ctypes
import os
import sys
from pathlib import Path

import requests

from sync_ramos import (
    ErrorFatal,
    MANIFEST_FILE,
    Manifest,
    carpeta_curso,
)
from sync_ramos import cargar_config as _cargar_config
from sync_ramos import conectar as _conectar
from sync_ramos import leer_env as _leer_env
from sync_ramos import resolver_drive_root as _resolver_drive_root
from sync_ramos import sanitizar
from sync_ramos import sincronizar as _sincronizar
from sync_ramos import verificar_drive_root as _verificar_drive_root
from worker.drive import EnlacesDrive as _EnlacesDrive
from worker.drive import conectar_drive as _conectar_drive
from worker.drive import conectar_calendario as _conectar_calendario
from worker import calendario as _calendario
from worker.drive import ruta_en_mi_unidad
from worker.snapshot import LecturaFallida
from worker.snapshot import snapshot_curso as _snapshot_curso
from worker.supabase import Supabase as _Supabase

REPO = Path(__file__).resolve().parent.parent
ESTADO_DIR = REPO / "worker_estado"
LOG_FILE = ESTADO_DIR / "ultima_corrida.log"

_CLAVES_SUPABASE = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "BC_USER_ID")

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_ACCESS_DENIED = 5

if sys.platform == "win32":
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    _kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


def _config_supabase(env):
    """Config de Supabase del worker: variables de entorno tienen prioridad
    sobre el .env. ErrorFatal con un mensaje claro si falta alguna."""
    valores = {}
    for clave in _CLAVES_SUPABASE:
        valores[clave] = os.environ.get(clave) or env.get(clave)
    faltan = [c for c in _CLAVES_SUPABASE if not valores[c]]
    if faltan:
        raise ErrorFatal(
            "Falta configurar " + ", ".join(faltan) + " en el .env para publicar en Supabase."
        )
    return valores


# --------------------------------------------------------------------- lock

def _pid_vivo(pid):
    """True si el proceso con ese pid sigue corriendo (o no se puede saber
    con certeza, por ejemplo sin permiso para abrirlo: ante la duda se
    trata como vivo, para no robarle el lock a una corrida real).

    En Windows, `os.kill(pid, 0)` en realidad *termina* el proceso (no es un
    simple chequeo como en POSIX): hay que usar la API nativa en su lugar.
    """
    if sys.platform == "win32":
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ctypes.get_last_error() == _ERROR_ACCESS_DENIED
        try:
            codigo = wintypes.DWORD()
            if not _kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return False
            return codigo.value == _STILL_ACTIVE
        finally:
            _kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, AttributeError):
        return False
    return True


class _LockCorrida:
    """Lock de archivo con el pid del proceso que lo tiene. Si el pid no
    corresponde a un proceso vivo, o el archivo no se puede leer, el lock se
    considera abandonado: se borra y se reintenta una vez.

    La creación con `os.O_CREAT | os.O_EXCL` es atómica (a diferencia de
    comprobar `exists()` y después escribir, que deja una ventana entre
    ambos pasos donde dos corridas podrían creer que tomaron el lock)."""

    def __init__(self, path):
        self.path = Path(path)
        self._tomado = False

    def _pid_del_lock(self):
        try:
            return int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def adquirir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _intento in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                pid = self._pid_del_lock()
                if pid is not None and _pid_vivo(pid):
                    return False
                try:
                    self.path.unlink()
                except OSError:
                    pass
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
            self._tomado = True
            return True
        return False

    def liberar(self):
        if self._tomado:
            try:
                self.path.unlink()
            except OSError:
                pass
            self._tomado = False


# --------------------------------------------------------------------- corrida

def _publicar_calendario(log, env, estado_dir, sb, conectar_calendario):
    """Publica clases y evaluaciones de Google Calendar. Sin autorizacion de
    Calendar solo deja un aviso (la corrida sigue ok); un error al leer o
    publicar si marca la corrida con errores."""
    try:
        servicio = conectar_calendario(estado_dir)
    except Exception as e:
        mensaje = sanitizar(str(e))
        log(f"Calendario no disponible ({mensaje})")
        return {"ok": True, "aviso": mensaje}
    try:
        desde, hasta = _calendario.ventana()
        marca = env.get("HORARIO_MARCA") or _calendario.MARCA_HORARIO_POR_DEFECTO
        filas = _calendario.leer_eventos(servicio, desde, hasta, marca)
        n = sb.publicar_eventos(filas, desde.isoformat(), hasta.isoformat())
    except Exception as e:
        mensaje = sanitizar(str(e))
        log(f"✗ no se pudo publicar el calendario: {mensaje}")
        return {"ok": False, "error": mensaje}
    log(f"  Calendario: {n} eventos publicados")
    return {"ok": True, "conteos": {"calendar_events": n}}


def correr(log=print, sync=True, *,
           estado_dir=ESTADO_DIR,
           leer_env=_leer_env,
           cargar_config=_cargar_config,
           resolver_drive_root=_resolver_drive_root,
           verificar_drive_root=_verificar_drive_root,
           sincronizar=_sincronizar,
           conectar=_conectar,
           snapshot_curso=_snapshot_curso,
           Supabase=_Supabase,
           conectar_drive=_conectar_drive,
           EnlacesDrive=_EnlacesDrive,
           conectar_calendario=_conectar_calendario,
           manifest_path=None):
    """Corrida completa: sincroniza (si `sync`) y publica cada ramo en
    Supabase con sus enlaces de Drive. Devuelve
    `{nombre_ramo: {"ok": bool, "conteos" | "error": ...}}`.

    Usa un lock de archivo en `estado_dir`/corrida.lock: si ya hay una
    corrida viva, no hace nada y devuelve `{}`. Todos los demás parámetros
    son colaboradores inyectables (para tests, sin red ni credenciales).
    """
    estado_dir = Path(estado_dir)
    lock = _LockCorrida(estado_dir / "corrida.lock")
    if not lock.adquirir():
        log("ya hay una corrida en curso")
        return {}
    try:
        return _correr(
            log=log, sync=sync, estado_dir=estado_dir, leer_env=leer_env,
            cargar_config=cargar_config, resolver_drive_root=resolver_drive_root,
            verificar_drive_root=verificar_drive_root, sincronizar=sincronizar,
            conectar=conectar, snapshot_curso=snapshot_curso, Supabase=Supabase,
            conectar_drive=conectar_drive, EnlacesDrive=EnlacesDrive,
            conectar_calendario=conectar_calendario, manifest_path=manifest_path,
        )
    finally:
        lock.liberar()


def _correr(*, log, sync, estado_dir, leer_env, cargar_config, resolver_drive_root,
            verificar_drive_root, sincronizar, conectar, snapshot_curso, Supabase,
            conectar_drive, EnlacesDrive, conectar_calendario, manifest_path):
    def _log(msg=""):
        log(sanitizar(msg))

    env = leer_env()
    config_sb = _config_supabase(env)
    cfg = cargar_config()
    cursos = cfg["cursos"]
    for i, curso in enumerate(cursos):
        curso["position"] = i

    raiz = resolver_drive_root(env)
    manifest_path = manifest_path or MANIFEST_FILE

    resultados = {}
    if sync:
        try:
            verificar_drive_root(raiz, escribir=True)
            sincronizar(cfg, cursos, raiz, _log, manifest_path=manifest_path)
        except Exception as e:
            # Si el sync falla, la corrida igual publica con el manifest
            # existente (mas abajo), pero la corrida completa no puede
            # quedar ok=True: Supabase mostraria datos viejos como si fueran
            # la ultima sincronizacion.
            mensaje = sanitizar(str(e))
            _log(f"✗ no se pudo sincronizar: {mensaje}")
            resultados["_sync"] = {"ok": False, "error": mensaje}

    manifest = Manifest(manifest_path)

    enlaces = None
    base_partes = None
    try:
        servicio = conectar_drive(estado_dir)
    except Exception as e:
        _log(f"Drive no disponible ({e}). Corre: python -m worker.drive")
    else:
        try:
            base_partes = ruta_en_mi_unidad(raiz)
            enlaces = EnlacesDrive(servicio, estado_dir / "drive_enlaces.json")
        except ValueError as e:
            _log(f"✗ DRIVE_ROOT no esta dentro de 'Mi unidad' ni 'My Drive': {e}")

    sb = Supabase(config_sb["SUPABASE_URL"], config_sb["SUPABASE_SERVICE_KEY"],
                  config_sb["BC_USER_ID"])
    run_id = sb.iniciar_corrida()

    try:
        api = conectar()
        for curso_cfg in cursos:
            nombre = curso_cfg["nombre"]
            try:
                snap = snapshot_curso(api, manifest, curso_cfg, api.base)
            except (LecturaFallida, requests.RequestException) as e:
                mensaje = sanitizar(str(e))
                _log(f"✗ {nombre}: no se pudo leer de Canvas, no se publica: {mensaje}")
                resultados[nombre] = {"ok": False, "error": mensaje}
                continue

            if enlaces is not None:
                dir_curso = carpeta_curso(raiz, cfg, curso_cfg)
                curso_partes = base_partes + list(Path(dir_curso).relative_to(raiz).parts)
                snap["course"]["drive_url"] = enlaces.enlace(curso_partes)
                for fila in snap["files"]:
                    fila["drive_url"] = enlaces.enlace(
                        curso_partes + ["canvas"] + fila["ruta"].split("/"))
            # Si Drive no esta disponible, no se manda drive_url (ni null):
            # el merge-duplicates del upsert deja el enlace anterior tal
            # como estaba en vez de borrarlo.

            try:
                primera_vez = not sb.curso_publicado(snap["course"]["canvas_id"])
                conteos = sb.publicar_curso(snap, primera_vez)
            except Exception as e:
                # Un fallo de Supabase (red, 5xx, etc.) en un ramo no debe
                # abortar la corrida completa: los demas ramos se publican
                # igual y la corrida se cierra con ok=False.
                mensaje = sanitizar(str(e))
                _log(f"✗ {nombre}: no se pudo publicar en Supabase: {mensaje}")
                resultados[nombre] = {"ok": False, "error": mensaje}
                continue

            resultados[nombre] = {"ok": True, "conteos": conteos}
            _log(f"  {nombre}: publicado en Supabase {conteos}")

        resultados["_calendario"] = _publicar_calendario(
            _log, env, estado_dir, sb, conectar_calendario)
    except Exception as e:
        # Un error que se escapa del recorrido por ramo (por ejemplo no
        # poder conectar a Canvas) no debe dejar la corrida "ok" solo
        # porque los resultados parciales lo eran: se registra aparte.
        mensaje = sanitizar(str(e))
        _log(f"✗ error inesperado: {mensaje}")
        resultados["_error"] = {"ok": False, "error": mensaje}
    finally:
        if enlaces is not None:
            try:
                enlaces.guardar()
            except Exception as e:
                _log(f"✗ no se pudo guardar la cache de enlaces de Drive: {e}")

        ok_total = bool(resultados) and all(r["ok"] for r in resultados.values())
        try:
            sb.cerrar_corrida(run_id, ok_total, resultados)
        except Exception as e:
            _log(f"✗ no se pudo cerrar la corrida en Supabase: {e}")

    return resultados


# --------------------------------------------------------------------- CLI

def _log_consola_y_archivo(archivo):
    def log(msg=""):
        texto = str(msg)
        try:
            print(texto)
        except Exception:
            pass
        try:
            archivo.write(texto + "\n")
            archivo.flush()
        except Exception:
            pass
    return log


def _preparar_salida():
    """Bajo `pythonw` (tarea programada) sys.stdout y sys.stderr son None:
    sin esto, cualquier print suelto o el log de argparse revientan con
    AttributeError antes de llegar al log de archivo (ver iniciar_canvas.pyw,
    que hace lo mismo para la GUI)."""
    for nombre in ("stdout", "stderr"):
        if getattr(sys, nombre, None) is None:
            try:
                setattr(sys, nombre, open(os.devnull, "w", encoding="utf-8"))
            except OSError:
                pass


def main(argv=None):
    _preparar_salida()
    parser = argparse.ArgumentParser(description="Corrida del trabajador de Better Canvas.")
    parser.add_argument("--sin-sync", action="store_true",
                        help="Solo publica en Supabase; no sincroniza Canvas con Drive.")
    args = parser.parse_args(argv)

    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as archivo:
        log = _log_consola_y_archivo(archivo)
        try:
            resultados = correr(log=log, sync=not args.sin_sync)
        except ErrorFatal as e:
            log(sanitizar(f"✗ {e}"))
            return 1
        except Exception as e:
            log(sanitizar(f"✗ error inesperado: {e}"))
            return 1
        if any(not r.get("ok") for r in resultados.values()):
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
