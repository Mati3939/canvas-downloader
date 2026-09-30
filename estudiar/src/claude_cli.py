"""Ejecución de Claude Code en modo headless (`claude -p`).

Por defecto corre con --safe-mode y un system prompt propio: sin plugins,
skills, MCP ni memoria el contexto base baja de ~130k a ~1k tokens. El
contexto que importa (CLAUDE.md del ramo, temario, etc.) se pasa en el prompt.
"""
import json
import shutil
import subprocess

from utils import ErrorFatal

SYSTEM_PROMPT = ("Eres un asistente de estudio para un estudiante de ingeniería. "
                 "Respondes en español, de forma precisa y sin relleno.")


class ErrorClaude(Exception):
    pass


def ejecutable(cfg):
    comando = (cfg.get("claude") or {}).get("comando", "claude")
    ruta = shutil.which(comando)
    if not ruta:
        raise ErrorFatal(f"No encuentro el comando '{comando}' de Claude Code en el PATH.")
    return ruta


def resumen_consumo(datos):
    u = datos.get("usage") or {}
    entrada = sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                        "cache_read_input_tokens"))
    return f"{entrada:,} tokens de entrada, {u.get('output_tokens', 0):,} de salida"


def ejecutar(cfg, prompt, cwd, *, schema=None, tools="", allowed_tools=None,
             permission_mode=None, add_dirs=None, modelo=None, system_prompt=SYSTEM_PROMPT,
             timeout=None):
    """Corre `claude -p` con el prompt por stdin. Devuelve el JSON de resultado
    (con `structured_output` si se pasó `schema`)."""
    ajustes = cfg.get("claude") or {}
    args = [ejecutable(cfg), "-p", "--output-format", "json", "--no-session-persistence",
            "--safe-mode", "--system-prompt", system_prompt, "--tools", tools]
    if modelo:
        args += ["--model", modelo]
    if schema is not None:
        args += ["--json-schema", json.dumps(schema, ensure_ascii=False)]
    if allowed_tools:
        args += ["--allowedTools", ",".join(allowed_tools)]
    if permission_mode:
        args += ["--permission-mode", permission_mode]
    for d in add_dirs or []:
        args += ["--add-dir", str(d)]
    try:
        proc = subprocess.run(args, input=prompt, cwd=str(cwd), capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=timeout or int(ajustes.get("timeout_segundos", 1800)))
    except subprocess.TimeoutExpired:
        raise ErrorClaude("Claude no respondió dentro del tiempo límite.")
    try:
        datos = json.loads(proc.stdout)
    except json.JSONDecodeError:
        detalle = (proc.stderr or proc.stdout or "").strip()[-500:]
        raise ErrorClaude(f"Claude terminó con código {proc.returncode}: {detalle}")
    if datos.get("is_error"):
        raise ErrorClaude(f"Claude devolvió un error: {str(datos.get('result'))[:500]}")
    if schema is not None and not isinstance(datos.get("structured_output"), dict):
        raise ErrorClaude("Claude no devolvió la respuesta estructurada esperada.")
    return datos
