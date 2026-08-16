---
name: canvas
description: Use when the user wants material from Canvas LMS (Instructure) — course files, slides, module content, assignments, announcements, or submissions — brought into the current workspace so it can be read or worked with. Triggers on "bajá/descargá de Canvas", "traeme el material de <ramo>", "las diapos de la semana N", "el enunciado de la tarea de <ramo>", or any request to read course material that is not already on disk.
---

# Descargar material de Canvas

Baja material de Canvas LMS a una carpeta local usando el CLI del repo
`canvas downloader`, para poder leerlo en la conversación sin pasar por la GUI.

**Responder siempre en español.**

## Setup

- Repo: `C:\Claude\canvas downloader` (variable `CANVAS_REPO` si está definida).
- Ejecutar **siempre** con `cwd` en el repo: el script lee las credenciales del
  `.env` que vive ahí. El `.venv` del repo no tiene `requests`; usar el `python`
  del sistema.
- Nunca leer, imprimir ni pedir el token. Si el CLI se queja de configuración
  faltante, avisar al usuario y parar.

Comando base:

```
cd "C:\Claude\canvas downloader" && python canvas_descargar.py <flags>
```

## Flujo

### 1. Identificar el curso

```
python canvas_descargar.py --listar --json --incluir-pasados
```

Devuelve `[{id, nombre, termino, pasado}]`. Matchear contra lo que dijo el
usuario ("bases de datos" → `BASE DE DATOS`), ignorando mayúsculas y acentos.

- Un solo match claro → seguir.
- Varios candidatos → preguntar cuál, mostrando nombre y término.
- Ninguno → mostrar la lista de cursos y preguntar.

### 2. Preguntar el destino

**Siempre preguntar antes de bajar nada.** Proponer como opción por defecto una
carpeta dentro del proyecto actual (p. ej. `./material-canvas/`), que es lo que
permite leer el material en el mismo chat. Ofrecer también la biblioteca
habitual (el destino por defecto del script, si el usuario la prefiere) y dejar
que escriba una ruta propia.

Pasar la ruta elegida con `--dest "<ruta>"`. Sin `--dest` el material va a la
biblioteca por defecto del script, que **no** es la carpeta del chat.

### 3a. Curso completo

Por defecto baja archivos + módulos. Sumar fuentes según lo que pidió:

| Pidió | Flags |
|---|---|
| todo el ramo | (nada extra) |
| ...con tareas | `--tareas` |
| ...con mis entregas | `--entregas` |
| ...con anuncios / foros | `--anuncios` `--discusiones` |
| solo módulos / solo archivos | `--solo-modulos` / `--solo-archivos` |
| todo lo que haya | `--tareas --entregas --anuncios --discusiones` |

```
python canvas_descargar.py --curso 80460 --dest "<destino>" --tareas
```

### 3b. Archivos puntuales

Cuando el pedido apunta a algo específico ("las diapos de la semana 5", "el
enunciado de la tarea 2", "la guía de ejercicios"):

```
python canvas_descargar.py --contenido <id_curso>
```

Devuelve JSON con `carpetas` (id, ruta, cantidad), `archivos` (id, nombre,
carpeta, tamaño, bloqueado), `modulos` (con sus items y `file_id` cuando el item
es un archivo), `tareas` y `avisos`. Es grande: redirigirlo a un archivo del
scratchpad y filtrarlo con `grep`/`python` en vez de volcarlo entero al chat.

Después, según lo que corresponda:

```
python canvas_descargar.py --curso <id> --archivos <ids...> --dest "<destino>"
python canvas_descargar.py --curso <id> --solo-archivos --carpetas <ids...> --dest "<destino>"
python canvas_descargar.py --curso <id> --solo-modulos --modulos <ids...> --dest "<destino>"
```

`--archivos` exige exactamente un `--curso`. Si el match no es obvio, mostrar
los candidatos con su nombre y confirmar antes de bajar.

### 4. Reportar

Decir qué bajó, cuántos archivos y la ruta exacta. Si el usuario pidió el
material para trabajarlo, leer los archivos relevantes y seguir con lo que
quería hacer — ese es el punto de la skill.

## Notas

- **Cursos concluidos**: `--curso <id>` resuelve solo el id aunque el curso esté
  cerrado; no hace falta `--incluir-pasados` para descargar. Sí hace falta para
  que aparezca en `--listar`.
- La pestaña Archivos suele estar bloqueada en cursos concluidos: si `--contenido`
  trae `avisos` sobre eso, el material está bajo `modulos` — usar `--modulos` o
  los `file_id` de sus items.
- `bloqueado: true` en un archivo significa que Canvas no entrega URL de descarga.
  No es un error del script: reportarlo y seguir con el resto.
- Re-ejecutar es seguro: lo ya descargado se salta comparando tamaño.
- Las páginas, enunciados y anuncios se guardan como `.html`; el texto se puede
  leer igual.
- Para bajar a un proyecto que no es este repo, `--dest` acepta rutas absolutas
  y relativas al repo. Ante la duda, pasar la ruta **absoluta** de la carpeta del
  chat.
