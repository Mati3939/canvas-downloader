# estudiar

Flujo de un clic que usa el descargador de Canvas como base:

1. Sincroniza de Canvas **solo los archivos nuevos o modificados** de tus ramos.
2. Los deja en una carpeta local sincronizada con Google Drive para escritorio.
3. Lee tu Google Calendar (dirección iCal) y detecta la **próxima evaluación** de cada ramo.
4. Arma un **temario tentativo** y te lo muestra para que lo confirmes o edites.
5. Con el temario confirmado, genera una **guía de estudio en PDF** con Claude Code
   en modo headless (`claude -p`) y LaTeX.

## Requisitos

- Windows, Python 3.10 o superior.
- [Claude Code](https://claude.com/claude-code) instalado y con sesión iniciada (`claude` en el PATH).
- Un compilador LaTeX: MiKTeX (`pdflatex`) o [tectonic](https://tectonic-typesetting.github.io/).
- Google Drive para escritorio con la carpeta de los ramos **disponible sin conexión**
  (clic derecho → "Disponible sin conexión", o Drive en modo "Mirror files").

## Instalación

```
cd estudiar
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy config.example.yaml config.yaml
```

En el `.env` de la raíz del repo (el mismo que usa el descargador) agrega:

```
CALENDAR_ICS_URL=https://calendar.google.com/calendar/ical/.../basic.ics
DRIVE_ROOT=<carpeta sincronizada con Drive donde vivirán los ramos>
```

`CALENDAR_ICS_URL` es la "Dirección secreta en formato iCal" de tu calendario
(Google Calendar → Configuración → tu calendario → Integrar el calendario). Trátala
como una contraseña. Se pueden poner varias separadas por coma.

Completa `config.yaml` con tus ramos: id de Canvas (`python canvas_descargar.py --listar`
en la raíz), carpeta y palabras con que aparecen en tu calendario.

## Uso

Doble clic en `estudiar.bat`, o desde una terminal:

```
estudiar.bat                    # flujo completo con el ramo de evaluación más cercana
estudiar.bat --curso "Álgebra"  # fuerza un ramo
estudiar.bat --sin-descarga     # salta la sincronización con Canvas
estudiar.bat --solo-sync        # solo descarga archivos nuevos
estudiar.bat --dry-run          # muestra qué haría, sin descargar ni generar
```

Cuando aparece el temario: `Enter` confirma, `e` lo abre en el Bloc de notas, `s` salta
al ramo siguiente y `r` lo vuelve a generar. La sección "Material de Canvas para
estudiar" del temario es la lista de archivos que se usa para la guía: puedes agregar
o quitar líneas antes de confirmar.

## Qué queda en cada ramo

```
<DRIVE_ROOT>/<semestre>/<Ramo>/
├── CLAUDE.md      # formalidades del ramo: complétalo, es lo que más mejora la guía
├── registro.md    # historial de ejecuciones (lo escribe el programa)
├── syllabus.md    # índice de módulos, archivos y tareas de Canvas
├── canvas/        # material descargado, ordenado por módulo
├── temario/       # temarios tentativos
└── guias/         # guías en PDF (y su .tex)
```

## Consumo

- El temario usa un modelo liviano y unos pocos miles de tokens.
- La guía es lo que más consume, porque Claude lee los PDFs del material. Se controla
  con `max_archivos_por_generacion` y `claude.modelo_guia` en `config.yaml`.
- Se genera como máximo una guía por ejecución.

## Usarlo desde otro dispositivo

Cada equipo necesita la carpeta de los ramos espejada sin conexión con Drive para
escritorio. Si usas un proyecto de Claude Cowork apuntando a la carpeta de un ramo,
verifica en cada dispositivo que el proyecto exista y apunte a la copia local: no
asumas que se sincroniza solo.
