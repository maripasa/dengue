"""Create a weekly dengue count panel and a municipal adjacency graph."""

import csv
import gzip
import io
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from zipfile import ZipFile

import shapefile
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/sinan_dengue_ce"
MESH = ROOT / "data/raw/ibge/CE_Municipios_2025.zip"
OUT = ROOT / "data/processed/dengue_v1"


def week_start(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def epi_year_week(start):
    # Brazilian epidemiological weeks run Sunday–Saturday. The week belongs
    # to the year containing its Wednesday (at least four days of that year).
    year = (start + timedelta(days=3)).year
    january_fourth = date(year, 1, 4)
    first = week_start(january_fourth)
    number = (start - first).days // 7 + 1
    return year, number


def municipalities_and_edges():
    with ZipFile(MESH) as archive:
        names = archive.namelist()
        def member(suffix):
            return io.BytesIO(archive.read(next(n for n in names if n.endswith(suffix))))
        reader = shapefile.Reader(shp=member(".shp"), shx=member(".shx"), dbf=member(".dbf"))
        fields = [field[0] for field in reader.fields[1:]]
        municipalities = {}
        for feature in reader.iterShapeRecords():
            attrs = dict(zip(fields, feature.record))
            municipalities[attrs["CD_MUN"]] = {
                "name": attrs["NM_MUN"],
                "geometry": shape(feature.shape.__geo_interface__),
            }
    if len(municipalities) != 184:
        raise RuntimeError("Expected 184 Ceará municipalities")
    codes = sorted(municipalities)
    edges = []
    for index, source in enumerate(codes):
        for target in codes[index + 1:]:
            shared = municipalities[source]["geometry"].boundary.intersection(
                municipalities[target]["geometry"].boundary
            )
            if shared.length > 0:
                edges.append((source, target))
    return municipalities, edges


def dengue_counts(codes):
    six_digit = {}
    for code in codes:
        prefix = code[:6]
        if prefix in six_digit:
            raise RuntimeError(f"Ambiguous six-digit municipality code: {prefix}")
        six_digit[prefix] = code
    counts = Counter()
    excluded = Counter()
    first_day = last_day = None
    for path in sorted(RAW.glob("dengue_ce_*.csv.gz")):
        with gzip.open(path, "rt", encoding="latin-1", newline="") as stream:
            for row in csv.DictReader(stream):
                try:
                    day = date.fromisoformat(row["DT_NOTIFIC"])
                except (ValueError, TypeError):
                    excluded["invalid_date"] += 1
                    continue
                first_day = min(first_day, day) if first_day else day
                last_day = max(last_day, day) if last_day else day
                raw_code = row["ID_MN_RESI"].strip()
                code = raw_code if raw_code in codes else six_digit.get(raw_code)
                if not code:
                    excluded["invalid_municipality"] += 1
                    continue
                counts[(week_start(day), code)] += 1
    if not first_day or not last_day:
        raise RuntimeError("No valid dengue notification dates")
    return counts, first_day, last_day, excluded


def write_csv(path, header, rows):
    with gzip.open(path, "wt", encoding="utf-8", newline="") if path.suffix == ".gz" else path.open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    municipalities, edges = municipalities_and_edges()
    codes = sorted(municipalities)
    counts, first_day, last_day, excluded = dengue_counts(set(codes))
    first_week = week_start(first_day)
    if first_week < first_day:
        first_week += timedelta(days=7)
    last_week = week_start(last_day)
    if last_week + timedelta(days=6) > last_day:
        last_week -= timedelta(days=7)
    weeks = []
    current = first_week
    while current <= last_week:
        weeks.append(current)
        current += timedelta(days=7)

    write_csv(
        OUT / "municipios.csv",
        ["municipio_ibge", "municipio_nome"],
        ((code, municipalities[code]["name"]) for code in codes),
    )
    # One row per undirected border; model code may add reverse edges/self-loops.
    write_csv(
        OUT / "arestas_vizinhos.csv",
        ["municipio_origem", "municipio_destino"],
        edges,
    )
    panel = OUT / "dengue_municipio_semana.csv.gz"
    write_csv(
        panel,
        ["municipio_ibge", "ano_epi", "semana_epi", "semana_inicio",
         "semana_fim", "casos_notificados"],
        (
            (
                code, year, number, start.isoformat(),
                (start + timedelta(days=6)).isoformat(),
                counts[(start, code)],
            )
            for start in weeks
            for year, number in [epi_year_week(start)]
            for code in codes
        ),
    )
    manifest = {
        "source_dengue": "data/raw/sinan_dengue_ce/manifest.json",
        "source_mesh": "data/raw/ibge/CE_Municipios_2025.zip",
        "outcome": "notificacoes de dengue por municipio de residencia e semana da notificacao",
        "municipalities": len(codes),
        "weeks": len(weeks),
        "panel_rows": len(codes) * len(weeks),
        "undirected_edges": len(edges),
        "first_complete_week_start": first_week.isoformat(),
        "last_complete_week_start": last_week.isoformat(),
        "first_notification_date": first_day.isoformat(),
        "last_notification_date": last_day.isoformat(),
        "excluded_records": dict(excluded),
        "note": "2026 ainda e parcial e sujeito a revisoes; o arquivo nao define treino/validacao/teste",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(codes)} municípios, {len(weeks)} semanas, {len(edges)} arestas, "
          f"{sum(counts.values()):,} notificações com município válido")


if __name__ == "__main__":
    main()
