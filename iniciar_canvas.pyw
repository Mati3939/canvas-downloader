"""
Lanzador del Descargador de Canvas para el acceso directo de Windows.

La extensión .pyw hace que Windows lo ejecute con pythonw.exe, o sea sin
ventana de consola: al abrirlo solo se levanta el servidor local y se abre el
navegador. Toda la lógica sigue viviendo en canvas_gui.py; acá solo agregamos
lo que hace falta para que funcione bien como acceso directo:

  - si ya hay una instancia abierta, no levanta un segundo servidor;
  - si algo falla, lo muestra en un cuadro de diálogo (sin consola, un error
    sin avisar sería un doble clic que "no hace nada").

Para instalarlo en el Menú Inicio: instalar_acceso_directo.ps1
"""
import os
import sys
import socket
import traceback
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _preparar_salida():
    """pythonw deja sys.stdout y sys.stderr en None.

    El servidor HTTP loguea cada request en sys.stderr, así que sin esto la
    primera visita muere con AttributeError y el navegador recibe una
    respuesta vacía. Mandamos la salida al vacío: el progreso igual se ve en
    la página, y los errores de arranque salen por diálogo.
    """
    for nombre in ("stdout", "stderr"):
        if getattr(sys, nombre, None) is None:
            try:
                setattr(sys, nombre, open(os.devnull, "w", encoding="utf-8"))
            except OSError:
                pass


def _aviso(mensaje):
    """Muestra el error en un diálogo; si no hay tkinter, lo deja en un log."""
    try:
        import tkinter
        from tkinter import messagebox
        raiz = tkinter.Tk()
        raiz.withdraw()
        messagebox.showerror("Descargador de Canvas", mensaje)
        raiz.destroy()
    except Exception:
        try:
            (HERE / "error_inicio.log").write_text(mensaje, encoding="utf-8")
        except Exception:
            pass


def _ya_esta_corriendo(puerto):
    """True si algo ya escucha en 127.0.0.1:puerto (otra instancia abierta)."""
    try:
        with socket.socket() as s:
            s.settimeout(0.3)
            return s.connect_ex(("127.0.0.1", puerto)) == 0
    except OSError:
        return False


def main():
    _preparar_salida()
    try:
        import canvas_gui
    except SystemExit as e:
        # canvas_descargar.py hace sys.exit si falta 'requests'.
        _aviso(str(e) or "No se pudo iniciar el programa.")
        return 1
    except Exception:
        _aviso("No se pudo cargar el programa:\n\n" + traceback.format_exc())
        return 1

    puerto = canvas_gui.PUERTO_PREFERIDO
    if _ya_esta_corriendo(puerto):
        webbrowser.open(f"http://127.0.0.1:{puerto}/")
        return 0

    try:
        canvas_gui.main()
    except SystemExit as e:
        if e.code:
            _aviso(str(e.code))
            return 1
    except Exception:
        _aviso("El servidor se cerró por un error:\n\n" + traceback.format_exc())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
