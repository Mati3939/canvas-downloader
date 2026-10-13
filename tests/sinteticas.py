"""Imágenes sintéticas de una hoja de cuaderno sobre una mesa, para los tests
de escaner.py y de la API de escaneo. Sin red ni archivos reales."""
import cv2
import numpy as np


def esquinas_centradas(area_frac, tam=(1280, 720), razon=None):
    """Esquinas (4,2) float32 de un rectángulo centrado que ocupa `area_frac`
    del frame `tam` (ancho, alto). Sin `razon`, mantiene la proporción del
    propio frame (así cualquier area_frac <= 1 entra sin salirse del cuadro).
    Con `razon` (alto/ancho), fuerza esa proporción. Orden: sup-izq, sup-der,
    inf-der, inf-izq."""
    ancho, alto = tam
    if razon is None:
        w = ancho * (area_frac ** 0.5)
        h = alto * (area_frac ** 0.5)
    else:
        area_hoja = ancho * alto * area_frac
        w = (area_hoja / razon) ** 0.5
        h = w * razon
    cx, cy = ancho / 2, alto / 2
    x0, y0 = cx - w / 2, cy - h / 2
    x1, y1 = cx + w / 2, cy + h / 2
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32)


def hoja_sintetica(esquinas, tam=(1280, 720), texto="Apuntes de prueba",
                    desenfoque=0, fondo=60, papel=235, lineas=1):
    """Imagen BGR uint8: fondo gris oscuro `fondo`, hoja clara `papel` como
    polígono de 4 esquinas (píxeles, cualquier orden), con cuadrícula
    gris-azulada tenue, `lineas` renglones de texto negro (tinta) y un trazo
    amarillo saturado (resaltador). `desenfoque` es el kernel (impar) de un
    GaussianBlur opcional sobre toda la imagen, para simular falta de foco.
    `lineas` sirve para simular páginas con más o menos texto (útil para que
    dos páginas "distintas" den una huella bien diferente, no solo una
    palabra distinta en un renglón, que una huella de 32x32 casi no nota)."""
    ancho, alto = tam
    img = np.full((alto, ancho, 3), fondo, dtype=np.uint8)
    pts = np.round(np.asarray(esquinas, dtype=np.float32)).astype(np.int32)
    cv2.fillConvexPoly(img, pts, (papel, papel, papel))

    mascara = np.zeros((alto, ancho), dtype=np.uint8)
    cv2.fillConvexPoly(mascara, pts, 255)

    x0, y0 = int(pts[:, 0].min()), int(pts[:, 1].min())
    x1, y1 = int(pts[:, 0].max()), int(pts[:, 1].max())

    # Todo el contenido de la hoja (grilla, texto, resaltador) se dibuja en una
    # capa aparte y se recorta con la máscara del polígono real: si no, en
    # trapecios fuertes el texto (posicionado por la caja del bounding box)
    # queda fuera del polígono angosto y contamina el fondo.
    capa = img.copy()
    color_grilla = (225, 215, 200)  # gris-azulado claro (B,G,R), poca saturación
    for x in range(x0, x1, 20):
        cv2.line(capa, (x, y0), (x, y1), color_grilla, 1)
    for y in range(y0, y1, 20):
        cv2.line(capa, (x0, y), (x1, y), color_grilla, 1)

    if x1 - x0 > 60 and y1 - y0 > 90:
        cv2.putText(capa, texto, (x0 + 15, y0 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                    (20, 20, 20), 2, cv2.LINE_AA)
        cv2.line(capa, (x0 + 15, y0 + 70), (x1 - 15, y0 + 70), (0, 220, 230), 6)
        for i in range(1, lineas):
            y_renglon = y0 + 105 + (i - 1) * 35
            if y_renglon > y1 - 15:
                break
            cv2.putText(capa, texto, (x0 + 15, y_renglon), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (20, 20, 20), 2, cv2.LINE_AA)

    img = np.where(mascara[:, :, None] > 0, capa, img)

    if desenfoque:
        k = desenfoque if desenfoque % 2 == 1 else desenfoque + 1
        img = cv2.GaussianBlur(img, (k, k), 0)
    return img
