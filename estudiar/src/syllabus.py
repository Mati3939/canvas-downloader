"""Temario tentativo de una evaluación, con confirmación interactiva."""
import re
import sys
import hashlib
import logging
import subprocess
import html as _html
from pathlib import Path

import claude_cli
from calendar_reader import evaluaciones_del_curso
from utils import ESTUDIAR, carpeta_curso, claude_md_vacio

PROMPT_TEMARIO = ESTUDIAR / "prompts" / "temario.md"
MAX_CHARS_DOC = 40000
MAX_CHARS_SYLLABUS = 30000

SCHEMA = {
    "type": "object",
    "properties": {
        "contenidos": {"type": "array", "items": {"type": "string"}},
        "fundamento": {"type": "array", "items": {"type": "string"}},
        "material": {"type": "array", "items": {
            "type": "object",
            "properties": {"ruta": {"type": "string"}, "motivo": {"type": "string"}},
            "required": ["ruta", "motivo"]}},
        "confianza": {"type": "string", "enum": ["alta", "media", "baja"]},
        "advertencias": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["contenidos", "fundamento", "material", "confianza", "advertencias"],
}


# ---------------------------------------------------------------- texto de archivos

def extraer_texto(path, limite=MAX_CHARS_DOC):
    path = Path(path)
    ext = path.suffix.lower()
    try:
        if ext == ".docx":
            import docx
            d = docx.Document(str(path))
            lineas = [p.text.strip() for p in d.paragraphs if p.text.strip()]
            for t in d.tables:
                for fila in t.rows:
                    celdas = []
                    for c in fila.cells:
                        x = re.sub(r"\s+", " ", c.text).strip()
                        if x and (not celdas or celdas[-1] != x):
                            celdas.append(x)
                    if celdas:
                        lineas.append(" | ".join(celdas))
            texto = "\n".join(lineas)
        elif ext == ".pdf":
            from pypdf import PdfReader
            logging.getLogger("pypdf").setLevel(logging.ERROR)
            texto = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
        elif ext in (".html", ".htm"):
            crudo = path.read_text(encoding="utf-8", errors="replace")
            texto = _html.unescape(re.sub(r"<[^>]+>", " ", crudo))
        elif ext in (".md", ".txt"):
            texto = path.read_text(encoding="utf-8", errors="replace")
        else:
            return ""
    except Exception as e:
        return f"(no se pudo leer {path.name}: {type(e).__name__})"
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto).strip()
    if len(texto) > limite:
        texto = texto[:limite] + "\n[… texto recortado …]"
    return texto


def documentos_calendarizacion(dir_canvas):
    patron = re.compile(r"calendariz|programa|syllabus", re.I)
    return sorted(p for p in Path(dir_canvas).rglob("*")
                  if p.is_file() and patron.search(p.name)
                  and p.suffix.lower() in (".docx", ".pdf"))


# ---------------------------------------------------------------- rutas

def ruta_temario(dir_curso, ev):
    return Path(dir_curso) / "temario" / f"{ev.fecha:%Y-%m-%d}_{ev.slug}.md"


# ---------------------------------------------------------------- generación

def _texto_otras(evals, ev):
    lineas = []
    for e in evals:
        marca = "  ← esta evaluación" if (e.titulo, e.inicio) == (ev.titulo, ev.inicio) else ""
        lineas.append(f"- {e.fecha:%Y-%m-%d}: {e.nombre_corto}{marca}")
    return "\n".join(lineas) or "(sin datos)"


def armar_prompt(cfg, curso, ev, dir_curso):
    dir_canvas = Path(dir_curso) / "canvas"
    claude_md = Path(dir_curso) / "CLAUDE.md"
    texto_md = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""
    if not texto_md or claude_md_vacio(texto_md):
        texto_md = "(vacío: el estudiante aún no lo completa)"
    syllabus = Path(dir_curso) / "syllabus.md"
    texto_syl = extraer_texto(syllabus, MAX_CHARS_SYLLABUS) if syllabus.exists() else "(no hay índice)"
    docs = documentos_calendarizacion(dir_canvas)
    calend = "\n\n".join(f"### {d.relative_to(dir_canvas).as_posix()}\n{extraer_texto(d)}"
                         for d in docs) or "(no hay calendarización en Canvas)"
    reemplazos = {
        "curso": curso["nombre"],
        "evaluacion": ev.nombre_corto,
        "fecha": f"{ev.inicio:%Y-%m-%d %H:%M}" if not ev.todo_el_dia else f"{ev.fecha:%Y-%m-%d}",
        "titulo_evento": ev.titulo,
        "descripcion_evento": ev.descripcion or "(sin descripción)",
        "otras_evaluaciones": _texto_otras(evaluaciones_del_curso(cfg, curso), ev),
        "claude_md": texto_md,
        "syllabus": texto_syl,
        "calendarizacion": calend,
        "max_archivos": str(cfg.get("max_archivos_por_generacion", 15)),
    }
    prompt = PROMPT_TEMARIO.read_text(encoding="utf-8")
    for k, v in reemplazos.items():
        prompt = prompt.replace("{{" + k + "}}", v)
    return prompt, docs


def _render(curso, ev, datos, dir_canvas, fuentes_usadas):
    fecha = f"{ev.inicio:%Y-%m-%d %H:%M}" if not ev.todo_el_dia else f"{ev.fecha:%Y-%m-%d}"
    lineas = [
        f"# Temario tentativo — {ev.nombre_corto} · {curso['nombre']}",
        "",
        f"- **Fecha:** {fecha}{' (aproximada)' if ev.aproximada else ''}",
        f"- **Fuente de la fecha:** Google Calendar («{ev.titulo}»)",
        f"- **Confianza:** {datos.get('confianza', 'baja')}",
        "",
        "> ⚠ **Temario aproximado.** No es un temario oficial: se infirió del material "
        "de abajo. Edítalo si sabes algo más (lo que dijo el profe, un correo, etc.).",
        "",
        "## Contenidos",
        "",
    ]
    lineas += [f"- {c}" for c in datos.get("contenidos", [])] or ["- (sin contenidos)"]
    lineas += ["", "## Por qué este temario", ""]
    lineas += [f"- {f}" for f in datos.get("fundamento", [])]
    if fuentes_usadas:
        lineas.append("- Documentos consultados: " + ", ".join(f"`{f}`" for f in fuentes_usadas))
    if datos.get("advertencias"):
        lineas += ["", "## Dudas y advertencias", ""]
        lineas += [f"- {a}" for a in datos["advertencias"]]
    lineas += ["", "## Material de Canvas para estudiar", "",
               "Rutas relativas a `canvas/`. Se usan para generar la guía: agrega o quita líneas.", ""]
    for m in datos.get("material", []):
        lineas.append(f"- `{m['ruta']}` — {m.get('motivo', '')}")
    return "\n".join(lineas) + "\n"


def _normalizar_material(datos, dir_canvas, maximo):
    """Descarta rutas que no existen en canvas/ (Claude a veces las reescribe)."""
    existentes = {p.relative_to(dir_canvas).as_posix(): p for p in Path(dir_canvas).rglob("*") if p.is_file()}
    por_nombre = {}
    for rel in existentes:
        por_nombre.setdefault(Path(rel).name.lower(), rel)
    validos, descartados = [], []
    for m in datos.get("material", []):
        ruta = str(m.get("ruta", "")).strip().strip("`").replace("\\", "/")
        ruta = re.sub(r"^canvas/", "", ruta)
        if ruta not in existentes:
            ruta = por_nombre.get(Path(ruta).name.lower(), ruta)
        if ruta in existentes and ruta not in [v["ruta"] for v in validos]:
            validos.append({"ruta": ruta, "motivo": m.get("motivo", "")})
        else:
            descartados.append(ruta)
    datos["material"] = validos[:maximo]
    if descartados:
        datos.setdefault("advertencias", []).append(
            f"Se descartaron {len(descartados)} rutas sugeridas que no existen en canvas/.")
    return datos


def generar(cfg, curso, ev, dir_curso, log):
    """Pide el temario a Claude y lo guarda. Devuelve (ruta, incidencias)."""
    dir_canvas = Path(dir_curso) / "canvas"
    prompt, docs = armar_prompt(cfg, curso, ev, dir_curso)
    fuentes = [d.relative_to(dir_canvas).as_posix() for d in docs]
    incidencias = []
    log(f"  Pidiendo a Claude un temario tentativo (≈{len(prompt) // 4:,} tokens de contexto)…")
    modelo = (cfg.get("claude") or {}).get("modelo_temario")
    try:
        r = claude_cli.ejecutar(cfg, prompt, cwd=dir_curso, schema=SCHEMA, modelo=modelo,
                                timeout=600)
        datos = r["structured_output"]
        log(f"  Listo ({claude_cli.resumen_consumo(r)}).")
    except claude_cli.ErrorClaude as e:
        log(f"  ⚠ No se pudo inferir el temario con Claude: {e}")
        incidencias.append(f"temario sin Claude: {e}")
        datos = {
            "contenidos": [ev.descripcion or "(completa los contenidos a mano)"],
            "fundamento": ["Claude no estaba disponible: solo se copió la descripción del evento."],
            "material": [], "confianza": "baja", "advertencias": [],
        }
    datos = _normalizar_material(datos, dir_canvas, int(cfg.get("max_archivos_por_generacion", 15)))
    destino = ruta_temario(dir_curso, ev)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(_render(curso, ev, datos, dir_canvas, fuentes), encoding="utf-8")
    return destino, incidencias


def leer_material(path_temario):
    """Rutas de la sección 'Material de Canvas para estudiar' del temario."""
    texto = Path(path_temario).read_text(encoding="utf-8")
    m = re.search(r"^## Material de Canvas para estudiar\s*$(.*?)(?=^## |\Z)", texto, re.M | re.S)
    if not m:
        return []
    return re.findall(r"^\s*-\s*`([^`]+)`", m.group(1), re.M)


# ---------------------------------------------------------------- confirmación

def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _abrir_editor(path, cfg):
    editor = cfg.get("editor") or "notepad"
    subprocess.run([editor, str(path)])


def confirmar(path, cfg, log, puede_regenerar=False):
    """Muestra el temario y espera la decisión del usuario.
    Devuelve 'confirmado', 'editado', 'saltado', 'regenerar' o 'sin_terminal'."""
    if not sys.stdin or not sys.stdin.isatty():
        log("\n⚠ No hay terminal interactiva: no puedo pedir confirmación del temario, "
            "así que no se genera la guía.")
        return "sin_terminal"
    original = _hash(path)
    while True:
        print("\n" + "═" * 70)
        print(Path(path).read_text(encoding="utf-8"))
        print("═" * 70)
        print(f"Archivo: {path}")
        opciones = "[Enter] confirmar / [e] editar / [s] saltar este ramo"
        if puede_regenerar:
            opciones += " / [r] regenerar"
        try:
            r = input(f"{opciones}\n> ").strip().lower()
        except EOFError:
            log("\n⚠ No se pudo leer la respuesta (entrada cerrada): no se genera la guía.")
            return "sin_terminal"
        if r == "":
            estado = "confirmado" if _hash(path) == original else "editado"
            log(f"  Temario {estado}: {Path(path).name}")
            return estado
        if r == "e":
            _abrir_editor(path, cfg)
        elif r == "s":
            log("  Ramo saltado.")
            return "saltado"
        elif r == "r" and puede_regenerar:
            return "regenerar"
        else:
            print("Opción no válida.")


def preparar_temario(cfg, curso, ev, raiz, log, dry_run=False):
    """Genera (o reutiliza) el temario y lo confirma. Devuelve un dict con
    'estado', 'ruta' e 'incidencias'."""
    dir_curso = carpeta_curso(raiz, cfg, curso)
    destino = ruta_temario(dir_curso, ev)
    if dry_run:
        prompt, docs = armar_prompt(cfg, curso, ev, dir_curso)
        log(f"  (dry-run) Se generaría {destino.relative_to(dir_curso).as_posix()} "
            f"con ≈{len(prompt) // 4:,} tokens de contexto y {len(docs)} documento(s) de calendarización.")
        return {"estado": "dry_run", "ruta": destino, "incidencias": []}
    incidencias = []
    reutilizado = destino.exists()
    if reutilizado:
        log(f"  Ya existe un temario para esta evaluación: {destino.name} (se reutiliza).")
    else:
        destino, incidencias = generar(cfg, curso, ev, dir_curso, log)
    while True:
        estado = confirmar(destino, cfg, log, puede_regenerar=True)
        if estado != "regenerar":
            break
        destino, inc = generar(cfg, curso, ev, dir_curso, log)
        incidencias += inc
    return {"estado": estado, "ruta": destino, "incidencias": incidencias,
            "reutilizado": reutilizado}
