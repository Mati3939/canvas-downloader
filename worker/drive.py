"""Enlaces de Google Drive: resuelve la ruta de un archivo o carpeta ya
sincronizado por Google Drive para Escritorio y devuelve su `webViewLink`,
para publicarlo junto con cada archivo/ramo en Supabase.

Solo lectura de metadata (`drive.metadata.readonly`); nunca se sube ni se
modifica nada en Drive.
"""
import json
from pathlib import Path

from sync_ramos import guardar_json_atomico

SCOPES = ["https://www.googleapis.com/auth/drive.metadata.readonly"]
_MIME_CARPETA = "application/vnd.google-apps.folder"


class DriveNoAutorizado(Exception):
    """No hay un token de Drive utilizable. Corre: python -m worker.drive"""


def ruta_en_mi_unidad(drive_root: Path) -> list[str]:
    """Partes de la ruta después del componente 'Mi unidad' (o 'My Drive').

    `ValueError` si ninguno de los dos aparece en la ruta.
    """
    partes = Path(drive_root).parts
    for nombre in ("Mi unidad", "My Drive"):
        if nombre in partes:
            i = partes.index(nombre)
            return list(partes[i + 1:])
    raise ValueError(
        f"La ruta no esta dentro de 'Mi unidad' ni 'My Drive': {drive_root}"
    )


def _escapar(nombre: str) -> str:
    """Escapa `\\` y `'` para usar el nombre dentro de una query de Drive."""
    return nombre.replace("\\", "\\\\").replace("'", "\\'")


class EnlacesDrive:
    """Resuelve rutas (listas de nombres) a `webViewLink` de Drive, bajando
    nivel a nivel desde 'root'. Cachea ids de carpeta por ruta y el enlace
    de cada hoja ya resuelta; nunca cachea `None`."""

    def __init__(self, servicio, cache_path: Path):
        self._servicio = servicio
        self._cache_path = Path(cache_path)
        self._carpetas, self._enlaces = self._cargar()

    def _cargar(self):
        if self._cache_path.exists():
            try:
                datos = json.loads(self._cache_path.read_text(encoding="utf-8"))
                return datos.get("carpetas", {}), datos.get("enlaces", {})
            except (OSError, ValueError):
                pass
        return {}, {}

    def guardar(self):
        guardar_json_atomico(
            self._cache_path,
            {"carpetas": self._carpetas, "enlaces": self._enlaces},
        )

    def _buscar(self, padre_id, nombre):
        q = f"'{padre_id}' in parents and name = '{_escapar(nombre)}' and trashed = false"
        try:
            resp = self._servicio.files().list(
                q=q, fields="files(id, name, mimeType, webViewLink)", pageSize=10,
            ).execute()
        except Exception as e:
            # Falla de la API de Drive (HTTP, red) al resolver esta ruta: no
            # abortar el lote completo, solo esta ruta (no se cachea, se
            # reintenta en la próxima corrida). Los errores de programación
            # (TypeError, AttributeError, etc.) sí se propagan.
            from googleapiclient.errors import HttpError

            if isinstance(e, (HttpError, OSError)):
                return None
            raise
        archivos = resp.get("files", [])
        return archivos[0] if archivos else None

    def enlace(self, partes: list[str]) -> str | None:
        """webViewLink del archivo o carpeta en `partes` (ruta desde la raíz
        de Mi unidad). `None` si todavía no existe en Drive o si falló la
        consulta a la API en algún nivel de la ruta."""
        ruta_completa = "/".join(partes)
        if ruta_completa in self._enlaces:
            return self._enlaces[ruta_completa]

        padre_id = "root"
        ruta_parcial = ""
        for i, nombre in enumerate(partes):
            ruta_parcial = nombre if not ruta_parcial else f"{ruta_parcial}/{nombre}"
            es_ultimo = i == len(partes) - 1

            if not es_ultimo and ruta_parcial in self._carpetas:
                padre_id = self._carpetas[ruta_parcial]
                continue

            encontrado = self._buscar(padre_id, nombre)
            if encontrado is None:
                return None

            if es_ultimo:
                link = encontrado.get("webViewLink")
                if link is not None:
                    self._enlaces[ruta_completa] = link
                return link

            if encontrado.get("mimeType") != _MIME_CARPETA:
                return None
            padre_id = encontrado["id"]
            self._carpetas[ruta_parcial] = padre_id

        return None


def conectar_drive(estado_dir: Path, interactivo: bool = False):
    """Servicio de Drive v3 (solo metadata), autenticado con
    `google_client.json` / `google_token.json` en `estado_dir`.

    Sin token utilizable (falta, corrupto, o refresh falló) y
    `interactivo=False` lanza `DriveNoAutorizado`. Con `interactivo=True`,
    esos mismos casos caen al flujo `InstalledAppFlow` (abre el navegador) y
    guardan el token nuevo.
    """
    estado_dir = Path(estado_dir)
    cliente_path = estado_dir / "google_client.json"
    token_path = estado_dir / "google_token.json"

    if not token_path.exists() and not interactivo:
        raise DriveNoAutorizado(
            "No hay token de Drive. Corre: python -m worker.drive"
        )

    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if creds.valid:
                return build("drive", "v3", credentials=creds)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_path.write_text(creds.to_json(), encoding="utf-8")
                return build("drive", "v3", credentials=creds)
        except (ValueError, GoogleAuthError):
            # Token corrupto (JSON invalido) o refresh fallido (revocado,
            # expirado sin refresh_token, o error de red/transporte de
            # Google): se trata igual que "sin token utilizable".
            pass

    if not interactivo:
        raise DriveNoAutorizado(
            "No hay un token de Drive valido. Corre: python -m worker.drive"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(cliente_path), SCOPES)
    creds = flow.run_local_server(port=0)
    estado_dir.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("drive", "v3", credentials=creds)


if __name__ == "__main__":
    _estado_dir = Path(__file__).resolve().parent.parent / "worker_estado"
    conectar_drive(_estado_dir, interactivo=True)
    print("Autorizacion de Drive guardada.")
