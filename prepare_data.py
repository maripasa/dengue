import csv
import gzip
import io
import json
import os
import re
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import shapefile
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw/sinan_dengue_ce"
MESH = ROOT / "data/raw/ibge/CE_Municipios_2025.zip"
GRAPH = ROOT / "data/processed/dengue_v1"
PANEL = ROOT / "data/processed/dengue_confirmed_weekly"
DENGUE_URL = "https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue"
MESH_URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2025/UFs/CE/CE_Municipios_2025.zip"


def dengue_resources():
    with urlopen(DENGUE_URL, timeout=60) as response:
        html = response.read().decode("utf-8")
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not match:
        raise RuntimeError("Could not find dengue dataset metadata")
    resources = json.loads(match.group(1))["props"]["pageProps"]["resources"]
    result = []
    for resource in resources:
        year = re.fullmatch(r"Dengue - (20\d{2})", resource["name"])
        if resource.get("format") == "CSV" and year:
            result.append((int(year.group(1)), resource["url"], resource["last_modified"]))
    return sorted(result)


def download_dengue_year(year, url, last_modified):
    target = RAW / f"dengue_ce_{year}.csv.gz"
    with tempfile.NamedTemporaryFile(dir=RAW, suffix=".csv.gz", delete=False) as pending:
        pending_path = Path(pending.name)
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip") as temp:
            with urlopen(url, timeout=120) as response:
                source_bytes = 0
                while chunk := response.read(1024 * 1024):
                    temp.write(chunk)
                    source_bytes += len(chunk)
            temp.flush()
            with ZipFile(temp.name) as archive:
                files = [item for item in archive.infolist() if item.filename.lower().endswith(".csv")]
                if len(files) != 1:
                    raise RuntimeError(f"Expected one CSV in {url}; got {len(files)}")
                source_uncompressed_bytes = files[0].file_size
                with archive.open(files[0]) as raw:
                    reader = csv.reader(io.TextIOWrapper(raw, encoding="latin-1", newline=""))
                    header = next(reader)
                    uf_index = header.index("SG_UF")
                    municipality_index = header.index("ID_MN_RESI")
                    count = by_state = by_municipality = missing_municipality = 0
                    with gzip.open(pending_path, "wt", encoding="latin-1", newline="") as dest:
                        writer = csv.writer(dest)
                        writer.writerow(header)
                        for row in reader:
                            uf = row[uf_index].strip().upper()
                            municipality = row[municipality_index].strip()
                            state_match = uf in {"CE", "23", "23.0"}
                            municipality_match = bool(re.fullmatch(r"23\d{4,5}", municipality))
                            if state_match or municipality_match:
                                writer.writerow(row)
                                count += 1
                                by_state += state_match
                                by_municipality += municipality_match
                                missing_municipality += not municipality_match
        os.replace(pending_path, target)
    finally:
        pending_path.unlink(missing_ok=True)
    return {
        "year": year,
        "url": url,
        "source_last_modified": last_modified,
        "national_zip_bytes": source_bytes,
        "national_csv_bytes": source_uncompressed_bytes,
        "ce_records": count,
        "ce_state_match_records": by_state,
        "ce_municipality_match_records": by_municipality,
        "ce_missing_or_invalid_municipality_records": missing_municipality,
        "ce_gzip_bytes": target.stat().st_size,
        "file": str(target.relative_to(ROOT)),
    }


def download_dengue():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest_path = RAW / "manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": []}
    previous_by_year = {item["year"]: item for item in previous["files"]}
    result = {
        "dataset_url": DENGUE_URL,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": [],
    }
    for year, url, last_modified in dengue_resources():
        old = previous_by_year.get(year)
        target = RAW / f"dengue_ce_{year}.csv.gz"
        if (old and target.exists() and old["url"] == url
                and old["source_last_modified"] == last_modified
                and old["ce_gzip_bytes"] == target.stat().st_size):
            item = old
            print(f"{year}: sem alterações", flush=True)
        else:
            item = download_dengue_year(year, url, last_modified)
            print(f"{year}: {item['ce_records']:,} registros do CE", flush=True)
        result["files"].append(item)
        manifest_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


def download_mesh():
    MESH.parent.mkdir(parents=True, exist_ok=True)
    if MESH.exists():
        with ZipFile(MESH) as archive:
            if any(name.endswith(".shp") for name in archive.namelist()):
                return
    with tempfile.NamedTemporaryFile(dir=MESH.parent, suffix=".zip", delete=False) as pending:
        pending_path = Path(pending.name)
    try:
        with urlopen(MESH_URL, timeout=120) as response, pending_path.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        with ZipFile(pending_path) as archive:
            if not any(name.endswith(".shp") for name in archive.namelist()):
                raise ValueError("Invalid IBGE municipality archive")
        os.replace(pending_path, MESH)
    finally:
        pending_path.unlink(missing_ok=True)


def prepare_graph():
    with ZipFile(MESH) as archive:
        names = archive.namelist()

        def member(suffix):
            return io.BytesIO(archive.read(next(name for name in names if name.endswith(suffix))))

        reader = shapefile.Reader(shp=member(".shp"), shx=member(".shx"), dbf=member(".dbf"))
        fields = [field[0] for field in reader.fields[1:]]
        nodes = {}
        for feature in reader.iterShapeRecords():
            attributes = dict(zip(fields, feature.record))
            nodes[attributes["CD_MUN"]] = (
                attributes["NM_MUN"], shape(feature.shape.__geo_interface__)
            )
    if len(nodes) != 184:
        raise ValueError("Expected 184 municipalities in the Ceará mesh")
    codes = sorted(nodes)
    GRAPH.mkdir(parents=True, exist_ok=True)
    with (GRAPH / "municipios.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["municipio_ibge", "municipio_nome"])
        writer.writerows((code, nodes[code][0]) for code in codes)
    with (GRAPH / "arestas_vizinhos.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["municipio_origem", "municipio_destino"])
        for index, source in enumerate(codes):
            for target in codes[index + 1:]:
                if nodes[source][1].boundary.intersection(nodes[target][1].boundary).length > 0:
                    writer.writerow([source, target])


def sunday(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def prepare_weekly():
    with (GRAPH / "municipios.csv").open(newline="", encoding="utf-8") as stream:
        codes = sorted(row["municipio_ibge"] for row in csv.DictReader(stream))
    if len(codes) != 184 or len(set(codes)) != 184:
        raise ValueError("Expected 184 unique Ceará municipality codes")
    code_set = set(codes)
    six_to_seven = {code[:6]: code for code in codes}
    if len(six_to_seven) != len(codes):
        raise ValueError("Ambiguous six-digit municipality codes")

    counts = Counter()
    audit = Counter()
    latest_date = None
    paths = sorted(RAW.glob("dengue_ce_*.csv.gz"))
    if not paths:
        raise FileNotFoundError(f"No annual dengue files in {RAW}")
    for path in paths:
        year = int(path.name.split("_")[-1].split(".")[0])
        if year < 2007:
            continue
        positive_codes = {"1", "2", "3", "4"} if year <= 2013 else {"10", "11", "12"}
        with gzip.open(path, "rt", newline="", encoding="latin-1") as stream:
            for row in csv.DictReader(stream):
                audit["records_read"] += 1
                if row["SG_UF"].strip().upper() not in {"CE", "23", "23.0"}:
                    audit["other_residence_uf"] += 1
                    continue
                classification = row["CLASSI_FIN"].strip().removesuffix(".0")
                criterion = row["CRITERIO"].strip().removesuffix(".0")
                if classification not in positive_codes:
                    audit["not_classified_as_dengue"] += 1
                    continue
                if criterion not in {"1", "2"}:
                    audit["criterion_not_concluded"] += 1
                    continue
                raw_code = row["ID_MN_RESI"].strip().removesuffix(".0")
                code = raw_code if raw_code in code_set else six_to_seven.get(raw_code)
                if code is None:
                    audit["invalid_residence_municipality"] += 1
                    continue
                try:
                    day = date.fromisoformat(row["DT_NOTIFIC"].strip())
                except ValueError:
                    audit["invalid_notification_date"] += 1
                    continue
                latest_date = max(latest_date, day) if latest_date else day
                counts[sunday(day), code] += 1
                audit["selected_records"] += 1

    if latest_date is None:
        raise ValueError("No classified dengue cases with valid dates")
    first_week = sunday(date(2007, 1, 1)) + timedelta(days=7)
    last_week = sunday(latest_date)
    if last_week + timedelta(days=6) > latest_date:
        last_week -= timedelta(days=7)
    weeks = []
    current = first_week
    while current <= last_week:
        weeks.append(current)
        current += timedelta(days=7)

    PANEL.mkdir(parents=True, exist_ok=True)
    with gzip.open(PANEL / "casos_municipio_semana.csv.gz", "wt", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["municipio_ibge", "semana_inicio", "casos_dengue"])
        for week in weeks:
            for code in codes:
                writer.writerow([code, week.isoformat(), counts[week, code]])
    manifest = {
        "definition": "CLASSI_FIN=1..4 (2007-2013) or 10..12 (2014+), CRITERIO=1 or 2",
        "time_field": "DT_NOTIFIC",
        "location_field": "ID_MN_RESI",
        "first_week": weeks[0].isoformat(),
        "last_week": weeks[-1].isoformat(),
        "weeks": len(weeks),
        "municipalities": len(codes),
        "panel_rows": len(weeks) * len(codes),
        "panel_cases": sum(counts[week, code] for week in weeks for code in codes),
        "audit": dict(audit),
        "note": "First and last incomplete boundary weeks are omitted; 2026 is partial.",
    }
    (PANEL / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(weeks)} semanas, {len(codes)} municípios, {manifest['panel_cases']} casos")


def prepare_data():
    download_dengue()
    download_mesh()
    prepare_graph()
    prepare_weekly()
