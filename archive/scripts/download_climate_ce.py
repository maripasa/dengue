"""Download Ceará boundaries and daily temperature/precipitation from NASA POWER."""

import csv
import gzip
import io
import json
import math
import os
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo
from zipfile import ZipFile

import shapefile
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
IBGE_FILE = ROOT / "data/raw/ibge/CE_Municipios_2025.zip"
CLIMATE_DIR = ROOT / "data/raw/climate_ce"
IBGE_URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/CE/CE_Municipios_2025.zip"
NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/regional"
BOUNDS = {"latitude-min": -8, "latitude-max": -2.5, "longitude-min": -41.5, "longitude-max": -37}


def atomic_json(path, value):
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as out:
        pending = Path(out.name)
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write("\n")
    os.replace(pending, path)


def download_ibge():
    IBGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if IBGE_FILE.exists():
        with ZipFile(IBGE_FILE) as archive:
            if archive.testzip() is None:
                print("Malha IBGE: já baixada", flush=True)
                return
        raise RuntimeError("Malha IBGE corrompida")
    with tempfile.NamedTemporaryFile(dir=IBGE_FILE.parent, suffix=".zip", delete=False) as out:
        pending = Path(out.name)
    try:
        with urlopen(IBGE_URL, timeout=120) as response, pending.open("wb") as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        with ZipFile(pending) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Download da malha corrompido")
        os.replace(pending, IBGE_FILE)
    finally:
        pending.unlink(missing_ok=True)


def municipality_points():
    with ZipFile(IBGE_FILE) as archive:
        names = archive.namelist()
        def member(suffix):
            return io.BytesIO(archive.read(next(n for n in names if n.endswith(suffix))))
        reader = shapefile.Reader(shp=member(".shp"), shx=member(".shx"), dbf=member(".dbf"))
        fields = [field[0] for field in reader.fields[1:]]
        points = []
        for feature in reader.iterShapeRecords():
            attrs = dict(zip(fields, feature.record))
            point = shape(feature.shape.__geo_interface__).representative_point()
            points.append((attrs["CD_MUN"], point.y, point.x))
    points.sort()
    if len(points) != 184 or len({p[0] for p in points}) != 184:
        raise RuntimeError("Malha não contém 184 municípios únicos")
    return points


def fetch(year, end_date, parameter):
    params = {**BOUNDS, "parameters": parameter, "community": "AG",
              "start": f"{year}0101", "end": end_date.replace("-", ""),
              "format": "JSON", "time-standard": "UTC"}
    url = NASA_URL + "?" + urlencode(params)
    for attempt in range(5):
        try:
            with urlopen(url, timeout=180) as response:
                data = json.load(response)
            if not data.get("features"):
                raise RuntimeError(f"Resposta vazia: {year} {parameter}")
            return url, data
        except (HTTPError, URLError, TimeoutError) as exc:
            if attempt == 4:
                raise RuntimeError(f"Falha em {year} {parameter}: {exc}") from exc
            time.sleep(2 ** attempt)


def cells(data, parameter):
    return {tuple(f["geometry"]["coordinates"][:2]): f["properties"]["parameter"][parameter]
            for f in data["features"]}


def process_year(year, end_date, points):
    temp_url, temp_data = fetch(year, end_date, "T2M")
    rain_url, rain_data = fetch(year, end_date, "PRECTOTCORR")
    temperature = cells(temp_data, "T2M")
    rain = cells(rain_data, "PRECTOTCORR")
    if temperature.keys() != rain.keys():
        raise RuntimeError(f"Grades incompatíveis em {year}")
    days = list(next(iter(temperature.values())))
    if days[0] != f"{year}0101" or days[-1] != end_date.replace("-", ""):
        raise RuntimeError(f"Período incompleto em {year}")
    if any(list(series) != days for series in (*temperature.values(), *rain.values())):
        raise RuntimeError(f"Datas diferentes entre células em {year}")

    raw_target = CLIMATE_DIR / f"nasa_power_grade_ce_{year}.json.gz"
    municipal_target = CLIMATE_DIR / f"nasa_power_municipios_ce_{year}.csv.gz"
    with tempfile.NamedTemporaryFile(dir=CLIMATE_DIR, suffix=".json.gz", delete=False) as out:
        raw_pending = Path(out.name)
    with tempfile.NamedTemporaryFile(dir=CLIMATE_DIR, suffix=".csv.gz", delete=False) as out:
        municipal_pending = Path(out.name)
    try:
        with gzip.open(raw_pending, "wt", encoding="utf-8") as out:
            json.dump({"T2M": temp_data, "PRECTOTCORR": rain_data}, out, ensure_ascii=False)
        missing_temp = missing_rain = 0
        with gzip.open(municipal_pending, "wt", encoding="utf-8", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(["municipio_ibge", "data", "temperatura_media_c",
                             "precipitacao_mm", "latitude_grade", "longitude_grade"])
            for code, latitude, longitude in points:
                nearest = min(temperature, key=lambda xy: math.hypot(xy[0] - longitude, xy[1] - latitude))
                for day in days:
                    t, p = temperature[nearest][day], rain[nearest][day]
                    missing_temp += t == -999
                    missing_rain += p == -999
                    writer.writerow([code, f"{day[:4]}-{day[4:6]}-{day[6:]}",
                                     "" if t == -999 else t, "" if p == -999 else p,
                                     nearest[1], nearest[0]])
        os.replace(raw_pending, raw_target)
        os.replace(municipal_pending, municipal_target)
    finally:
        raw_pending.unlink(missing_ok=True)
        municipal_pending.unlink(missing_ok=True)
    return {
        "year": year, "end_date": end_date, "days": len(days),
        "grid_cells": len(temperature), "municipal_records": len(points) * len(days),
        "missing_temperature": missing_temp, "missing_precipitation": missing_rain,
        "temperature_url": temp_url, "precipitation_url": rain_url,
        "raw_file": str(raw_target.relative_to(ROOT)),
        "municipal_file": str(municipal_target.relative_to(ROOT)),
        "raw_bytes": raw_target.stat().st_size, "municipal_bytes": municipal_target.stat().st_size,
    }


def main():
    download_ibge()
    points = municipality_points()
    CLIMATE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = CLIMATE_DIR / "manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"years": []}
    old_by_year = {item["year"]: item for item in previous["years"]}
    latest = datetime.now(ZoneInfo("America/Sao_Paulo")).date() - timedelta(days=6)
    manifest = {
        "malha_url": IBGE_URL, "malha_file": str(IBGE_FILE.relative_to(ROOT)),
        "climate_source": "NASA POWER Daily API",
        "climate_docs": "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
        "bounds": BOUNDS,
        "method": "Ponto interno por município associado à célula NASA POWER mais próxima; não é média da área municipal",
        "time_standard": "UTC", "municipalities": len(points),
        "checked_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "years": [],
    }
    for year in range(2000, latest.year + 1):
        end_date = min(date(year, 12, 31), latest).isoformat()
        old = old_by_year.get(year)
        if (old and old["end_date"] == end_date and
                (ROOT / old["raw_file"]).exists() and
                (ROOT / old["municipal_file"]).exists()):
            item = old
            print(f"Clima {year}: sem alterações", flush=True)
        else:
            item = process_year(year, end_date, points)
            print(f"Clima {year}: {item['municipal_records']:,} registros", flush=True)
        manifest["years"].append(item)
        atomic_json(manifest_path, manifest)


if __name__ == "__main__":
    main()
