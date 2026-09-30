Vas a escribir una **guía de estudio en LaTeX** para una evaluación universitaria. Trabajas dentro de la carpeta del ramo: `canvas/` tiene el material oficial descargado de Canvas y debes escribir el resultado en `{{archivo_tex}}`.

## Evaluación
- Ramo: {{curso}}
- Evaluación: {{evaluacion}}
- Fecha: {{fecha}}

## Temario confirmado por el estudiante (tentativo)
{{temario}}

## Formalidades del curso (CLAUDE.md)
Respétalas aunque difieran de los libros: notación, forma de justificar, criterios del profesor.

{{claude_md}}

## Material que debes usar
Lee **solo** estos archivos (rutas relativas a la carpeta del ramo). No explores otras carpetas: el consumo está acotado a propósito.

{{archivos}}

{{textos_extraidos}}

## Guías anteriores del ramo
{{registro}}

## Referencia de estilo
Así se ve una guía anterior del estudiante (texto extraído de un PDF, sin formato). Imita su tono, estructura y nivel de detalle, no su contenido:

{{referencia_estilo}}

## Formato obligatorio (en este orden exacto)
1. **Encabezado**: ramo, evaluación, fecha y el temario cubierto, marcado explícitamente como *tentativo*. Incluye una nota breve: "Documento generado por Claude como material de práctica adicional. No es material oficial de la asignatura."
2. **Ejercicios**:
   - Numerados (`Ej. 1`, `Ej. 2`, …) y **sin pistas**.
   - Ordenados por **dificultad creciente** (subsecciones Nivel fácil / Nivel medio / Nivel desafiante), no por tema.
   - Prefiere ejercicios tomados o adaptados del material de `canvas/`, citando la fuente como `[n]`.
   - Los ejercicios inventados llevan la marca **(generado)**.
   - Si un ejercicio depende de algo que no está en el material, dilo en vez de inventar.
   - Entre 12 y 20 ejercicios, proporcionales a la extensión de la evaluación.
3. **Formulario resumen**: compacto, **sin cajas** (nada de `tcolorbox`, `fbox`, `mdframed`) y sin explicaciones largas. Solo lo necesario para resolver los ejercicios.
4. **Solucionario**: resolución paso a paso de cada ejercicio, en el mismo orden, respetando las formalidades de CLAUDE.md. Destaca el resultado final y, cuando ayude, una línea "Ojo:" con el error típico.
5. **Fuentes**: lista numerada `[n]` con la ruta del archivo de `canvas/` de cada cita.

## Reglas de LaTeX
- Documento completo y compilable con **pdflatex** (MiKTeX). Usa este preámbulo como base y no agregues paquetes exóticos:

```latex
\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish,es-noshorthands]{babel}
\usepackage{lmodern}
\usepackage[a4paper,margin=2.2cm]{geometry}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{enumitem}
\usepackage{fancyhdr}
\usepackage[hidelinks]{hyperref}
\pagestyle{fancy}\fancyhf{}
\rhead{\thepage}\lhead{ {{curso}} · {{evaluacion}} }
\setlength{\parindent}{0pt}\setlength{\parskip}{4pt}
```
- Español, con notación matemática en LaTeX correcto (`\,dx`, `\left(\right)`, `\mathbb{R}`, etc.).
- Escapa bien los caracteres especiales (`%`, `&`, `_`, `#`) en el texto.
- Escribe el archivo con la herramienta Write en `{{archivo_tex}}`. No escribas en ningún otro lugar.

Al terminar, responde solo con una línea: la cantidad de ejercicios y cuántos son (generado).
