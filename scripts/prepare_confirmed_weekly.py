import csv
import gzip
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/sinan_dengue_ce"
MUNICIPALITIES = ROOT / "data/processed/dengue_v1/municipios.csv"
OUT = ROOT / "data/processed/dengue_confirmed_weekly"


def sunday(day: date) -> date:
    return day - timedelta(days=(day.weekday() + 1) % 7)


def main() -> None:
    with MUNICIPALITIES.open(newline="", encoding="utf-8") as stream:
        codes = sorted(row["municipio_ibge"] for row in csv.DictReader(stream))
    if len(codes) != 184 or len(set(codes)) != 184:
        raise ValueError("Expected 184 unique Ceará municipality codes")
    code_set = set(codes)
    six_to_seven = {code[:6]: code for code in codes}
    if len(six_to_seven) != len(codes):
        raise ValueError("Ambiguous six-digit municipality codes")

    counts: Counter[tuple[date, str]] = Counter()
    audit: Counter[str] = Counter()
    latest_date: date | None = None
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

    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / "casos_municipio_semana.csv.gz"
    with gzip.open(destination, "wt", newline="", encoding="utf-8") as stream:
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
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
