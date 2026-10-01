"""registro.md por ramo: historial de ejecuciones pensado para que otro Claude
(p. ej. el proyecto de Cowork del ramo) entienda qué se hizo y con qué material."""
import re
from datetime import datetime
from pathlib import Path

MAX_LINEAS = 300
DETALLADAS = 10
MARCA_ENTRADAS = "<!-- entradas -->"

ENCABEZADO = """# Registro de ejecuciones — {curso}

Historial que escribe automáticamente el programa `estudiar` cada vez que trabaja con
este ramo: archivos nuevos de Canvas, evaluación detectada en el calendario, temario
usado y guía generada. Sirve para que cualquier asistente que abra esta carpeta sepa
qué material se usó en cada guía y no repita ejercicios. No lo edites a mano: las
entradas nuevas se agregan al final.

{marca}
"""


def _ruta_rel(path, dir_curso):
    try:
        return Path(path).relative_to(dir_curso).as_posix()
    except ValueError:
        return Path(path).name


def _lista(items, vacio="ninguno"):
    if not items:
        return f" {vacio}"
    return "".join(f"\n  - {i}" for i in items)


def armar_entrada(dir_curso, *, ev=None, sync=None, temario=None, guia=None, ahora=None):
    """Arma el texto de una entrada. Cualquier parte puede faltar."""
    ahora = ahora or datetime.now()
    titulo = ev.nombre_corto if ev else "Sincronización"
    lineas = [f"## {ahora:%Y-%m-%d %H:%M} — {titulo}"]
    incidencias = []

    if ev:
        aprox = ", aproximada" if ev.aproximada else ""
        lineas.append(f"- **Evaluación:** {ev.nombre_corto} (fecha: {ev.fecha:%Y-%m-%d}{aprox}), "
                      "fuente: Google Calendar")

    if sync is None:
        lineas.append("- **Archivos nuevos desde la última ejecución:** no se sincronizó (--sin-descarga)")
    else:
        nuevos = [f"`{a['ruta']}` (módulo: {a.get('modulo') or '—'})" for a in sync["nuevos"]]
        nuevos += [f"`{a['ruta']}` (actualizado; módulo: {a.get('modulo') or '—'})"
                   for a in sync["actualizados"]]
        lineas.append("- **Archivos nuevos desde la última ejecución:**" + _lista(nuevos))
        incidencias += [f"omitido en Canvas: {o}" for o in sync.get("omitidos", [])]
        incidencias += [f"error de sincronización: {e}" for e in sync.get("errores", [])]

    if temario:
        rel = _ruta_rel(temario["ruta"], dir_curso)
        estados = {
            "confirmado": "confirmado tal cual",
            "editado": "editado por el estudiante antes de confirmar",
            "saltado": "el estudiante saltó este ramo (no se generó guía)",
            "sin_terminal": "sin confirmar (no había terminal interactiva)",
        }
        estado = estados.get(temario["estado"], temario["estado"])
        if temario.get("reutilizado"):
            estado += "; se reutilizó un temario ya existente"
        lineas.append(f"- **Temario:** [{rel}]({rel}) — {estado}")
        incidencias += temario.get("incidencias", [])

    if guia:
        lineas.append("- **Archivos usados en la generación:**"
                      + _lista([f"`canvas/{a}`" for a in guia.get("archivos", [])]))
        if guia["estado"] == "generada":
            rel = _ruta_rel(guia["pdf"], dir_curso)
            lineas.append(f"- **Guía generada:** [{rel}]({rel})")
        else:
            lineas.append(f"- **Guía generada:** no generada ({guia.get('motivo', 'sin motivo')})")
        incidencias += guia.get("incidencias", [])
    elif temario:
        lineas.append("- **Guía generada:** no generada (temario no confirmado)")

    lineas.append("- **Incidencias:**" + _lista(incidencias, vacio="ninguna"))
    return "\n".join(lineas) + "\n"


def agregar(dir_curso, nombre_curso, entrada):
    """Agrega la entrada al final de registro.md (lo crea si no existe) y compacta
    si el archivo se hizo demasiado largo."""
    path = Path(dir_curso) / "registro.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(ENCABEZADO.format(curso=nombre_curso, marca=MARCA_ENTRADAS), encoding="utf-8")
    texto = path.read_text(encoding="utf-8")
    if not texto.endswith("\n"):
        texto += "\n"
    texto += "\n" + entrada
    if texto.count("\n") > MAX_LINEAS:
        texto = compactar(texto)
    path.write_text(texto, encoding="utf-8")
    return path


# ---------------------------------------------------------------- compactación

_ENTRADA = re.compile(r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2} — .*$", re.M)


def compactar(texto):
    """Deja detalladas las últimas DETALLADAS entradas y resume las anteriores por
    evaluación en una sección al inicio (que se va acumulando)."""
    if MARCA_ENTRADAS not in texto:
        return texto
    cabecera, cuerpo = texto.split(MARCA_ENTRADAS, 1)
    inicios = [m.start() for m in _ENTRADA.finditer(cuerpo)]
    if len(inicios) <= DETALLADAS:
        return texto
    entradas = [cuerpo[a:b].strip() for a, b in zip(inicios, inicios[1:] + [len(cuerpo)])]
    viejas, recientes = entradas[:-DETALLADAS], entradas[-DETALLADAS:]

    resumen = {}
    for e in viejas:
        fecha = e[3:13]
        m_ev = re.search(r"\*\*Evaluación:\*\* (.+?) \(fecha: ([\d-]+)", e)
        clave = f"{m_ev.group(1)} ({m_ev.group(2)})" if m_ev else "Sincronizaciones"
        r = resumen.setdefault(clave, {"ejecuciones": 0, "desde": fecha, "hasta": fecha,
                                       "guias": [], "archivos": 0})
        r["ejecuciones"] += 1
        r["hasta"] = fecha
        r["archivos"] += len(re.findall(r"^\s+- `", e.split("**Temario", 1)[0], re.M))
        m_g = re.search(r"\*\*Guía generada:\*\* \[([^\]]+)\]", e)
        if m_g and m_g.group(1) not in r["guias"]:
            r["guias"].append(m_g.group(1))

    lineas = []
    for clave, r in resumen.items():
        guias = ", ".join(f"[{g}]({g})" for g in r["guias"]) or "ninguna"
        lineas.append(f"- **{clave}:** {r['ejecuciones']} ejecuciones entre {r['desde']} y "
                      f"{r['hasta']}; {r['archivos']} archivos nuevos de Canvas; guías: {guias}")

    titulo = "## Resumen de ejecuciones anteriores"
    if titulo in cabecera:
        cabecera = cabecera.rstrip() + "\n" + "\n".join(lineas) + "\n\n"
    else:
        cabecera = (cabecera.rstrip() + f"\n\n{titulo}\n\nEntradas antiguas agrupadas por "
                    "evaluación (las últimas ejecuciones siguen en detalle más abajo).\n\n"
                    + "\n".join(lineas) + "\n\n")
    return cabecera + MARCA_ENTRADAS + "\n\n" + "\n\n".join(recientes) + "\n"
