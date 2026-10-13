"""Visión pura del escáner de apuntes: detectar la hoja en un frame, decidir
cuándo capturar (encuadre + quietud + enfoque, sin duplicados al pasar de
página) y procesarla como un escáner (fondo blanco parejo, cuadrícula
atenuada, tinta y colores conservados). Sin HTTP ni sesión: eso vive en
escaneo_sesion.py.
"""
import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import img2pdf
import numpy as np

# ---------------------------------------------------------------- constantes

AREA_MIN_DETECCION = 0.25   # fracción del frame para aceptar un contorno como hoja
AREA_MIN = 0.40
AREA_MAX = 0.90
MARGEN = 0.02               # fracción de ancho/alto
RAZON_LADOS_MIN = 0.80
QUIETO_TOL = 0.015          # fracción de la diagonal del frame
QUIETO_SEG = 0.6
# NITIDEZ_MIN: varianza del Laplaciano de la hoja sintética (LADO_ANALISIS=800)
# nítida da ~270; con GaussianBlur(k=21), simulando desenfoque, da ~14. Piso en
# 80: ~3x por debajo de lo nítido y ~5x por encima del desenfoque, con margen
# para ruido de cámara real.
NITIDEZ_MIN = 80.0
NITIDEZ_REL = 0.85
CONFIRMAR_SEG = 0.8
MOVIMIENTO_GRANDE = 0.10    # fracción de la diagonal
# HUELLA_DIF_MIN: la huella normaliza casi toda la variación de encuadre (la
# misma página, aun re-encuadrada con un corrimiento de varios px, da
# distancia ~0.0 sobre datos sintéticos) y promedia bastante el detalle fino
# (una sola palabra distinta en un renglón apenas mueve la aguja, ~0.004).
# Una página con contenido bien distinto (varios renglones más de texto) da
# >=0.28. Umbral en 0.15: muy por encima del ruido de re-encuadre y muy por
# debajo de un cambio de contenido real, con margen hacia ambos lados.
HUELLA_DIF_MIN = 0.15
LADO_ANALISIS = 800         # lado mayor de la hoja enderezada para nitidez/huella

FRASES_LADO = {
    "izquierda": "hacia la izquierda",
    "derecha": "hacia la derecha",
    "arriba": "hacia arriba",
    "abajo": "hacia abajo",
}


# ---------------------------------------------------------------- jpeg

def decodificar_jpeg(datos: bytes) -> np.ndarray:
    """BGR; ValueError si el cuerpo está vacío o corrupto."""
    if not datos:
        raise ValueError("Imagen vacía")
    arreglo = np.frombuffer(datos, dtype=np.uint8)
    img = cv2.imdecode(arreglo, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("JPEG inválido o corrupto")
    return img


def codificar_jpeg(img, calidad: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    if not ok:
        raise ValueError("No se pudo codificar la imagen")
    return buf.tobytes()


def miniatura_jpeg(img, ancho: int = 240) -> bytes:
    alto_img, ancho_img = img.shape[:2]
    alto_nuevo = max(1, round(ancho * alto_img / ancho_img))
    chica = cv2.resize(img, (ancho, alto_nuevo), interpolation=cv2.INTER_AREA)
    return codificar_jpeg(chica, calidad=80)


# ---------------------------------------------------------------- geometría

def ordenar_esquinas(pts) -> np.ndarray:
    """(4,2) float32: sup-izq, sup-der, inf-der, inf-izq."""
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    suma = pts.sum(axis=1)
    diferencia = pts[:, 0] - pts[:, 1]
    orden = np.zeros((4, 2), dtype=np.float32)
    orden[0] = pts[np.argmin(suma)]
    orden[2] = pts[np.argmax(suma)]
    orden[1] = pts[np.argmax(diferencia)]
    orden[3] = pts[np.argmin(diferencia)]
    return orden


def _area_poligono(pts) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def detectar_hoja(img) -> "np.ndarray | None":
    """Esquinas en píxeles de `img`, ordenadas, o None si no hay hoja."""
    alto, ancho = img.shape[:2]
    area_frame = ancho * alto
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gris, (5, 5), 0)
    bordes = cv2.dilate(cv2.Canny(blur, 50, 150), np.ones((3, 3), np.uint8))
    mapas = [bordes]
    if blur.std() > 1.0:
        # Otsu no tiene sentido sobre una imagen ~uniforme (sin hoja): da un
        # umbral arbitrario que puede marcar como "hoja" el frame entero.
        _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        mapas.append(otsu)

    mejor, area_mejor = None, 0.0
    for mapa in mapas:
        contornos, _ = cv2.findContours(mapa, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contornos:
            area = cv2.contourArea(c)
            if area <= area_mejor or area < AREA_MIN_DETECCION * area_frame:
                continue
            perimetro = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * perimetro, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                mejor, area_mejor = approx.reshape(4, 2).astype(np.float32), area
    if mejor is None:
        return None
    return ordenar_esquinas(mejor)


def enderezar(img, esquinas, lado_mayor: "int | None" = None) -> np.ndarray:
    """Transformación de perspectiva; el tamaño de salida respeta la
    proporción medida de la hoja (reescalada a `lado_mayor` si se da)."""
    esquinas = np.asarray(esquinas, dtype=np.float32)
    sup_izq, sup_der, inf_der, inf_izq = esquinas
    ancho_sup = np.linalg.norm(sup_der - sup_izq)
    ancho_inf = np.linalg.norm(inf_der - inf_izq)
    alto_izq = np.linalg.norm(inf_izq - sup_izq)
    alto_der = np.linalg.norm(inf_der - sup_der)
    ancho = max(ancho_sup, ancho_inf, 1.0)
    alto = max(alto_izq, alto_der, 1.0)
    if lado_mayor:
        escala = lado_mayor / max(ancho, alto)
        ancho, alto = ancho * escala, alto * escala
    ancho_px, alto_px = max(int(round(ancho)), 1), max(int(round(alto)), 1)
    destino = np.array([[0, 0], [ancho_px - 1, 0], [ancho_px - 1, alto_px - 1], [0, alto_px - 1]],
                       dtype=np.float32)
    matriz = cv2.getPerspectiveTransform(esquinas, destino)
    return cv2.warpPerspective(img, matriz, (ancho_px, alto_px))


# ---------------------------------------------------------------- enfoque / huella

def nitidez(img) -> float:
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gris, cv2.CV_64F).var())


def huella(img_enderezada) -> np.ndarray:
    """32x32 float32, gris normalizado (media 0, desv 1)."""
    gris = cv2.cvtColor(img_enderezada, cv2.COLOR_BGR2GRAY) if img_enderezada.ndim == 3 else img_enderezada
    chica = cv2.resize(gris, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    media, desvio = float(chica.mean()), float(chica.std())
    if desvio < 1e-6:
        return chica - media
    return (chica - media) / desvio


def distancia_huellas(a, b) -> float:
    return float(np.mean(np.abs(a - b)))


# ---------------------------------------------------------------- procesado tipo escáner

def realzar(img) -> np.ndarray:
    """Iluminación pareja (fondo por canal con cierre morfológico + blur
    grande), cuadrícula atenuada a blanco y tinta/colores conservados."""
    img = img.astype(np.float32)
    alto, ancho = img.shape[:2]
    lado_menor = min(alto, ancho)
    k = max(lado_menor // 30, 3)
    k += 1 - k % 2  # impar
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    salida = np.empty_like(img)
    for canal in range(3):
        plano = img[:, :, canal].astype(np.uint8)
        fondo = cv2.morphologyEx(plano, cv2.MORPH_CLOSE, kernel).astype(np.float32)
        fondo = cv2.GaussianBlur(fondo, (0, 0), sigmaX=max(k, 3))
        fondo = np.clip(fondo, 1, 255)
        salida[:, :, canal] = np.clip(img[:, :, canal] / fondo * 255.0, 0, 255)
    salida = salida.astype(np.uint8)

    hsv = cv2.cvtColor(salida, cv2.COLOR_BGR2HSV).astype(np.float32)
    s, v = hsv[:, :, 1], hsv[:, :, 2]
    v_norm, s_norm = v / 255.0, s / 255.0
    blanco = (v_norm > 0.80) & (s_norm < 0.25)

    oscuridad = np.clip(1.0 - v_norm, 0.0, 1.0) ** (1.0 / 1.3)
    v_tinta = (1.0 - oscuridad) * 255.0
    s_tinta = np.clip(s * 1.1, 0, 255)

    hsv[:, :, 2] = np.where(blanco, 255.0, v_tinta)
    hsv[:, :, 1] = np.where(blanco, 0.0, s_tinta)
    return cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)


def procesar_pagina(img, esquinas=None) -> np.ndarray:
    if esquinas is not None:
        img = enderezar(img, esquinas)
    return realzar(img)


def armar_pdf(rutas: list, destino) -> None:
    """img2pdf, orden dado, sin recomprimir; escribe destino.tmp y renombra."""
    destino = Path(destino)
    tmp = destino.with_name(destino.name + ".tmp")
    datos = img2pdf.convert([str(r) for r in rutas])
    tmp.write_bytes(datos)
    os.replace(tmp, destino)


# ---------------------------------------------------------------- diagnóstico

@dataclass
class Diagnostico:
    estado: str          # sin_hoja | encuadre | quieto | desenfocado | listo | pasa_pagina
    mensaje: str
    esquinas: "list | None"  # 4 [x, y] normalizados 0..1 (o None)
    progreso: float = 0.0
    capturar: bool = False

    def a_dict(self) -> dict:
        return {
            "estado": self.estado,
            "mensaje": self.mensaje,
            "esquinas": self.esquinas,
            "progreso": self.progreso,
            "capturar": self.capturar,
        }


def _lados_fuera(esquinas, ancho, alto):
    margen_x, margen_y = MARGEN * ancho, MARGEN * alto
    xs, ys = esquinas[:, 0], esquinas[:, 1]
    lados = []
    if xs.min() <= margen_x:
        lados.append("izquierda")
    if xs.max() >= ancho - margen_x:
        lados.append("derecha")
    if ys.min() <= margen_y:
        lados.append("arriba")
    if ys.max() >= alto - margen_y:
        lados.append("abajo")
    return lados


def _normalizar(esquinas, ancho, alto):
    return (esquinas / np.array([ancho, alto], dtype=np.float32)).tolist()


class Detector:
    """Máquina de estados sobre una serie de frames: decide encuadre, quietud,
    enfoque y cuándo capturar, evitando duplicados al pasar de página."""

    def __init__(self):
        self._historial = []             # [(t, esquinas)] desde que se asentó
        self._nitidez_max = 0.0
        self._t_listo = None
        self._pasa_pagina = False
        self._esquinas_captura = None     # esquinas al momento de la última captura
        self._hubo_movimiento = False
        self._ultima_huella_pagina = None
        self._ultimas_esquinas = None
        self.ultima_huella_frame = None   # huella del último frame con hoja (para capturas)

    # ---- API pública

    def analizar(self, img, t: float) -> Diagnostico:
        alto, ancho = img.shape[:2]
        diagonal = float(np.hypot(ancho, alto))
        esquinas = detectar_hoja(img)
        self._ultimas_esquinas = esquinas

        enderezada = None
        if esquinas is not None:
            enderezada = enderezar(img, esquinas, LADO_ANALISIS)
            self.ultima_huella_frame = huella(enderezada)

        if self._pasa_pagina:
            return self._seguir_pasa_pagina(img, t, esquinas, enderezada, diagonal)
        return self._analizar_normal(img, t, esquinas, enderezada, diagonal)

    def registrar_captura(self, huella_pagina) -> None:
        """Entra a pasa_pagina con esa huella (captura forzada)."""
        self._entrar_pasa_pagina(self._ultimas_esquinas, huella_pagina)

    def fijar_ultima_huella(self, huella_pagina) -> None:
        """Tras borrar: huella de la última página restante, o None (no
        exige diferencia con la próxima captura)."""
        self._ultima_huella_pagina = huella_pagina

    # ---- internos

    def _reiniciar_estabilidad(self):
        self._historial = []
        self._nitidez_max = 0.0

    def _reiniciar_listo(self):
        self._t_listo = None

    def _chequear_encuadre(self, esquinas, ancho, alto):
        lados = _lados_fuera(esquinas, ancho, alto)
        if lados:
            mensaje = "Mové la cámara " + " y ".join(FRASES_LADO[l] for l in lados)
            return Diagnostico("encuadre", mensaje, None)
        area_frac = _area_poligono(esquinas) / (ancho * alto)
        if area_frac < AREA_MIN:
            return Diagnostico("encuadre", "Acercá", None)
        if area_frac > AREA_MAX:
            return Diagnostico("encuadre", "Alejá", None)
        sup_izq, sup_der, inf_der, inf_izq = esquinas
        lado_sup = np.linalg.norm(sup_der - sup_izq)
        lado_inf = np.linalg.norm(inf_der - inf_izq)
        lado_izq = np.linalg.norm(inf_izq - sup_izq)
        lado_der = np.linalg.norm(inf_der - sup_der)
        razon_h = min(lado_sup, lado_inf) / max(lado_sup, lado_inf, 1e-6)
        razon_v = min(lado_izq, lado_der) / max(lado_izq, lado_der, 1e-6)
        if min(razon_h, razon_v) < RAZON_LADOS_MIN:
            return Diagnostico("encuadre", "Poné el celular paralelo a la hoja", None)
        return None

    def _actualizar_quieto(self, t, esquinas, diagonal):
        """Devuelve True si el historial ya cubre QUIETO_SEG. Reinicia el
        historial (y el máximo de nitidez) si el desplazamiento respecto del
        frame anterior supera QUIETO_TOL de la diagonal."""
        if self._historial:
            _, previas = self._historial[-1]
            desplazamiento = float(np.linalg.norm(esquinas - previas, axis=1).max())
            if desplazamiento > QUIETO_TOL * diagonal:
                self._reiniciar_estabilidad()
        self._historial.append((t, esquinas))
        duracion = t - self._historial[0][0]
        return duracion >= QUIETO_SEG

    def _analizar_normal(self, img, t, esquinas, enderezada, diagonal):
        alto, ancho = img.shape[:2]

        if esquinas is None:
            self._reiniciar_estabilidad()
            self._reiniciar_listo()
            return Diagnostico("sin_hoja", "No veo la hoja", None)

        esquinas_norm = _normalizar(esquinas, ancho, alto)

        diag_encuadre = self._chequear_encuadre(esquinas, ancho, alto)
        if diag_encuadre is not None:
            self._reiniciar_estabilidad()
            self._reiniciar_listo()
            diag_encuadre.esquinas = esquinas_norm
            return diag_encuadre

        if not self._actualizar_quieto(t, esquinas, diagonal):
            self._reiniciar_listo()
            return Diagnostico("quieto", "Quieto…", esquinas_norm)

        n = nitidez(enderezada)
        self._nitidez_max = max(self._nitidez_max, n)
        if not (n >= NITIDEZ_MIN and n >= NITIDEZ_REL * self._nitidez_max):
            self._reiniciar_listo()
            return Diagnostico("desenfocado", "Desenfocado, esperá un segundo", esquinas_norm)

        if self._t_listo is None:
            self._t_listo = t
        transcurrido = t - self._t_listo
        progreso = min(transcurrido / CONFIRMAR_SEG, 1.0)
        # tolerancia chica para no perder el disparo por redondeo de floats
        capturar = False
        if transcurrido >= CONFIRMAR_SEG - 1e-9:
            progreso = 1.0
            capturar = True
            self._entrar_pasa_pagina(esquinas, self.ultima_huella_frame)
        return Diagnostico("listo", "¡Listo! No te muevas", esquinas_norm,
                           progreso=progreso, capturar=capturar)

    def _entrar_pasa_pagina(self, esquinas, huella_pagina):
        self._pasa_pagina = True
        self._esquinas_captura = None if esquinas is None else np.array(esquinas, dtype=np.float32)
        self._hubo_movimiento = False
        self._ultima_huella_pagina = huella_pagina
        self._reiniciar_estabilidad()
        self._reiniciar_listo()

    def _seguir_pasa_pagina(self, img, t, esquinas, enderezada, diagonal):
        alto, ancho = img.shape[:2]
        esquinas_norm = None if esquinas is None else _normalizar(esquinas, ancho, alto)

        if not self._hubo_movimiento:
            if esquinas is None or self._esquinas_captura is None:
                self._hubo_movimiento = True
            else:
                desplazamiento = float(np.linalg.norm(esquinas - self._esquinas_captura, axis=1).max())
                if desplazamiento > MOVIMIENTO_GRANDE * diagonal:
                    self._hubo_movimiento = True

        if not self._hubo_movimiento:
            return Diagnostico("pasa_pagina", "Pasá la página", esquinas_norm)

        if esquinas is None:
            return Diagnostico("pasa_pagina", "Pasá la página", None)

        diag = self._analizar_normal(img, t, esquinas, enderezada, diagonal)
        if diag.estado != "listo":
            return Diagnostico("pasa_pagina", "Pasá la página", diag.esquinas)

        huella_actual = huella(enderezada)
        if self._ultima_huella_pagina is not None and \
                distancia_huellas(huella_actual, self._ultima_huella_pagina) <= HUELLA_DIF_MIN:
            # misma página: no confirma el anillo, sigue esperando otra página
            self._reiniciar_listo()
            return Diagnostico("pasa_pagina", "Pasá la página", diag.esquinas)

        self._pasa_pagina = False
        return diag
