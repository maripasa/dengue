"""One-week-ahead LSTM -> GCN baseline on raw weekly dengue counts.

No input or target scaling is applied. Runs on CUDA when available.
"""

import argparse
import csv
import gzip
import json
import random
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F


ROOT = Path(__file__).resolve().parent
PANEL = ROOT / "data/processed/dengue_confirmed_weekly/casos_municipio_semana.csv.gz"
MUNICIPALITIES = ROOT / "data/processed/dengue_v1/municipios.csv"
EDGES = ROOT / "data/processed/dengue_v1/arestas_vizinhos.csv"


def load_data() -> tuple[torch.Tensor, list[str], list[str], torch.Tensor]:
    with MUNICIPALITIES.open(newline="", encoding="utf-8") as stream:
        codes = sorted(row["municipio_ibge"] for row in csv.DictReader(stream))
    code_to_index = {code: i for i, code in enumerate(codes)}
    by_week: dict[str, dict[str, float]] = {}
    with gzip.open(PANEL, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            week = row["semana_inicio"]
            code = row["municipio_ibge"]
            if code in by_week.setdefault(week, {}):
                raise ValueError(f"Duplicate municipality/week: {code}/{week}")
            by_week[week][code] = float(row["casos_dengue"])
    weeks = sorted(by_week)
    if any(set(by_week[week]) != set(codes) for week in weeks):
        raise ValueError("Panel must contain all municipalities in every week")
    counts = torch.tensor([[by_week[week][code] for code in codes] for week in weeks])

    adjacency = torch.eye(len(codes))
    with EDGES.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            i = code_to_index[row["municipio_origem"]]
            j = code_to_index[row["municipio_destino"]]
            adjacency[i, j] = adjacency[j, i] = 1.0
    degree = adjacency.sum(dim=1).rsqrt()
    adjacency = degree[:, None] * adjacency * degree[None, :]
    return counts, weeks, codes, adjacency


class LSTMGCN(nn.Module):
    def __init__(self, hidden: int = 32):
        super().__init__()
        self.lstm = nn.LSTM(1, hidden, batch_first=True)
        self.graph = nn.Linear(hidden, hidden, bias=False)
        self.output = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor, adjacency: torch.Tensor) -> torch.Tensor:
        batch, nodes, lookback = x.shape
        _, (hidden, _) = self.lstm(x.reshape(batch * nodes, lookback, 1))
        hidden = hidden[-1].reshape(batch, nodes, -1)
        hidden = F.relu(torch.matmul(adjacency, self.graph(hidden)))
        correction = self.output(hidden).squeeze(-1)
        return F.softplus(x[:, :, -1] + correction)


@torch.no_grad()
def evaluate(model, x, y, adjacency, indices, device, batch_size):
    model.eval()
    absolute = squared = baseline_absolute = 0.0
    items = 0
    for start in range(0, len(indices), batch_size):
        batch_indices = indices[start:start + batch_size]
        xb = x[batch_indices].to(device)
        yb = y[batch_indices].to(device)
        prediction = model(xb, adjacency)
        error = prediction - yb
        absolute += error.abs().sum().item()
        squared += error.square().sum().item()
        baseline_absolute += (xb[:, :, -1] - yb).abs().sum().item()
        items += yb.numel()
    return {
        "mae": absolute / items,
        "rmse": (squared / items) ** 0.5,
        "persistence_mae": baseline_absolute / items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookback", type=int, default=8)
    parser.add_argument("--hidden", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/lstm_gcn_v1")
    args = parser.parse_args()
    if min(args.lookback, args.hidden, args.epochs, args.patience, args.batch_size) < 1:
        parser.error("All numeric options must be positive")

    random.seed(42)
    torch.manual_seed(42)
    counts, weeks, codes, adjacency = load_data()
    if len(weeks) <= args.lookback + 10:
        raise ValueError("Not enough weeks for the requested lookback")
    x = torch.stack([counts[t - args.lookback:t].T for t in range(args.lookback, len(weeks))])
    y = counts[args.lookback:]
    target_weeks = weeks[args.lookback:]
    train_end = int(len(y) * 0.70)
    validation_end = int(len(y) * 0.85)
    if min(train_end, validation_end - train_end, len(y) - validation_end) < 1:
        raise ValueError("Empty chronological split")
    splits = {
        "train": list(range(0, train_end)),
        "validation": list(range(train_end, validation_end)),
        "test": list(range(validation_end, len(y))),
    }
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    adjacency = adjacency.to(device)
    model = LSTMGCN(args.hidden).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)
    criterion = nn.SmoothL1Loss(beta=10.0)
    args.out.mkdir(parents=True, exist_ok=True)
    best_validation = float("inf")
    best_epoch = 0
    stale = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = torch.randperm(len(splits["train"]))
        total_loss = batches = 0
        for start in range(0, len(order), args.batch_size):
            indices = order[start:start + args.batch_size]
            xb = x[indices].to(device)
            yb = y[indices].to(device)
            optimizer.zero_grad(set_to_none=True)
            prediction = model(xb, adjacency)
            loss = criterion(prediction, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
            batches += 1
        validation = evaluate(model, x, y, adjacency, splits["validation"], device, args.batch_size)
        print(f"epoch={epoch:02d} train_loss={total_loss/batches:.4f} "
              f"val_mae={validation['mae']:.4f} persistence_mae={validation['persistence_mae']:.4f}", flush=True)
        if validation["mae"] < best_validation:
            best_validation = validation["mae"]
            best_epoch = epoch
            stale = 0
            torch.save(model.state_dict(), args.out / "best.pt")
        else:
            stale += 1
            if stale >= args.patience:
                break

    model.load_state_dict(torch.load(args.out / "best.pt", map_location=device, weights_only=True))
    metrics = {
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "torch_version": torch.__version__,
        "municipalities": len(codes),
        "weeks": len(weeks),
        "lookback": args.lookback,
        "best_epoch": best_epoch,
        "split_weeks": {name: [target_weeks[v[0]], target_weeks[v[-1]]] for name, v in splits.items()},
        "validation": evaluate(model, x, y, adjacency, splits["validation"], device, args.batch_size),
        "test": evaluate(model, x, y, adjacency, splits["test"], device, args.batch_size),
        "note": "Retrospective next-week prediction; raw counts, no scaling. MAE/RMSE are cases per municipality-week.",
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(metrics, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
