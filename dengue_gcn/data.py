import csv
import gzip
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import torch

from .config import FIRST_TARGET


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class WeeklyData:
    counts: torch.Tensor
    calendar: torch.Tensor
    adjacency: torch.Tensor
    weeks: list[str]
    municipalities: list[str]


@dataclass
class Examples:
    x: torch.Tensor
    last: torch.Tensor
    target: torch.Tensor

    def to(self, device):
        return Examples(self.x.to(device), self.last.to(device), self.target.to(device))


def load_weekly_data():
    with (ROOT / "data/processed/dengue_v1/municipios.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        municipalities = sorted(row["municipio_ibge"] for row in csv.DictReader(stream))
    if len(municipalities) != 184 or len(set(municipalities)) != 184:
        raise ValueError("Expected 184 unique municipalities")
    municipality_index = {code: index for index, code in enumerate(municipalities)}

    records = {}
    path = ROOT / "data/processed/dengue_confirmed_weekly/casos_municipio_semana.csv.gz"
    with gzip.open(path, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            week = row["semana_inicio"]
            code = row["municipio_ibge"]
            if code in records.setdefault(week, {}):
                raise ValueError(f"Duplicate municipality and week: {code}, {week}")
            records[week][code] = float(row["casos_dengue"])
    weeks = sorted(records)
    if any(set(records[week]) != set(municipalities) for week in weeks):
        raise ValueError("Every week must contain all municipalities")
    counts = torch.tensor([[records[week][code] for code in municipalities] for week in weeks])

    adjacency = torch.eye(len(municipalities))
    with (ROOT / "data/processed/dengue_v1/arestas_vizinhos.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        for row in csv.DictReader(stream):
            source = municipality_index[row["municipio_origem"]]
            target = municipality_index[row["municipio_destino"]]
            adjacency[source, target] = adjacency[target, source] = 1.0
    degree = adjacency.sum(dim=1).rsqrt()
    adjacency = degree[:, None] * adjacency * degree[None, :]

    calendar = []
    for week in weeks:
        day = date.fromisoformat(week)
        week_number = day.isocalendar().week
        calendar.append([
            math.sin(2 * math.pi * (week_number - 1) / 52.18),
            math.cos(2 * math.pi * (week_number - 1) / 52.18),
            math.sin(2 * math.pi * (day.month - 1) / 12),
            math.cos(2 * math.pi * (day.month - 1) / 12),
        ])
    return WeeklyData(
        counts, torch.tensor(calendar, dtype=torch.float32), adjacency,
        weeks, municipalities,
    )


def split_examples(data):
    train_end = int(len(data.weeks) * 0.70)
    validation_end = int(len(data.weeks) * 0.85)
    if not FIRST_TARGET < train_end < validation_end < len(data.weeks):
        raise ValueError("Not enough weeks for chronological splits")
    return {
        "train": slice(0, train_end - FIRST_TARGET),
        "validation": slice(train_end - FIRST_TARGET, validation_end - FIRST_TARGET),
        "test": slice(validation_end - FIRST_TARGET, len(data.weeks) - FIRST_TARGET),
    }


def make_examples(data, lookback, seasonal):
    number_of_calendar_features = {"none": 0, "week": 2, "week_month": 4}[seasonal]
    inputs = []
    for target_week in range(FIRST_TARGET, len(data.weeks)):
        count_window = data.counts[target_week - lookback:target_week].T.unsqueeze(-1)
        if number_of_calendar_features:
            calendar_window = data.calendar[
                target_week - lookback:target_week, :number_of_calendar_features
            ].unsqueeze(0).expand(len(data.municipalities), -1, -1)
            count_window = torch.cat((count_window, calendar_window), dim=-1)
        inputs.append(count_window)
    return Examples(
        torch.stack(inputs), data.counts[FIRST_TARGET - 1:-1],
        data.counts[FIRST_TARGET:],
    )
