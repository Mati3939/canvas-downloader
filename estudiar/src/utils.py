"""Utilidades comunes: rutas, configuración, logging sin secretos, Drive y CLAUDE.md."""
import os
import re
import sys
import json
import functools
import unicodedata
from datetime import datetime
from pathlib import Path

ESTUDIAR = Path(__file__).resolve().parent.parent
REPO = ESTUDIAR.parent
STATE_DIR = ESTUDIAR / "state"
LOGS_DIR = ESTUDIAR / "logs"
CONFIG_FILE = ESTUDIAR / "config.yaml"
DOTENV_FILE = REPO / ".env"

# El núcleo del descargador vive en la raíz del repo: se importa, no se copia.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from canvas_descargar import _leer_dotenv, limpiar as _limpiar_nucleo  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


class ErrorFatal(Exception):
    """Error que detiene la ejecución con un mensaje claro para el usuario."""


# ---------------------------------------------------------------- configuración

def leer_env():
    """Variables del .env del repo; las variables de entorno tienen prioridad."""
    valores = _leer_dotenv(DOTENV_FILE)
    for clave in ("CANVAS_BASE_URL", "CANVAS_URL", "CANVAS_TOKEN",
                  "CALENDAR_ICS_URL", "DRIVE_ROOT"):
        if os.environ.get(clave):
            valores[clave] = os.environ[clave]
    return valores


def cargar_config():
    import yaml
    if not CONFIG_FILE.exists():
        raise ErrorFatal(f"No existe {CONFIG_FILE.name}. Copia config.example.yaml "
                         "como config.yaml y completa tus ramos.")
    cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    cursos = cfg.get("cursos") or []
    if not cursos:
        raise ErrorFatal("config.yaml no tiene cursos.")
    for c in cursos:
        for campo in ("nombre", "canvas_course_id", "carpeta"):
            if not c.get(campo):
                raise ErrorFatal(f"Un curso de config.yaml no tiene '{campo}': {c}")
        c.setdefault("rol", "estudiante")
        c.setdefault("palabras_calendario", [])
    cfg.setdefault("semestre", "")
    cfg.setdefault("canvas", {}).setdefault("fuentes", ["modulos", "archivos", "tareas"])
    return cfg


def normalizar(texto):
    """Minúsculas y sin tildes, para comparar nombres."""
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(ch for ch in t if not unicodedata.combining(ch)).lower().strip()


def buscar_curso(cfg, texto):
    """Cursos de config cuyo nombre o carpeta contiene `texto` (sin tildes)."""
    q = normalizar(texto)
    return [c for c in cfg["cursos"]
            if q in normalizar(c["nombre"]) or q in normalizar(c["carpeta"])]


def limpiar(nombre):
    """Nombre válido en Windows (el núcleo no quita puntos ni espacios finales)."""
    return _limpiar_nucleo(nombre).rstrip(". ") or "sin_nombre"


# ---------------------------------------------------------------- logging

_URL_CON_QUERY = re.compile(r"(https?://[^\s?\"'<>]+)\?[^\s\"'<>]*")
_ICS_PRIVADO = re.compile(r"(calendar/ical/)[^\s\"'<>]+")
_BEARER = re.compile(r"(Bearer\s+)\S+", re.I)


def sanitizar(texto):
    """Quita de un mensaje lo que puede ser secreto: parámetros de URLs (los
    enlaces de descarga de Canvas llevan un `verifier`), direcciones privadas
    de calendario y tokens."""
    t = str(texto)
    t = _URL_CON_QUERY.sub(r"\1?…", t)
    t = _ICS_PRIVADO.sub(r"\1…", t)
    t = _BEARER.sub(r"\1…", t)
    for secreto in _secretos():
        t = t.replace(secreto, "…")
    return t


@functools.lru_cache(maxsize=1)
def _secretos():
    env = leer_env()
    return tuple(v for k in ("CANVAS_TOKEN", "CALENDAR_ICS_URL")
                 if (v := env.get(k)) and len(v) > 8)


class Log:
    """Imprime en consola y agrega al log del día en logs/, siempre sanitizado."""

    def __init__(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.archivo = LOGS_DIR / f"estudiar_{datetime.now():%Y-%m-%d}.log"

    def __call__(self, msg=""):
        msg = sanitizar(msg)
        print(msg, flush=True)
        try:
            with open(self.archivo, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%H:%M:%S} {msg}\n")
        except OSError:
            pass


# ---------------------------------------------------------------- archivos

def guardar_json_atomico(path, datos):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def escribir_si_cambia(path, texto):
    """Escribe el archivo solo si el contenido cambió. Devuelve True si escribió."""
    path = Path(path)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == texto:
                return False
        except (OSError, UnicodeDecodeError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texto, encoding="utf-8")
    return True


# ---------------------------------------------------------------- Drive

def resolver_drive_root(env, override=None):
    ruta = override or env.get("DRIVE_ROOT")
    if not ruta:
        raise ErrorFatal("Falta DRIVE_ROOT en el .env (carpeta sincronizada con Google Drive).")
    return Path(ruta)


def verificar_drive_root(raiz, escribir=True):
    """Comprueba que la carpeta de Drive existe y se puede escribir. Nunca se
    escribe en otro lugar si esto falla."""
    raiz = Path(raiz)
    if not raiz.is_dir():
        raise ErrorFatal(
            f"No encuentro la carpeta de Drive: {raiz}\n"
            "  ¿Está abierto Google Drive para escritorio y montada la unidad?")
    if escribir:
        prueba = raiz / f".estudiar_prueba_{os.getpid()}"
        try:
            prueba.write_text("ok", encoding="utf-8")
            prueba.unlink()
        except OSError as e:
            raise ErrorFatal(f"No puedo escribir en {raiz}: {e}\n"
                             "  Revisa que Google Drive esté corriendo y con sesión iniciada.")


def carpeta_curso(raiz, cfg, curso):
    base = Path(raiz)
    if cfg.get("semestre"):
        base = base / limpiar(cfg["semestre"])
    return base / limpiar(curso["carpeta"])


# ---------------------------------------------------------------- CLAUDE.md

CLAUDE_MD_SECCIONES = [
    ("Formalidades del curso",
     "(notación, convenciones, cómo se espera que se justifiquen las respuestas, criterios del profe)"),
    ("Diferencias con libros u otras universidades", ""),
    ("Estilo de evaluación", "(tipo de preguntas, puntaje, ponderaciones)"),
    ("Notas", ""),
]


def plantilla_claude_md(nombre):
    partes = [f"# {nombre}"]
    for titulo, ayuda in CLAUDE_MD_SECCIONES:
        partes.append(f"## {titulo}")
        if ayuda:
            partes.append(ayuda)
    return "\n".join(partes) + "\n"


def claude_md_vacio(texto):
    """True si el CLAUDE.md solo tiene encabezados y los textos de ayuda."""
    ayudas = {normalizar(a) for _, a in CLAUDE_MD_SECCIONES if a}
    for linea in texto.splitlines():
        l = linea.strip()
        if not l or l.startswith("#"):
            continue
        if normalizar(l) in ayudas:
            continue
        return False
    return True


def asegurar_claude_md(carpeta, nombre, crear=True):
    """Crea CLAUDE.md si falta. Devuelve 'creado', 'vacio', 'ok' o 'falta'."""
    path = Path(carpeta) / "CLAUDE.md"
    if not path.exists():
        if not crear:
            return "falta"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plantilla_claude_md(nombre), encoding="utf-8")
        return "creado"
    return "vacio" if claude_md_vacio(path.read_text(encoding="utf-8")) else "ok"
