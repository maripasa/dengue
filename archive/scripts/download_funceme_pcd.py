"""Download FUNCEME PCD daily rain and 2 m air temperature for a common period."""

import csv
import gzip
import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/funceme_pcd"
BASE = "https://api1.funceme.br"
START_YEAR = 2018
END_YEAR = 2025


def get_json(url):
    for attempt in range(4):
        try:
            with urlopen(url, timeout=45) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def station_catalog():
    catalog_path = OUT / "stations.json"
    if catalog_path.exists():
        return json.loads(catalog_path.read_text())
    url = BASE + "/rest/pcd/estacao_pcd?limit=no&orderBy=id"
    all_stations = get_json(url)["data"]["list"]
    ce = [s for s in all_stations
          if str(s.get("municipio", "")).split(".")[0].startswith("23")
          and s.get("tipo_estacao") in (1.0, 3.0)
          and (s.get("dt_inicio_ativ") or s.get("dt_inst") or "9999")[:4] <= str(START_YEAR)
          and (s.get("dt_fim_ativ") or "9999")[:4] >= str(END_YEAR)]

    def detail(station):
        result = get_json(BASE + f"/rest/pcd/estacao_pcd/{station['id']}?with=sensor")["data"]
        result["sensor_ids"] = [int(s["id"]) for s in result.pop("sensor", [])]
        return result

    with ThreadPoolExecutor(max_workers=6) as pool:
        stations = list(pool.map(detail, ce))
    stations = [s for s in stations if {2, 22}.issubset(s["sensor_ids"])]
    stations.sort(key=lambda s: s["id"])
    if not stations:
        raise RuntimeError("Nenhuma estação PCD com temperatura e chuva")
    catalog_path.write_text(json.dumps(stations, ensure_ascii=False, indent=2) + "\n")
    print(f"Cadastro FUNCEME: {len(stations)} estações, "
          f"{len({int(s['municipio']) for s in stations})} municípios", flush=True)
    return stations


def fetch_half(station, year, month_start, month_end):
    params = {
        "estacao": station["id"], "sensor": "2,22",
        "data_inicio": f"{year}-{month_start}",
        "data_fim": f"{year}-{month_end}",
    }
    url = BASE + "/rpc/v1/dado-sensor-diario?" + urlencode(params)
    response = get_json(url)
    if "data" not in response:
        raise RuntimeError(f"Resposta sem dados para estação {station['id']}: {response}")
    values = {}
    for sensor in response["data"]["list"]:
        field = {2: "temperature_c", 22: "precipitation_mm"}.get(int(sensor["name"]))
        if field is None:
            continue
        for item in sensor["series"]:
            day = item["name"][:10]
            values.setdefault(day, {})[field] = item["value"]
    return values


def fetch_station_year(station, year):
    first = fetch_half(station, year, "01-01", "06-30")
    second = fetch_half(station, year, "07-01", "12-31")
    first.update(second)
    code = str(int(station["municipio"]))
    return [
        (station["id"], code, day, value.get("temperature_c", ""),
         value.get("precipitation_mm", ""))
        for day, value in sorted(first.items())
    ]


def download_year(stations, year):
    target = OUT / f"pcd_daily_{year}.csv.gz"
    if target.exists():
        print(f"FUNCEME {year}: já baixado", flush=True)
        return
    with ThreadPoolExecutor(max_workers=6) as pool:
        result = list(pool.map(lambda station: fetch_station_year(station, year), stations))
    with tempfile.NamedTemporaryFile(dir=OUT, suffix=".csv.gz", delete=False) as out:
        pending = Path(out.name)
    try:
        with gzip.open(pending, "wt", encoding="utf-8", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(["station_id", "municipio_ibge", "date",
                             "temperature_c", "precipitation_mm"])
            for station_rows in result:
                writer.writerows(station_rows)
        os.replace(pending, target)
    finally:
        pending.unlink(missing_ok=True)
    print(f"FUNCEME {year}: {sum(map(len, result)):,} linhas", flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stations = station_catalog()
    for year in range(START_YEAR, END_YEAR + 1):
        download_year(stations, year)


if __name__ == "__main__":
    main()
