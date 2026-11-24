import csv
import gzip
import io
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "sinan_dengue_ce"
DATASET_URL = "https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue"


def resources():
    with urlopen(DATASET_URL, timeout=60) as response:
        html = response.read().decode("utf-8")
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not match:
        raise RuntimeError("Could not find dataset metadata")
    data = json.loads(match.group(1))
    items = []
    for resource in data["props"]["pageProps"]["resources"]:
        if resource.get("format") != "CSV":
            continue
        year_match = re.fullmatch(r"Dengue - (20\d{2})", resource["name"])
        if year_match:
            items.append((int(year_match.group(1)), resource["url"], resource["last_modified"]))
    return sorted(items)


def process(year, url, last_modified):
    target = OUT / f"dengue_ce_{year}.csv.gz"
    with tempfile.NamedTemporaryFile(dir=OUT, suffix=".csv.gz", delete=False) as pending:
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
                    count = 0
                    by_state = 0
                    by_municipality = 0
                    missing_municipality = 0
                    with gzip.open(pending_path, "wt", encoding="latin-1", newline="") as dest:
                        writer = csv.writer(dest)
                        writer.writerow(header)
                        for row in reader:
                            uf = row[uf_index].strip().upper()
                            municipality = row[municipality_index].strip()
                            state_match = uf in {"CE", "23"}
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": []}
    previous_by_year = {item["year"]: item for item in previous["files"]}
    result = {
        "dataset_url": DATASET_URL,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": [],
    }
    for year, url, last_modified in resources():
        old = previous_by_year.get(year)
        target = OUT / f"dengue_ce_{year}.csv.gz"
        if (old and target.exists() and old["url"] == url
                and old["source_last_modified"] == last_modified
                and old["ce_gzip_bytes"] == target.stat().st_size):
            item = old
            print(f"{year}: sem alterações", flush=True)
        else:
            item = process(year, url, last_modified)
            print(f"{year}: {item['ce_records']:,} registros do CE, {item['ce_gzip_bytes'] / 1024**2:.1f} MiB", flush=True)
        result["files"].append(item)
        manifest_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
