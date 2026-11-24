import csv
import io
from pathlib import Path
from zipfile import ZipFile

import shapefile
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parents[1]
MESH = ROOT / "data/raw/ibge/CE_Municipios_2025.zip"
OUTPUT = ROOT / "data/processed/dengue_v1"


def municipalities():
    with ZipFile(MESH) as archive:
        names = archive.namelist()

        def member(suffix):
            return io.BytesIO(archive.read(next(name for name in names if name.endswith(suffix))))

        reader = shapefile.Reader(shp=member(".shp"), shx=member(".shx"), dbf=member(".dbf"))
        fields = [field[0] for field in reader.fields[1:]]
        result = {}
        for feature in reader.iterShapeRecords():
            attributes = dict(zip(fields, feature.record))
            result[attributes["CD_MUN"]] = (
                attributes["NM_MUN"], shape(feature.shape.__geo_interface__)
            )
    if len(result) != 184:
        raise ValueError("Expected 184 municipalities in the Ceará mesh")
    return result


def main():
    nodes = municipalities()
    codes = sorted(nodes)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "municipios.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["municipio_ibge", "municipio_nome"])
        writer.writerows((code, nodes[code][0]) for code in codes)
    with (OUTPUT / "arestas_vizinhos.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["municipio_origem", "municipio_destino"])
        for index, source in enumerate(codes):
            for target in codes[index + 1:]:
                shared = nodes[source][1].boundary.intersection(nodes[target][1].boundary)
                if shared.length > 0:
                    writer.writerow([source, target])
    print(f"{len(codes)} municipalities")


if __name__ == "__main__":
    main()
