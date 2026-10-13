# Canvas Downloader

Descargador de material de cursos de **Canvas LMS** (Instructure), con interfaz web local y línea de comandos. Pensado para armar un respaldo/banco de conocimiento en tu disco: baja archivos, módulos, tareas, anuncios y foros, preservando la estructura de carpetas y sin volver a bajar lo que ya existe.

![Python](https://img.shields.io/badge/python-3.8%2B-blue) ![deps](https://img.shields.io/badge/dependencias-requests-green)

## Qué descarga

| Fuente | Contenido |
|---|---|
| **Archivos** | La pestaña Archivos completa, con su árbol de carpetas (filtrable por carpeta) |
| **Módulos** | Archivos de cada módulo y archivos embebidos en sus páginas (filtrable por módulo) |
| **Tareas** | Adjuntos del enunciado + snapshot `enunciado.html` |
| **Mis entregas** | Los archivos que vos entregaste en cada tarea (con historial de intentos) |
| **Anuncios** | Mensajes del profesor con sus adjuntos + snapshot HTML |
| **Discusiones** | Foros del curso con sus adjuntos + snapshot HTML |

Funciona también con **cursos pasados/concluidos** (inscripciones anteriores), incluso cuando la pestaña Archivos está bloqueada y el material solo es accesible vía Módulos. El contenido escrito (páginas, enunciados, anuncios) se conserva como archivos `.html`.

## Configuración

1. Generá un token en Canvas: **Cuenta → Configuración → Tokens de acceso aprobados → "+ Nuevo token de acceso"**.
2. Creá un archivo `.env` junto a los scripts (no se commitea):

```
CANVAS_URL=https://tu-institucion.instructure.com
CANVAS_TOKEN=tu_token
```

También se aceptan variables de entorno o un `canvas_config.json` (`{"base_url": "...", "token": "..."}`). Prioridad: variables de entorno > json > `.env`.

3. Instalá la única dependencia:

```
pip install requests
```

## Interfaz web

```
python canvas_gui.py
```

Abre el navegador en `http://127.0.0.1:8765/` con:

- **Tarjetas por curso** estilo Canvas, separadas en *Activos*, *Pasados* y *Ocultados*.
- Expandí una tarjeta ("Contenido") para elegir **carpetas y módulos específicos** con checkboxes en cascada.
- Elegí las **fuentes** a descargar (archivos, módulos, tareas, entregas, anuncios, discusiones).
- **Ocultar cursos** y **reordenar arrastrando** las tarjetas; la configuración se guarda por usuario de Canvas en `canvas_gui_prefs.json`.
- Carpeta destino configurable y opción de **organizar por término académico** (`destino/término/curso/…`).
- Log de progreso en vivo con resumen final (nuevos / ya existían / errores).
- Tema claro y oscuro.
- El botón **Sincronizar ramos** baja solo lo nuevo de tus ramos hacia una carpeta de Google Drive (ver abajo).

## Sincronizar ramos

El botón **Sincronizar ramos** de la GUI (`sync_ramos.py`) mantiene una copia
incremental de cada ramo del semestre en una carpeta sincronizada con Google Drive:
módulos, archivos, tareas, anuncios y mensajes de profes, más un `syllabus.md`
por ramo. Solo baja lo nuevo o modificado (lleva un manifest en `sync_estado/`).

Para activarlo:

1. Instala PyYAML: `pip install pyyaml`.
2. Agrega `DRIVE_ROOT` al `.env` con la ruta de tu carpeta de Drive para escritorio.
3. Copia `ramos.example.yaml` como `ramos.yaml` y completa el semestre y tus ramos
   (id del curso en Canvas y nombre de la carpeta).

Los archivos quedan en `DRIVE_ROOT/<semestre>/<carpeta del ramo>/canvas/`.

## Escanear apuntes

El botón **Escanear apuntes** de la GUI abre `/escanear` en otra pestaña: usa una
cámara (o el celular como webcam) para detectar sola una hoja de cuaderno,
esperar que esté encuadrada, quieta y enfocada, y capturarla sin tocar nada.
Al terminar la sesión arma un PDF y lo deja en
`DRIVE_ROOT/<semestre>/<carpeta del ramo>/Apuntes/`.

Para activarlo, instala las dependencias de visión:

```
pip install opencv-python-headless img2pdf
```

Necesita además `ramos.yaml` y `DRIVE_ROOT` configurados (ver "Sincronizar
ramos" arriba) y una cámara disponible para el navegador.

## Acceso directo en Windows

Para abrirlo con un clic, sin consola ni editor:

```
powershell -ExecutionPolicy Bypass -File .\instalar_acceso_directo.ps1
```

Se corre **una sola vez**: crea *Canvas Downloader* en el Menú Inicio (con icono),
apuntando a `iniciar_canvas.pyw`. Desde ahí lo buscás escribiendo "Canvas" y, con
clic derecho, lo anclás a Inicio o a la barra de tareas.

`iniciar_canvas.pyw` es el mismo `canvas_gui.py` pero pensado para el doble clic:
corre bajo `pythonw` (sin ventana de consola), no levanta un segundo servidor si
ya hay una instancia abierta —solo trae al navegador a la que está corriendo— y
si algo falla lo avisa en un cuadro de diálogo en vez de cerrarse en silencio.

Para cerrarlo, terminá el proceso `pythonw` desde el Administrador de tareas.

Volvé a correr el instalador si movés la carpeta del proyecto o reinstalás Python
(el acceso directo guarda las rutas). Necesita Python instalado en la máquina: no
es un `.exe` autocontenido.

## Línea de comandos

```
python canvas_descargar.py --listar                    # lista tus cursos
python canvas_descargar.py --listar --incluir-pasados  # incluye cursos concluidos
python canvas_descargar.py --curso 12345               # descarga un curso (archivos + módulos)
python canvas_descargar.py --todos --filtro fisica     # todos los cursos que contengan "fisica"
python canvas_descargar.py --curso 12345 --tareas --entregas --anuncios --discusiones
python canvas_descargar.py --todos --por-termino       # organiza destino/término/curso
python canvas_descargar.py --curso 12345 --solo-modulos
python canvas_descargar.py --curso 12345 --dest "D:\Universidad\Canvas"
```

Destino por defecto: `../Archivos oficiales/Canvas (descarga)/` relativo a la carpeta del script.

### Salida JSON y descarga selectiva

Pensados para automatizar (los usa la skill de Claude Code):

```
python canvas_descargar.py --listar --json --incluir-pasados   # cursos como JSON
python canvas_descargar.py --contenido 12345                   # índice del curso como JSON
python canvas_descargar.py --curso 12345 --archivos 987 654    # solo esos archivos, por id
python canvas_descargar.py --curso 12345 --solo-archivos --carpetas 111 222
python canvas_descargar.py --curso 12345 --solo-modulos --modulos 333
```

`--contenido` no descarga nada: devuelve carpetas, archivos (con id, tamaño y si están bloqueados), módulos con sus ítems, tareas y avisos. Sirve para elegir qué bajar. `--curso <id>` resuelve el id directo, así que también funciona con cursos concluidos sin pasar `--incluir-pasados`.

## Skill de Claude Code

`.claude/skills/canvas/` es una skill que le permite a Claude bajar material desde el chat: identifica el ramo por nombre, pregunta el destino, y descarga el curso completo o archivos puntuales. Para usarla desde cualquier proyecto, enlazala a tu carpeta de skills:

```
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\canvas" `
         -Target "C:\Claude\canvas downloader\.claude\skills\canvas"
```

Después basta con pedir en el chat "bajame el material de Base de Datos" o "traeme las diapos de la semana 5 de Cálculo".

## Estructura de salida

```
Canvas (descarga)/
└── FÍSICA/
    ├── <carpetas de la pestaña Archivos>/
    ├── Módulos/<módulo>/archivos y páginas .html
    ├── Tareas/<tarea>/enunciado.html + adjuntos
    │   └── Mi entrega/
    ├── Anuncios/<anuncio>/
    └── Discusiones/<foro>/
```

## Notas

- Lo ya descargado se salta (comparando tamaño), así que se puede re-ejecutar para sincronizar.
- Algunos archivos de cursos concluidos aparecen como `✗ archivo bloqueado o restringido`: Canvas ya no entrega URL de descarga para ellos; no es un error del script.
- El token da acceso a tu cuenta: no lo compartas ni lo subas al repo (el `.gitignore` ya excluye `.env` y `canvas_config.json`).
