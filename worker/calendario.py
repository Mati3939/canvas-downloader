"""Lee el calendario principal de Google (solo lectura) y arma las filas de
`calendar_events` para publicar en Supabase: los bloques de clases (eventos
cuya descripcion lleva la marca de horario) y las evaluaciones (certamenes,
pruebas, controles, examenes, entregas).
"""
import re
from datetime import datetime, timedelta, timezone

MARCA_HORARIO_POR_DEFECTO = "[Horario"
DIAS_ATRAS = 7
DIAS_ADELANTE = 42

_PATRON_EVALUACION = re.compile(
    r"\b(certamen(es)?|pruebas?|control(es)?|ex[aá]men(es)?|evaluaci[oó]n(es)?"
    r"|interrogaci[oó]n(es)?|solemnes?|quiz|entregas?)\b",
    re.IGNORECASE,
)
_LARGO_MAX_DESCRIPCION = 2000


def ventana(ahora: datetime | None = None) -> tuple[datetime, datetime]:
    """Rango de fechas que se publica: desde hace una semana hasta seis
    semanas adelante."""
    ahora = ahora or datetime.now(timezone.utc)
    return ahora - timedelta(days=DIAS_ATRAS), ahora + timedelta(days=DIAS_ADELANTE)


def clasificar(evento: dict, marca: str) -> str | None:
    """'clase', 'evaluacion' o None (el evento no se publica)."""
    if marca and marca in (evento.get("description") or ""):
        return "clase"
    if _PATRON_EVALUACION.search(evento.get("summary") or ""):
        return "evaluacion"
    return None


def _inicio_fin(evento: dict) -> tuple[str, str, bool] | None:
    inicio, fin = evento.get("start") or {}, evento.get("end") or {}
    if inicio.get("dateTime") and fin.get("dateTime"):
        return inicio["dateTime"], fin["dateTime"], False
    if inicio.get("date") and fin.get("date"):
        # Evento de dia completo: se guarda a las 04:00 UTC (medianoche o
        # 01:00 en Chile), asi la fecha local es siempre la del evento.
        return f"{inicio['date']}T04:00:00Z", f"{fin['date']}T04:00:00Z", True
    return None


def fila_evento(evento: dict, marca: str) -> dict | None:
    """Fila de `calendar_events` (sin user_id) o None si no se publica."""
    if evento.get("status") == "cancelled":
        return None
    tipo = clasificar(evento, marca)
    if tipo is None:
        return None
    rango = _inicio_fin(evento)
    if rango is None:
        return None
    inicio, fin, dia_completo = rango
    return {
        "google_id": evento["id"],
        "title": evento.get("summary") or "",
        "location": evento.get("location") or None,
        "description": (evento.get("description") or "")[:_LARGO_MAX_DESCRIPCION] or None,
        "start_at": inicio,
        "end_at": fin,
        "all_day": dia_completo,
        "kind": tipo,
        "html_link": evento.get("htmlLink") or None,
    }


def leer_eventos(servicio, desde: datetime, hasta: datetime, marca: str) -> list[dict]:
    """Filas de clases y evaluaciones del calendario principal entre `desde`
    y `hasta`, con las repeticiones ya expandidas."""
    filas, token = [], None
    while True:
        resp = servicio.events().list(
            calendarId="primary",
            timeMin=desde.isoformat(),
            timeMax=hasta.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
            pageToken=token,
        ).execute()
        for evento in resp.get("items", []):
            fila = fila_evento(evento, marca)
            if fila is not None:
                filas.append(fila)
        token = resp.get("nextPageToken")
        if not token:
            return filas
