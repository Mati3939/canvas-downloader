"""Sesión de escaneo de apuntes: ramo, título, carpeta temporal, páginas
capturadas y estado del detector; terminar (arma el PDF en Drive) o cancelar.
Sin HTTP: las rutas viven en canvas_gui.py.

`escaner` (y por lo tanto cv2/numpy/img2pdf) se importa perezoso dentro de
cada método: si falta alguna dependencia, el resto de la GUI sigue
funcionando y `estado()` avisa qué instalar.
"""
import base64
import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import sync_ramos


class ErrorEscaneo(Exception):
    """Error de la API de escaneo: `status` es el código HTTP a devolver."""

    def __init__(self, mensaje: str, status: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status


LADO_DETECCION = 640   # mismo tamaño que los frames que analiza el navegador


def _detectar_reducida(escaner, img):
    """Detecta la hoja sobre una copia reducida (como en el análisis en vivo) y
    escala las esquinas a la foto completa: en 1080p/4K la cuadrícula y el ruido
    fino le meten bordes de más a Canny."""
    import cv2
    alto, ancho = img.shape[:2]
    escala = LADO_DETECCION / max(alto, ancho)
    if escala >= 1:
        return escaner.detectar_hoja(img)
    chica = cv2.resize(img, (round(ancho * escala), round(alto * escala)),
                       interpolation=cv2.INTER_AREA)
    esquinas = escaner.detectar_hoja(chica)
    return None if esquinas is None else esquinas / escala


def _escaner():
    import escaner
    return escaner


@dataclass
class _Sesion:
    ramo: str
    titulo: str
    tmp_dir: Path
    detector: object
    paginas: list = field(default_factory=list)   # [{"id", "ruta", "huella", "miniatura"}]
    _contador: int = 0

    def nuevo_id(self):
        self._contador += 1
        return f"p{self._contador:03d}"


class GestorEscaneo:
    """Thread-safe: cada método público toma el lock (hay una sola sesión
    activa a la vez, pero dos pestañas pueden estar analizando juntas)."""

    def __init__(self):
        self._lock = threading.RLock()
        self._sesion = None
        self._ultimo_pdf = None
        self._ultima_carpeta = None

    # ---- disponibilidad / estado

    def _disponibilidad(self):
        """(disponible, motivo, ramos). `ramos` vacío si no disponible."""
        try:
            _escaner()
        except ImportError:
            return False, "Faltan dependencias: python -m pip install opencv-python-headless img2pdf", []
        try:
            cfg = sync_ramos.cargar_config()
            sync_ramos.resolver_drive_root(sync_ramos.leer_env())
        except sync_ramos.ErrorFatal as e:
            return False, str(e).splitlines()[0], []
        ramos = [{"nombre": c["nombre"]} for c in cfg["cursos"]]
        return True, None, ramos

    @staticmethod
    def _pagina_dict(p):
        b64 = base64.b64encode(p["miniatura"]).decode("ascii")
        return {"id": p["id"], "miniatura": f"data:image/jpeg;base64,{b64}"}

    def _sesion_dict(self, sesion):
        return {
            "ramo": sesion.ramo,
            "titulo": sesion.titulo,
            "paginas": [self._pagina_dict(p) for p in sesion.paginas],
        }

    def estado(self) -> dict:
        with self._lock:
            disponible, motivo, ramos = self._disponibilidad()
            sesion = self._sesion_dict(self._sesion) if self._sesion is not None else None
            return {
                "disponible": disponible,
                "motivo": motivo,
                "ramos": ramos,
                "sesion": sesion,
                "ultimo_pdf": self._ultimo_pdf,
            }

    # ---- sesión

    def iniciar(self, ramo: str, titulo: "str | None") -> dict:
        with self._lock:
            if self._sesion is not None:
                raise ErrorEscaneo("Ya hay una sesión de escaneo en curso.", 409)
            if not ramo:
                raise ErrorEscaneo("Falta el ramo.", 400)
            disponible, motivo, ramos = self._disponibilidad()
            if not disponible:
                raise ErrorEscaneo(motivo, 400)
            if not any(r["nombre"] == ramo for r in ramos):
                raise ErrorEscaneo(f"No encuentro el ramo '{ramo}'.", 404)
            titulo_final = (titulo or "").strip() or f"Apuntes {date.today():%Y-%m-%d}"
            tmp_dir = Path(tempfile.mkdtemp(prefix="escaneo_"))
            detector = _escaner().Detector()
            self._sesion = _Sesion(ramo=ramo, titulo=titulo_final, tmp_dir=tmp_dir, detector=detector)
            return self._sesion_dict(self._sesion)

    def _requerir_sesion(self, status_si_no_hay=409):
        if self._sesion is None:
            raise ErrorEscaneo("No hay una sesión de escaneo activa.", status_si_no_hay)
        return self._sesion

    def analizar(self, jpeg: bytes, t: "float | None" = None) -> dict:
        escaner = _escaner()
        try:
            img = escaner.decodificar_jpeg(jpeg)
        except ValueError:
            raise ErrorEscaneo("Imagen inválida", 400)
        with self._lock:
            sesion = self._requerir_sesion()
            t_final = time.monotonic() if t is None else t
            diag = sesion.detector.analizar(img, t_final)
            return diag.a_dict()

    def capturar(self, jpeg: bytes, forzar: bool) -> dict:
        escaner = _escaner()
        try:
            img = escaner.decodificar_jpeg(jpeg)
        except ValueError:
            raise ErrorEscaneo("Imagen inválida", 400)
        with self._lock:
            sesion = self._requerir_sesion()
            esquinas = _detectar_reducida(escaner, img)
            if esquinas is not None:
                enderezada = escaner.enderezar(img, esquinas)
                # Recorta un borde fino: las esquinas vienen de la imagen reducida
                # y suelen dejar una línea de mesa en los bordes.
                m = max(2, round(min(enderezada.shape[:2]) * 0.006))
                enderezada = enderezada[m:-m, m:-m]
                huella_pagina = escaner.huella(enderezada)
                procesada = escaner.realzar(enderezada)
            else:
                huella_pagina = escaner.huella(img)
                procesada = escaner.realzar(img)

            id_ = sesion.nuevo_id()
            ruta = sesion.tmp_dir / f"{id_}.jpg"
            ruta.write_bytes(escaner.codificar_jpeg(procesada, calidad=90))
            miniatura = escaner.miniatura_jpeg(procesada)
            pagina = {"id": id_, "ruta": ruta, "huella": huella_pagina, "miniatura": miniatura}
            sesion.paginas.append(pagina)

            if forzar:
                sesion.detector.registrar_captura(huella_pagina)
            return self._pagina_dict(pagina)

    def pagina_jpeg(self, id_: str) -> bytes:
        with self._lock:
            sesion = self._requerir_sesion(status_si_no_hay=404)
            for p in sesion.paginas:
                if p["id"] == id_:
                    return p["ruta"].read_bytes()
            raise ErrorEscaneo("Página no encontrada", 404)

    def borrar(self, id_: str) -> dict:
        with self._lock:
            sesion = self._requerir_sesion(status_si_no_hay=404)
            idx = next((i for i, p in enumerate(sesion.paginas) if p["id"] == id_), None)
            if idx is None:
                raise ErrorEscaneo("Página no encontrada", 404)
            pagina = sesion.paginas.pop(idx)
            try:
                pagina["ruta"].unlink(missing_ok=True)
            except OSError:
                pass
            ultima_huella = sesion.paginas[-1]["huella"] if sesion.paginas else None
            sesion.detector.fijar_ultima_huella(ultima_huella)
            return {"paginas": [self._pagina_dict(p) for p in sesion.paginas]}

    def terminar(self, titulo: "str | None" = None) -> dict:
        escaner = _escaner()
        with self._lock:
            sesion = self._requerir_sesion()
            if not sesion.paginas:
                raise ErrorEscaneo("No hay páginas capturadas.", 400)
            titulo_final = (titulo or "").strip() or sesion.titulo
            try:
                cfg = sync_ramos.cargar_config()
                raiz = sync_ramos.resolver_drive_root(sync_ramos.leer_env())
                sync_ramos.verificar_drive_root(raiz, escribir=True)
                curso = next((c for c in cfg["cursos"] if c["nombre"] == sesion.ramo), None)
                if curso is None:
                    raise ErrorEscaneo(f"No encuentro el ramo '{sesion.ramo}'.", 500)
                destino_dir = sync_ramos.carpeta_curso(raiz, cfg, curso) / "Apuntes"
                destino_dir.mkdir(parents=True, exist_ok=True)
                nombre = sync_ramos.limpiar(titulo_final)
                destino = destino_dir / f"{nombre}.pdf"
                sufijo = 2
                while destino.exists():
                    destino = destino_dir / f"{nombre} ({sufijo}).pdf"
                    sufijo += 1
                rutas = [p["ruta"] for p in sesion.paginas]
                escaner.armar_pdf(rutas, destino)
            except sync_ramos.ErrorFatal as e:
                raise ErrorEscaneo(str(e).splitlines()[0], 500)
            except OSError as e:
                raise ErrorEscaneo(str(e), 500)

            shutil.rmtree(sesion.tmp_dir, ignore_errors=True)
            self._sesion = None
            self._ultimo_pdf = str(destino)
            self._ultima_carpeta = str(destino_dir)
            return {"pdf": str(destino), "carpeta": str(destino_dir)}

    def cancelar(self) -> None:
        with self._lock:
            if self._sesion is not None:
                shutil.rmtree(self._sesion.tmp_dir, ignore_errors=True)
            self._sesion = None

    def abrir_carpeta(self) -> None:
        with self._lock:
            carpeta = self._ultima_carpeta
        if not carpeta:
            raise ErrorEscaneo("Todavía no se generó ningún PDF.", 404)
        os.startfile(carpeta)
