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
