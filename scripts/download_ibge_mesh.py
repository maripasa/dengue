import os
import tempfile
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data/raw/ibge/CE_Municipios_2025.zip"
URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/CE/CE_Municipios_2025.zip"


def valid_zip(path):
    try:
        with ZipFile(path) as archive:
            return any(name.endswith(".shp") for name in archive.namelist())
    except FileNotFoundError:
        return False


def main():
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if valid_zip(DESTINATION):
        print(DESTINATION)
        return
    with tempfile.NamedTemporaryFile(dir=DESTINATION.parent, suffix=".zip", delete=False) as pending:
        pending_path = Path(pending.name)
    try:
        with urlopen(URL, timeout=120) as response, pending_path.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        if not valid_zip(pending_path):
            raise ValueError("Invalid IBGE municipality archive")
        os.replace(pending_path, DESTINATION)
    finally:
        pending_path.unlink(missing_ok=True)
    print(DESTINATION)


if __name__ == "__main__":
    main()
