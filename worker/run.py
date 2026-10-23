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
from worker.drive import ruta_en_mi_unidad
from worker.snapshot import LecturaFallida
from worker.snapshot import snapshot_curso as _snapshot_curso
from worker.supabase import Supabase as _Supabase

REPO = Path(__file__).resolve().parent.parent
ESTADO_DIR = REPO / "worker_estado"
LOG_FILE = ESTADO_DIR / "ultima_corrida.log"

_CLAVES_SUPABASE = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "BC_USER_ID")


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
    """True si el proceso con ese pid sigue corriendo.

    En Windows, `os.kill(pid, 0)` en realidad *termina* el proceso (no es un
    simple chequeo como en POSIX): hay que usar la API nativa en su lugar.
    """
    if sys.platform == "win32":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            codigo = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
                return False
            return codigo.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except (OSError, AttributeError):
        return False
    return True


class _LockCorrida:
    """Lock de archivo con el pid del proceso que lo tiene. Si el pid no
    corresponde a un proceso vivo, o el archivo no se puede leer, el lock se
    considera abandonado y se toma igual."""

    def __init__(self, path):
        self.path = Path(path)
        self._tomado = False

    def adquirir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                pid = int(self.path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                pid = None
            if pid is not None and _pid_vivo(pid):
                return False
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        self._tomado = True
        return True

    def liberar(self):
        if self._tomado:
            try:
                self.path.unlink()
            except OSError:
                pass
            self._tomado = False


# --------------------------------------------------------------------- corrida

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
            manifest_path=manifest_path,
        )
    finally:
        lock.liberar()


def _correr(*, log, sync, estado_dir, leer_env, cargar_config, resolver_drive_root,
            verificar_drive_root, sincronizar, conectar, snapshot_curso, Supabase,
            conectar_drive, EnlacesDrive, manifest_path):
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

    if sync:
        try:
            verificar_drive_root(raiz, escribir=True)
            sincronizar(cfg, cursos, raiz, _log, manifest_path=manifest_path)
        except Exception as e:
            _log(f"✗ no se pudo sincronizar: {e}")

    manifest = Manifest(manifest_path)

    enlaces = None
    base_partes = None
    try:
        servicio = conectar_drive(estado_dir)
        enlaces = EnlacesDrive(servicio, estado_dir / "drive_enlaces.json")
        base_partes = ruta_en_mi_unidad(raiz)
    except Exception as e:
        _log(f"Drive no disponible ({e}). Corre: python -m worker.drive")
        enlaces = None

    sb = Supabase(config_sb["SUPABASE_URL"], config_sb["SUPABASE_SERVICE_KEY"],
                  config_sb["BC_USER_ID"])
    run_id = sb.iniciar_corrida()
    api = conectar()

    resultados = {}
    for curso_cfg in cursos:
        nombre = curso_cfg["nombre"]
        try:
            snap = snapshot_curso(api, manifest, curso_cfg, api.base)
        except (LecturaFallida, requests.RequestException) as e:
            _log(f"✗ {nombre}: no se pudo leer de Canvas, no se publica: {e}")
            resultados[nombre] = {"ok": False, "error": str(e)}
            continue

        if enlaces is not None:
            dir_curso = carpeta_curso(raiz, cfg, curso_cfg)
            curso_partes = base_partes + list(Path(dir_curso).relative_to(raiz).parts)
            snap["course"]["drive_url"] = enlaces.enlace(curso_partes)
            for fila in snap["files"]:
                fila["drive_url"] = enlaces.enlace(
                    curso_partes + ["canvas"] + fila["ruta"].split("/"))
        else:
            snap["course"]["drive_url"] = None
            for fila in snap["files"]:
                fila["drive_url"] = None

        primera_vez = not sb.curso_publicado(snap["course"]["canvas_id"])
        conteos = sb.publicar_curso(snap, primera_vez)
        resultados[nombre] = {"ok": True, "conteos": conteos}
        _log(f"  {nombre}: publicado en Supabase {conteos}")

    if enlaces is not None:
        enlaces.guardar()

    ok_total = all(r["ok"] for r in resultados.values())
    sb.cerrar_corrida(run_id, ok_total, resultados)
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


def main(argv=None):
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
        if any(not r.get("ok") for r in resultados.values()):
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
