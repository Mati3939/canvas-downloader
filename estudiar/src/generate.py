"""Genera la guía de estudio: `claude -p` escribe el .tex y se compila a PDF."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import claude_cli
from syllabus import extraer_texto, leer_material, ruta_temario
from utils import ESTUDIAR, carpeta_curso, claude_md_vacio, normalizar

PROMPT_GUIA = ESTUDIAR / "prompts" / "guia_estudio.md"
MAX_REINTENTOS_LATEX = 2
LEIBLES_POR_CLAUDE = {".pdf", ".png", ".jpg", ".jpeg", ".ipynb", ".txt", ".md", ".csv", ".py", ".sql"}
MAX_CHARS_EXTRAIDO = 15000
AUXILIARES = (".aux", ".log", ".out", ".toc", ".synctex.gz", ".fls", ".fdb_latexmk")


# ---------------------------------------------------------------- selección de material

def seleccionar_material(cfg, dir_curso, temario_path, ev):
    """Archivos para la generación: los del temario confirmado (que el usuario
    pudo editar), hasta `max_archivos_por_generacion`. Devuelve (usados, omitidos)."""
    maximo = int(cfg.get("max_archivos_por_generacion", 15))
    dir_canvas = Path(dir_curso) / "canvas"
    rutas = []
    for r in leer_material(temario_path):
        r = r.replace("\\", "/").removeprefix("canvas/")
        if (dir_canvas / r).is_file() and r not in rutas:
            rutas.append(r)
    if not rutas:
        rutas = _material_por_nombre(dir_canvas, ev)
    return rutas[:maximo], rutas[maximo:]


def _material_por_nombre(dir_canvas, ev):
    """Respaldo si el temario no lista material: evaluaciones anteriores del
    mismo tipo, guías, listados y ayudantías."""
    tipo = normalizar(ev.nombre_corto).split(" ")[0]
    patrones = [tipo, "guia", "listado", "ayudant", "pauta"]
    candidatos = []
    for p in Path(dir_canvas).rglob("*"):
        if p.is_file() and p.suffix.lower() in LEIBLES_POR_CLAUDE | {".docx"}:
            nombre = normalizar(p.name)
            puntaje = next((i for i, pat in enumerate(patrones) if pat and pat in nombre), None)
            if puntaje is not None:
                candidatos.append((puntaje, -p.stat().st_mtime, p.relative_to(dir_canvas).as_posix()))
    return [r for _, _, r in sorted(candidatos)]


# ---------------------------------------------------------------- referencia de estilo

def referencia_estilo(cfg, curso):
    """Texto de las primeras páginas de la guía anterior más reciente del ramo."""
    raiz = cfg.get("referencias_estilo")
    if not raiz or not Path(raiz).is_dir():
        return None, "(no hay guías anteriores configuradas)"

    def guias_en(base):
        if not base.is_dir():
            return []
        return [p for p in base.rglob("*.pdf")
                if "guia" in normalizar(p.name)
                and "vigia" not in normalizar(str(p.relative_to(raiz)))]

    # Primero las del mismo ramo; si no hay, cualquiera del semestre (el estilo es el mismo).
    carpeta = curso.get("carpeta_referencia")
    guias = guias_en(Path(raiz) / carpeta) if carpeta else []
    guias = guias or guias_en(Path(raiz))
    if not guias:
        return None, "(no hay guías anteriores en PDF)"
    guia = max(guias, key=lambda p: p.stat().st_mtime)
    try:
        import logging
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        paginas = PdfReader(str(guia)).pages[:2]
        texto = "\n".join(p.extract_text() or "" for p in paginas)
    except Exception as e:
        return guia, f"(no se pudo leer {guia.name}: {type(e).__name__})"
    return guia, texto[:4000]


# ---------------------------------------------------------------- prompt

def armar_prompt(cfg, curso, ev, dir_curso, temario_path, archivos, archivo_tex):
    dir_curso = Path(dir_curso)
    claude_md = dir_curso / "CLAUDE.md"
    texto_md = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""
    if not texto_md or claude_md_vacio(texto_md):
        texto_md = "(vacío: usa convenciones estándar y sé explícito en las justificaciones)"

    lista, extraidos = [], []
    for r in archivos:
        p = dir_curso / "canvas" / r
        if p.suffix.lower() in LEIBLES_POR_CLAUDE:
            lista.append(f"- `canvas/{r}`")
        else:
            lista.append(f"- `canvas/{r}` (texto incluido abajo)")
            extraidos.append(f"### canvas/{r}\n{extraer_texto(p, MAX_CHARS_EXTRAIDO)}")
    textos = ("## Texto de los archivos que no puedes abrir directamente\n\n" + "\n\n".join(extraidos)
              if extraidos else "")

    registro = dir_curso / "registro.md"
    if registro.exists():
        texto_registro = ("Lee `registro.md` antes de empezar: ahí están las guías anteriores de este "
                          "ramo y con qué material se hicieron. No repitas sus ejercicios y mantén la "
                          "continuidad con ellas.")
    else:
        texto_registro = "(es la primera guía que se genera para este ramo)"

    _, estilo = referencia_estilo(cfg, curso)
    fecha = f"{ev.fecha:%Y-%m-%d}" + ("" if ev.todo_el_dia else f" {ev.inicio:%H:%M}")
    reemplazos = {
        "curso": curso["nombre"],
        "evaluacion": ev.nombre_corto,
        "fecha": fecha,
        "temario": Path(temario_path).read_text(encoding="utf-8"),
        "claude_md": texto_md,
        "archivos": "\n".join(lista) or "(no hay material seleccionado)",
        "textos_extraidos": textos,
        "registro": texto_registro,
        "referencia_estilo": estilo,
        "archivo_tex": archivo_tex,
    }
    prompt = PROMPT_GUIA.read_text(encoding="utf-8")
    for k, v in reemplazos.items():
        prompt = prompt.replace("{{" + k + "}}", v)
    return prompt


# ---------------------------------------------------------------- LaTeX

def detectar_compilador():
    for nombre in ("tectonic", "pdflatex", "xelatex"):
        ruta = shutil.which(nombre)
        if ruta:
            return nombre, ruta
    return None, None


def compilar(tex, timeout=600):
    """Compila el .tex en su carpeta. Devuelve (ok, error_resumido)."""
    tex = Path(tex)
    nombre, ruta = detectar_compilador()
    if not ruta:
        return False, None
    if nombre == "tectonic":
        comandos = [[ruta, "--keep-logs", tex.name]]
    else:
        base = [ruta, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
        if nombre == "pdflatex" or nombre == "xelatex":
            base.append("-enable-installer")  # MiKTeX: instala paquetes faltantes sin preguntar
        comandos = [base + [tex.name]] * 2    # dos pasadas para referencias y hyperref
    for cmd in comandos:
        try:
            proc = subprocess.run(cmd, cwd=str(tex.parent), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "La compilación superó el tiempo límite."
        if proc.returncode != 0:
            return False, _resumen_error(tex, proc.stdout + proc.stderr)
    return tex.with_suffix(".pdf").exists(), None


def _resumen_error(tex, salida):
    log = tex.with_suffix(".log")
    texto = log.read_text(encoding="utf-8", errors="replace") if log.exists() else salida
    lineas = texto.splitlines()
    trozos = []
    for i, l in enumerate(lineas):
        if l.startswith("!") or re.search(r"\.tex:\d+:", l):
            trozos.append("\n".join(lineas[i:i + 6]))
        if len(trozos) >= 4:
            break
    return ("\n---\n".join(trozos) or "\n".join(lineas[-30:]))[:3000]


def limpiar_auxiliares(tex):
    for ext in AUXILIARES:
        p = Path(tex).with_suffix(ext)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------- flujo

def _herramientas():
    return {"tools": "Read,Write,Edit",
            "allowed_tools": ["Read(./**)", "Write(./guias/**)", "Edit(./guias/**)"],
            "permission_mode": "dontAsk"}


def generar_guia(cfg, curso, ev, raiz, log, temario_path=None, dry_run=False):
    """Devuelve un dict con 'estado', 'pdf', 'tex', 'archivos', 'omitidos',
    'incidencias' (se usa también para registro.md)."""
    dir_curso = carpeta_curso(raiz, cfg, curso)
    temario_path = Path(temario_path or ruta_temario(dir_curso, ev))
    stem = temario_path.stem
    tex = dir_curso / "guias" / f"{stem}.tex"
    pdf = tex.with_suffix(".pdf")
    rel_tex = f"guias/{tex.name}"
    usados, omitidos = seleccionar_material(cfg, dir_curso, temario_path, ev)
    resultado = {"estado": "no_generada", "pdf": pdf, "tex": tex, "archivos": usados,
                 "omitidos": omitidos, "incidencias": []}
    if omitidos:
        resultado["incidencias"].append(
            f"{len(omitidos)} archivos del temario quedaron fuera por el límite de "
            f"{cfg.get('max_archivos_por_generacion', 15)}")

    compilador, _ = detectar_compilador()
    log(f"\n  Material para la guía ({len(usados)} archivos):")
    for r in usados:
        log(f"    - {r}")
    if omitidos:
        log(f"  ({len(omitidos)} más quedaron fuera por el límite de archivos por generación)")
    if not compilador:
        log("  ✗ No hay compilador LaTeX (tectonic, pdflatex o xelatex). Instala tectonic "
            "(winget install TectonicProject.Tectonic) o MiKTeX.")
        resultado["motivo"] = "sin compilador LaTeX"
        return resultado
    if dry_run:
        log(f"  (dry-run) Claude escribiría {rel_tex} y se compilaría con {compilador}.")
        resultado["estado"] = "dry_run"
        return resultado
    if not usados:
        log("  ⚠ No hay material de Canvas seleccionado: la guía se basará solo en el temario.")
        resultado["incidencias"].append("sin material de Canvas seleccionado")

    tex.parent.mkdir(parents=True, exist_ok=True)
    if tex.exists():
        tex.unlink()  # evita confundir un .tex viejo con uno nuevo
    prompt = armar_prompt(cfg, curso, ev, dir_curso, temario_path, usados, rel_tex)
    modelo = (cfg.get("claude") or {}).get("modelo_guia")
    log(f"\n  Generando la guía con Claude (puede tardar varios minutos)…")
    try:
        r = claude_cli.ejecutar(cfg, prompt, cwd=dir_curso, modelo=modelo, **_herramientas())
        log(f"  Claude terminó ({claude_cli.resumen_consumo(r)}): {str(r.get('result', '')).strip()[:200]}")
    except claude_cli.ErrorClaude as e:
        log(f"  ✗ {e}")
        resultado["motivo"] = f"falló Claude: {e}"
        return resultado
    if not tex.exists():
        log(f"  ✗ Claude no escribió {rel_tex}.")
        resultado["motivo"] = "Claude no escribió el .tex"
        return resultado

    log(f"  Compilando con {compilador}…")
    ok, error = compilar(tex)
    intento = 0
    while not ok and intento < MAX_REINTENTOS_LATEX:
        intento += 1
        log(f"  ⚠ La compilación falló. Pido a Claude que corrija el .tex (reintento {intento}/{MAX_REINTENTOS_LATEX})…")
        resultado["incidencias"].append(f"reintento LaTeX {intento}: {error.splitlines()[0] if error else 'error'}")
        arreglo = (f"El archivo `{rel_tex}` no compila con {compilador}. Este es el error:\n\n"
                   f"```\n{error}\n```\n\nCorrige `{rel_tex}` con la herramienta Edit, cambiando lo "
                   "mínimo necesario para que compile. No cambies el contenido de los ejercicios. "
                   "Responde solo 'listo'.")
        try:
            claude_cli.ejecutar(cfg, arreglo, cwd=dir_curso, modelo=modelo, timeout=900,
                                **_herramientas())
        except claude_cli.ErrorClaude as e:
            resultado["incidencias"].append(f"reintento {intento} falló: {e}")
            break
        ok, error = compilar(tex)
    if not ok:
        log(f"  ✗ No se pudo compilar la guía. El .tex quedó en {tex}")
        resultado["motivo"] = "no compiló después de los reintentos"
        return resultado

    limpiar_auxiliares(tex)
    resultado["estado"] = "generada"
    log(f"  ✓ Guía lista: {pdf}")
    try:
        os.startfile(str(pdf.parent))
    except OSError:
        pass
    return resultado
