"""Punto de entrada de estudiar: sync de Canvas -> calendario -> temario -> guía."""
import argparse
import sys
from pathlib import Path

from utils import (ErrorFatal, Log, asegurar_claude_md, buscar_curso, cargar_config,
                   carpeta_curso, leer_env, resolver_drive_root, verificar_drive_root)


def parsear_args(argv=None):
    ap = argparse.ArgumentParser(prog="estudiar",
                                 description="Canvas -> Drive -> calendario -> guía de estudio")
    ap.add_argument("--curso", help="fuerza un ramo (busca por nombre, sin importar tildes)")
    ap.add_argument("--sin-descarga", action="store_true", help="salta la sincronización con Canvas")
    ap.add_argument("--solo-sync", action="store_true", help="solo descarga archivos nuevos")
    ap.add_argument("--dry-run", action="store_true", help="muestra qué haría, sin descargar ni generar")
    ap.add_argument("--drive-root", help="usa otra carpeta raíz en vez de DRIVE_ROOT (pruebas)")
    ap.add_argument("--manifest", help="usa otro manifest en vez de state/manifest.json (pruebas)")
    return ap.parse_args(argv)


def elegir_cursos(cfg, texto):
    if not texto:
        return cfg["cursos"]
    encontrados = buscar_curso(cfg, texto)
    if not encontrados:
        nombres = ", ".join(c["nombre"] for c in cfg["cursos"])
        raise ErrorFatal(f"No hay ningún ramo que coincida con '{texto}'. Ramos: {nombres}")
    if len(encontrados) > 1:
        nombres = ", ".join(c["nombre"] for c in encontrados)
        raise ErrorFatal(f"'{texto}' coincide con varios ramos: {nombres}. Sé más específico.")
    return encontrados


def revisar_claude_md(cfg, cursos, raiz, log, crear):
    vacios = []
    for c in cursos:
        estado = asegurar_claude_md(carpeta_curso(raiz, cfg, c), c["nombre"], crear=crear)
        if estado == "creado":
            log(f"  + CLAUDE.md creado para {c['nombre']}")
        if estado in ("creado", "vacio", "falta") and c["rol"] == "estudiante":
            vacios.append(c["nombre"])
    if vacios:
        log("\n⚠ Estos ramos tienen el CLAUDE.md vacío. Completar sus formalidades "
            "(notación, criterios del profe, estilo de evaluación) es lo que más mejora la guía:")
        for n in vacios:
            log(f"    - {n}")


def elegir_evaluaciones(cfg, cursos, log, forzado=False):
    """Lee el calendario y devuelve las próximas evaluaciones de `cursos`, de la
    más cercana a la más lejana. Si el calendario falla, avisa y devuelve []."""
    from calendar_reader import imprimir_proximas, proximas_evaluaciones
    try:
        proximas, sin_asociar = proximas_evaluaciones(cfg, log)
    except ErrorFatal as e:
        log(f"\n✗ Calendario: {e}")
        return []
    imprimir_proximas(cfg, proximas, sin_asociar, log)
    ids = {c["canvas_course_id"] for c in cursos}
    candidatas = sorted((e for cid, e in proximas.items() if cid in ids), key=lambda e: e.inicio)
    if not candidatas:
        if forzado:
            c = cursos[0]
            motivo = ("eres ayudante en ese ramo" if c["rol"] != "estudiante"
                      else f"no tiene evaluaciones en los próximos {cfg.get('dias_horizonte', 30)} días")
            log(f"\n{c['nombre']}: {motivo}. No hay nada que preparar.")
        else:
            log("\nNo hay evaluaciones próximas. No hay nada que preparar.")
    return candidatas


def escribir_registros(cfg, cursos, raiz, resultados, trabajados, log):
    """Una entrada en registro.md por cada ramo que esta ejecución tocó: el de la
    evaluación (o los saltados) y los que recibieron archivos nuevos."""
    import registro
    for c in cursos:
        sync = (resultados or {}).get(c["nombre"])
        datos = trabajados.get(c["nombre"])
        hubo_cambios = sync and (sync["nuevos"] or sync["actualizados"] or sync["errores"])
        if not datos and not hubo_cambios:
            continue
        datos = datos or {}
        dir_curso = carpeta_curso(raiz, cfg, c)
        entrada = registro.armar_entrada(dir_curso, ev=datos.get("ev"), sync=sync,
                                         temario=datos.get("temario"), guia=datos.get("guia"))
        try:
            registro.agregar(dir_curso, c["nombre"], entrada)
            log(f"  + registro.md actualizado: {c['nombre']}")
        except OSError as e:
            log(f"  ⚠ No pude escribir registro.md de {c['nombre']}: {e}")


def main(argv=None):
    args = parsear_args(argv)
    log = Log()
    try:
        cfg = cargar_config()
        env = leer_env()
        raiz = resolver_drive_root(env, args.drive_root)
        verificar_drive_root(raiz, escribir=not args.dry_run)
        cursos = elegir_cursos(cfg, args.curso)
        log(f"Carpeta de ramos: {Path(raiz) / cfg['semestre']}")
        if args.dry_run:
            log("Modo dry-run: no se descarga ni se escribe nada.")

        resultados = None
        if not args.sin_descarga:
            from canvas_sync import MANIFEST_FILE, imprimir_resumen, sincronizar
            resultados = sincronizar(cfg, cursos, raiz, log, dry_run=args.dry_run,
                                     manifest_path=args.manifest or MANIFEST_FILE)
            imprimir_resumen(resultados, log, dry_run=args.dry_run)

        revisar_claude_md(cfg, cursos, raiz, log, crear=not args.dry_run)

        trabajados = {}  # nombre del curso -> datos para su entrada de registro.md
        if not args.solo_sync:
            candidatas = elegir_evaluaciones(cfg, cursos, log, forzado=bool(args.curso))
            from syllabus import preparar_temario
            for ev in candidatas:
                log(f"\n→ {ev.curso['nombre']} — {ev.nombre_corto} ({ev.cuando()})")
                temario = preparar_temario(cfg, ev.curso, ev, raiz, log, dry_run=args.dry_run)
                datos = trabajados.setdefault(ev.curso["nombre"], {"curso": ev.curso})
                datos.update(ev=ev, temario=temario)
                if temario["estado"] == "saltado":
                    continue
                if temario["estado"] in ("confirmado", "editado", "dry_run"):
                    from generate import generar_guia
                    datos["guia"] = generar_guia(cfg, ev.curso, ev, raiz, log,
                                                 temario_path=temario["ruta"], dry_run=args.dry_run)
                break
            else:
                if candidatas:
                    log("\nNo quedan más ramos con evaluaciones próximas.")

        if not args.dry_run:
            escribir_registros(cfg, cursos, raiz, resultados, trabajados, log)
        return 0
    except ErrorFatal as e:
        log(f"\n✗ {e}")
        return 1
    except KeyboardInterrupt:
        log("\nInterrumpido por el usuario.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
