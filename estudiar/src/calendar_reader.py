"""Lee el calendario (ICS) y detecta la próxima evaluación de cada ramo."""
import re
import sys
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from utils import STATE_DIR, ErrorFatal, guardar_json_atomico, leer_env, normalizar

ZONA = ZoneInfo("America/Santiago")
CACHE_ICS = STATE_DIR / "calendario.ics"
ASOCIACIONES_FILE = STATE_DIR / "calendario_asociaciones.json"
_APROX = re.compile(r"aprox|por confirmar|confirmar\]", re.I)


@dataclass
class Evaluacion:
    titulo: str
    inicio: datetime
    todo_el_dia: bool
    descripcion: str = ""
    aproximada: bool = False
    curso: dict = field(default=None, repr=False)

    @property
    def fecha(self):
        return self.inicio.date()

    @property
    def nombre_corto(self):
        """'Certamen 2 - Cálculo Multivariable' -> 'Certamen 2'."""
        t = re.sub(r"\[.*?\]", "", self.titulo)
        t = re.sub(r"\((ayudant[ií]a|[^)]*%[^)]*)\)", "", t, flags=re.I)
        if self.curso:
            palabras = [self.curso["nombre"], *self.curso["palabras_calendario"]]
            partes = [p for p in re.split(r"\s+[-–—|]\s+", t)
                      if not any(_contiene(normalizar(p), k) for k in palabras)]
            if partes:
                t = " - ".join(partes)
            else:
                # Sin separador ("Certamen 1 TOPD"): se quita la palabra del ramo.
                for k in sorted(palabras, key=len, reverse=True):
                    t = re.sub(rf"(?<!\w){re.escape(k)}(?!\w)", "", t, flags=re.I)
        return re.sub(r"\s{2,}", " ", t).strip(" -–—|:") or self.titulo

    @property
    def slug(self):
        s = normalizar(self.nombre_corto)
        s = re.sub(r"n[°º]\s*", "", s)
        return re.sub(r"[^a-z0-9]+", "", s) or "evaluacion"

    def cuando(self):
        if self.todo_el_dia:
            return f"{self.fecha:%d/%m}"
        return f"{self.inicio:%d/%m %H:%M}"


# ---------------------------------------------------------------- descarga

def _urls(env):
    crudo = env.get("CALENDAR_ICS_URL") or ""
    return [u for u in re.split(r"[\s,]+", crudo) if u]


def descargar_ics(log):
    """Baja los ICS configurados. Si falla la red usa la última copia guardada.
    Devuelve una lista de bytes (un ICS por URL)."""
    urls = _urls(leer_env())
    if not urls:
        raise ErrorFatal("Falta CALENDAR_ICS_URL en el .env (dirección secreta iCal de Google Calendar).")
    contenidos, fallo = [], None
    for i, url in enumerate(urls):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            if b"BEGIN:VCALENDAR" not in r.content[:200]:
                raise ValueError("la respuesta no es un calendario ICS")
            contenidos.append(r.content)
        except (requests.RequestException, ValueError) as e:
            fallo = e
            break
    if fallo is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_ICS.write_bytes(b"\n".join(contenidos))
        return contenidos
    if CACHE_ICS.exists():
        guardado = datetime.fromtimestamp(CACHE_ICS.stat().st_mtime)
        log(f"⚠ No pude descargar el calendario ({type(fallo).__name__}). "
            f"Uso la copia del {guardado:%d/%m %H:%M}.")
        crudo = CACHE_ICS.read_bytes()
        return [b"BEGIN:VCALENDAR" + p for p in crudo.split(b"BEGIN:VCALENDAR") if p.strip()]
    raise ErrorFatal(f"No pude descargar el calendario y no hay copia guardada: {fallo}")


# ---------------------------------------------------------------- parseo

def _como_datetime(valor):
    if isinstance(valor, datetime):
        return (valor if valor.tzinfo else valor.replace(tzinfo=ZONA)).astimezone(ZONA), False
    return datetime(valor.year, valor.month, valor.day, tzinfo=ZONA), True


def eventos(contenidos, desde, hasta):
    import icalendar
    import recurring_ical_events
    lista = []
    for ics in contenidos:
        cal = icalendar.Calendar.from_ical(ics)
        for ev in recurring_ical_events.of(cal).between(desde, hasta):
            inicio, todo_dia = _como_datetime(ev.get("DTSTART").dt)
            titulo = str(ev.get("SUMMARY") or "").strip()
            desc = str(ev.get("DESCRIPTION") or "").strip()
            lista.append(Evaluacion(titulo=titulo, inicio=inicio, todo_el_dia=todo_dia,
                                    descripcion=desc,
                                    aproximada=bool(_APROX.search(titulo))))
    lista.sort(key=lambda e: e.inicio)
    return lista


def _contiene(texto_norm, palabra):
    p = normalizar(palabra)
    return bool(p) and re.search(rf"(?<![a-z0-9]){re.escape(p)}(?![a-z0-9])", texto_norm) is not None


def es_evaluacion(ev, keywords):
    texto = normalizar(f"{ev.titulo}\n{ev.descripcion}")
    return any(_contiene(texto, k) for k in keywords)


def candidatos(ev, cursos):
    """Cursos cuyas palabras aparecen en el título (o, si no, en la descripción),
    ordenados por la coincidencia más larga."""
    for texto in (ev.titulo, ev.descripcion):
        t = normalizar(texto)
        puntajes = []
        for c in cursos:
            largos = [len(normalizar(k)) for k in [c["nombre"], *c["palabras_calendario"]]
                      if _contiene(t, k)]
            if largos:
                puntajes.append((max(largos), c))
        if puntajes:
            puntajes.sort(key=lambda x: -x[0])
            mejor = puntajes[0][0]
            return [c for p, c in puntajes if p == mejor]
    return []


# ---------------------------------------------------------------- asociación

def _cargar_asociaciones():
    if ASOCIACIONES_FILE.exists():
        return json.loads(ASOCIACIONES_FILE.read_text(encoding="utf-8"))
    return {}


def _preguntar_curso(ev, opciones, log):
    """Pregunta a qué ramo corresponde un evento. Devuelve el id de Canvas,
    'ignorar' o None (si no hay terminal interactiva)."""
    if not sys.stdin or not sys.stdin.isatty():
        return None
    log(f"\n? No sé a qué ramo corresponde: «{ev.titulo}» ({ev.cuando()})")
    for i, c in enumerate(opciones, 1):
        log(f"    [{i}] {c['nombre']}")
    log("    [i] ignorar siempre   [Enter] saltar por ahora")
    while True:
        r = input("    > ").strip().lower()
        if r == "":
            return None
        if r == "i":
            return "ignorar"
        if r.isdigit() and 1 <= int(r) <= len(opciones):
            return opciones[int(r) - 1]["canvas_course_id"]
        print("    Opción no válida.")


def asociar(evals, cfg, log, interactivo=True):
    """Asigna ev.curso a cada evaluación. Devuelve las que no se pudieron asociar."""
    cursos = cfg["cursos"]
    por_id = {c["canvas_course_id"]: c for c in cursos}
    ignorar = [normalizar(x) for x in cfg.get("calendario_ignorar", [])]
    memoria = _cargar_asociaciones()
    cambios = False
    sin_asociar = []
    for ev in evals:
        clave = normalizar(ev.titulo)
        if any(_contiene(clave, x) for x in ignorar):
            continue
        guardado = memoria.get(clave)
        if guardado == "ignorar":
            continue
        if guardado in por_id:
            ev.curso = por_id[guardado]
            continue
        opciones = candidatos(ev, cursos)
        if len(opciones) == 1:
            ev.curso = opciones[0]
            continue
        respuesta = _preguntar_curso(ev, opciones or cursos, log) if interactivo else None
        if respuesta is None:
            sin_asociar.append(ev)
            continue
        memoria[clave] = respuesta
        cambios = True
        if respuesta != "ignorar":
            ev.curso = por_id[respuesta]
    if cambios:
        guardar_json_atomico(ASOCIACIONES_FILE, memoria)
    return sin_asociar


# ---------------------------------------------------------------- API del módulo

def proximas_evaluaciones(cfg, log, ahora=None, interactivo=True):
    """Devuelve (proximas, sin_asociar):
    - proximas: {canvas_course_id: Evaluacion} con la próxima evaluación de cada
      ramo donde el usuario es estudiante, dentro de `dias_horizonte`;
    - sin_asociar: evaluaciones que no se pudieron atribuir a ningún ramo."""
    ahora = ahora or datetime.now(ZONA)
    hoy = ahora.date()
    hasta = hoy + timedelta(days=int(cfg.get("dias_horizonte", 30)) + 1)
    contenidos = descargar_ics(log)
    evals = [e for e in eventos(contenidos, hoy, hasta)
             if es_evaluacion(e, cfg.get("evaluacion_keywords", []))]
    # Un evento de todo el día cuenta hasta que termina ese día.
    evals = [e for e in evals if (e.fecha >= hoy if e.todo_el_dia else e.inicio >= ahora)]
    sin_asociar = asociar(evals, cfg, log, interactivo=interactivo)
    proximas = {}
    for e in evals:
        if e.curso is None or e.curso.get("rol") != "estudiante":
            continue
        proximas.setdefault(e.curso["canvas_course_id"], e)
    return proximas, sin_asociar


def imprimir_proximas(cfg, proximas, sin_asociar, log, ahora=None):
    hoy = (ahora or datetime.now(ZONA)).date()
    log(f"\n──────── Próximas evaluaciones (próximos {cfg.get('dias_horizonte', 30)} días) ────────")
    orden = sorted(proximas.values(), key=lambda e: e.inicio)
    for e in orden:
        dias = (e.fecha - hoy).days
        cuando = "hoy" if dias == 0 else "mañana" if dias == 1 else f"en {dias} días"
        aviso = "  (fecha aproximada)" if e.aproximada else ""
        log(f"  {e.cuando():<12} {cuando:<12} {e.curso['nombre']}: {e.nombre_corto}{aviso}")
    faltan = [c["nombre"] for c in cfg["cursos"]
              if c["rol"] == "estudiante" and c["canvas_course_id"] not in proximas]
    if faltan:
        log(f"  Sin evaluaciones en el horizonte: {', '.join(faltan)}")
    if sin_asociar:
        log("  Eventos de evaluación sin ramo asociado (agrega palabras en "
            "`palabras_calendario` o en `calendario_ignorar` de config.yaml):")
        for e in sin_asociar:
            log(f"    - {e.cuando()}  {e.titulo}")
    return orden
