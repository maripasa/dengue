"""Reproducible, resumable grid search for weekly dengue forecasts.

All models see the same municipality-week labels and chronological splits.
Inputs are raw case counts; no scaler is fitted or applied.
"""

import argparse
import csv
import gzip
import itertools
import json
import math
import random
import time
from datetime import date
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F


ROOT = Path(__file__).resolve().parent
PANEL = ROOT / "data/processed/dengue_confirmed_weekly/casos_municipio_semana.csv.gz"
MUNICIPALITIES = ROOT / "data/processed/dengue_v1/municipios.csv"
EDGES = ROOT / "data/processed/dengue_v1/arestas_vizinhos.csv"

LOOKBACKS = [4, 8, 16]
HIDDEN_SIZES = [16, 32]
LSTM_LAYERS = [1, 2]
SEASONAL = ["none", "week", "week_month"]
LEARNING_RATES = [0.001, 0.0003]
GRAPH_DEPTHS = [1, 2, 4]
MAX_EPOCHS = 20
PATIENCE = 5
BATCH_SIZE = 16
SEED = 42


def configurations() -> list[dict]:
    configs = []
    for model in ["node_lstm", "joint_lstm", "lstm_gcn"]:
        depths = GRAPH_DEPTHS if model == "lstm_gcn" else [0]
        for values in itertools.product(
            LOOKBACKS, HIDDEN_SIZES, LSTM_LAYERS, SEASONAL, LEARNING_RATES, depths
        ):
            lookback, hidden, lstm_layers, seasonal, lr, graph_depth = values
            configs.append({
                "id": len(configs), "model": model, "lookback": lookback,
                "hidden": hidden, "lstm_layers": lstm_layers, "seasonal": seasonal,
                "lr": lr, "graph_depth": graph_depth,
            })
    return configs


def read_data():
    with MUNICIPALITIES.open(newline="", encoding="utf-8") as stream:
        codes = sorted(row["municipio_ibge"] for row in csv.DictReader(stream))
    code_index = {code: i for i, code in enumerate(codes)}
    by_week = {}
    with gzip.open(PANEL, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            week, code = row["semana_inicio"], row["municipio_ibge"]
            if code in by_week.setdefault(week, {}):
                raise ValueError(f"Duplicate {code}/{week}")
            by_week[week][code] = float(row["casos_dengue"])
    weeks = sorted(by_week)
    if any(set(by_week[week]) != set(codes) for week in weeks):
        raise ValueError("Every week must contain every municipality")
    counts = torch.tensor([[by_week[week][code] for code in codes] for week in weeks])
    adjacency = torch.eye(len(codes))
    with EDGES.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            i, j = code_index[row["municipio_origem"]], code_index[row["municipio_destino"]]
            adjacency[i, j] = adjacency[j, i] = 1.0
    degree = adjacency.sum(1).rsqrt()
    adjacency = degree[:, None] * adjacency * degree[None, :]
    seasonal = []
    for week in weeks:
        day = date.fromisoformat(week)
        week_number = day.isocalendar().week
        seasonal.append([
            math.sin(2 * math.pi * (week_number - 1) / 52.18),
            math.cos(2 * math.pi * (week_number - 1) / 52.18),
            math.sin(2 * math.pi * (day.month - 1) / 12),
            math.cos(2 * math.pi * (day.month - 1) / 12),
        ])
    return counts, weeks, codes, adjacency, torch.tensor(seasonal, dtype=torch.float32)


def split_targets(number_of_weeks):
    first = max(LOOKBACKS)
    train_end = int(number_of_weeks * 0.70)
    val_end = int(number_of_weeks * 0.85)
    assert first < train_end < val_end < number_of_weeks
    return {
        "train": torch.arange(first, train_end),
        "validation": torch.arange(train_end, val_end),
        "test": torch.arange(val_end, number_of_weeks),
    }


def make_windows(counts, seasonal_features, targets, config):
    lookback = config["lookback"]
    extra = {"none": 0, "week": 2, "week_month": 4}[config["seasonal"]]
    inputs = []
    for t in targets.tolist():
        count_window = counts[t - lookback:t]
        season_window = seasonal_features[t - lookback:t, :extra]
        if config["model"] == "joint_lstm":
            inputs.append(torch.cat((count_window, season_window), dim=-1))
        else:
            by_node = count_window.T.unsqueeze(-1)
            if extra:
                season_by_node = season_window.unsqueeze(0).expand(len(counts[0]), -1, -1)
                by_node = torch.cat((by_node, season_by_node), dim=-1)
            inputs.append(by_node)
    return torch.stack(inputs), counts[targets - 1], counts[targets]


class ForecastModel(nn.Module):
    def __init__(self, config, number_of_nodes):
        super().__init__()
        self.config = config
        extra = {"none": 0, "week": 2, "week_month": 4}[config["seasonal"]]
        input_size = number_of_nodes + extra if config["model"] == "joint_lstm" else 1 + extra
        dropout = 0.1 if config["lstm_layers"] > 1 else 0.0
        self.lstm = nn.LSTM(
            input_size, config["hidden"], num_layers=config["lstm_layers"],
            batch_first=True, dropout=dropout,
        )
        if config["model"] == "lstm_gcn":
            self.graph_layers = nn.ModuleList(
                nn.Linear(config["hidden"], config["hidden"], bias=False)
                for _ in range(config["graph_depth"])
            )
        else:
            self.graph_layers = nn.ModuleList()
        output_size = number_of_nodes if config["model"] == "joint_lstm" else 1
        self.output = nn.Linear(config["hidden"], output_size)
        nn.init.zeros_(self.output.weight)
        nn.init.zeros_(self.output.bias)

    def forward(self, x, last_counts, adjacency):
        if self.config["model"] == "joint_lstm":
            _, (hidden, _) = self.lstm(x)
            correction = self.output(hidden[-1])
        else:
            batch, nodes, lookback, features = x.shape
            _, (hidden, _) = self.lstm(x.reshape(batch * nodes, lookback, features))
            hidden = hidden[-1].reshape(batch, nodes, -1)
            for layer in self.graph_layers:
                hidden = F.relu(torch.matmul(adjacency, layer(hidden)) + hidden)
            correction = self.output(hidden).squeeze(-1)
        return last_counts + correction


@torch.no_grad()
def metrics(model, x, last, y, adjacency, start, stop):
    model.eval()
    abs_sum = sq_sum = nonzero_sum = high_sum = 0.0
    n = nonzero_n = high_n = 0
    for offset in range(start, stop, BATCH_SIZE):
        sl = slice(offset, min(offset + BATCH_SIZE, stop))
        prediction = model(x[sl], last[sl], adjacency).clamp_min(0)
        error = (prediction - y[sl]).abs()
        abs_sum += error.sum().item()
        sq_sum += error.square().sum().item()
        n += error.numel()
        nonzero = y[sl] > 0
        high = y[sl] >= 10
        nonzero_sum += error[nonzero].sum().item()
        high_sum += error[high].sum().item()
        nonzero_n += nonzero.sum().item()
        high_n += high.sum().item()
    return {
        "mae": abs_sum / n,
        "rmse": math.sqrt(sq_sum / n),
        "mae_nonzero": nonzero_sum / nonzero_n if nonzero_n else None,
        "mae_ge10": high_sum / high_n if high_n else None,
        "nonzero_items": nonzero_n,
        "ge10_items": high_n,
    }


def train_one(config, counts, weeks, adjacency, seasonal_features, splits, device, output_dir):
    random.seed(SEED)
    torch.manual_seed(SEED)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(SEED)
    all_targets = torch.arange(max(LOOKBACKS), len(weeks))
    x, last, y = make_windows(counts, seasonal_features, all_targets, config)
    x, last, y = x.to(device), last.to(device), y.to(device)
    adj = adjacency.to(device)
    train_stop = len(splits["train"])
    val_stop = train_stop + len(splits["validation"])
    model = ForecastModel(config, len(counts[0])).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["lr"], weight_decay=1e-4)
    criterion = nn.SmoothL1Loss(beta=10.0)
    checkpoint = output_dir / "checkpoints" / f"{config['id']:03d}.pt"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    best = metrics(model, x, last, y, adj, train_stop, val_stop)
    best_epoch = 0
    torch.save(model.state_dict(), checkpoint)
    stale = 0
    start_time = time.monotonic()
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        order = torch.randperm(train_stop, device=device)
        for offset in range(0, train_stop, BATCH_SIZE):
            indices = order[offset:offset + BATCH_SIZE]
            optimizer.zero_grad(set_to_none=True)
            prediction = model(x[indices], last[indices], adj)
            loss = criterion(prediction, y[indices])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        current = metrics(model, x, last, y, adj, train_stop, val_stop)
        if current["mae"] < best["mae"] - 1e-6:
            best, best_epoch, stale = current, epoch, 0
            torch.save(model.state_dict(), checkpoint)
        else:
            stale += 1
            if stale >= PATIENCE:
                break
    return {
        **config,
        "best_epoch": best_epoch,
        "epochs_ran": epoch,
        "validation": best,
        "seconds": round(time.monotonic() - start_time, 2),
        "checkpoint": str(checkpoint.relative_to(output_dir)),
        "status": "ok",
    }


def finalize(configs, counts, weeks, adjacency, seasonal_features, splits, device, output_dir):
    results = {}
    for path in sorted(output_dir.glob("results_shard*.jsonl")):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            results[record["id"]] = record
    if len(results) != len(configs) or any(r.get("status") != "ok" for r in results.values()):
        raise ValueError(f"Need {len(configs)} successful configs; have {len(results)} results")
    with (output_dir / "leaderboard.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["rank", "id", "model", "lookback", "hidden", "lstm_layers",
                         "seasonal", "lr", "graph_depth", "best_epoch", "val_mae",
                         "val_rmse", "val_mae_nonzero", "val_mae_ge10", "seconds"])
        for rank, record in enumerate(sorted(results.values(), key=lambda r: r["validation"]["mae"]), 1):
            writer.writerow([rank, record["id"], record["model"], record["lookback"],
                             record["hidden"], record["lstm_layers"], record["seasonal"],
                             record["lr"], record["graph_depth"], record["best_epoch"],
                             record["validation"]["mae"], record["validation"]["rmse"],
                             record["validation"]["mae_nonzero"], record["validation"]["mae_ge10"],
                             record["seconds"]])
    best_by_model = {}
    test_config = {"model": "node_lstm", "lookback": 4, "hidden": 16,
                   "lstm_layers": 1, "seasonal": "none", "lr": 0.001, "graph_depth": 0}
    all_targets = torch.arange(max(LOOKBACKS), len(weeks))
    x, last, y = make_windows(counts, seasonal_features, all_targets, test_config)
    baseline = {
        name: metrics(ForecastModel(test_config, len(counts[0])).to(device),
                      x.to(device), last.to(device), y.to(device), adjacency.to(device),
                      0 if name == "train" else len(splits["train"]) if name == "validation" else len(splits["train"]) + len(splits["validation"]),
                      len(splits["train"]) if name == "train" else len(splits["train"]) + len(splits["validation"]) if name == "validation" else len(y))
        for name in ["train", "validation", "test"]
    }
    for name in ["node_lstm", "joint_lstm", "lstm_gcn"]:
        record = min((r for r in results.values() if r["model"] == name),
                     key=lambda r: r["validation"]["mae"])
        config = {k: record[k] for k in ["id", "model", "lookback", "hidden", "lstm_layers", "seasonal", "lr", "graph_depth"]}
        x, last, y = make_windows(counts, seasonal_features, all_targets, config)
        x, last, y = x.to(device), last.to(device), y.to(device)
        model = ForecastModel(config, len(counts[0])).to(device)
        checkpoint = output_dir / record["checkpoint"]
        model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True))
        test_start = len(splits["train"]) + len(splits["validation"])
        best_by_model[name] = {
            "config": config,
            "best_epoch": record["best_epoch"],
            "validation": record["validation"],
            "test": metrics(model, x, last, y, adjacency.to(device), test_start, len(y)),
            "checkpoint": str(checkpoint.relative_to(output_dir)),
        }
    summary = {
        "configurations": len(configs),
        "grid": {"lookbacks": LOOKBACKS, "hidden_sizes": HIDDEN_SIZES,
                 "lstm_layers": LSTM_LAYERS, "seasonal": SEASONAL,
                 "learning_rates": LEARNING_RATES, "graph_depths": GRAPH_DEPTHS,
                 "max_epochs": MAX_EPOCHS, "patience": PATIENCE, "batch_size": BATCH_SIZE},
        "split_weeks": {name: [weeks[indices[0]], weeks[indices[-1]]] for name, indices in splits.items()},
        "baseline": baseline,
        "best_by_model": best_by_model,
        "selection": "Lowest validation MAE within each model family; test evaluated after selection.",
        "input": "Raw weekly case counts; optional sine/cosine week and month features; no scaling.",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/grid_v1")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--ids", help="Comma-separated configuration IDs for a timing probe")
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    configs = configurations()
    if args.dry_run:
        print(json.dumps({"total": len(configs), "by_model": {
            name: sum(c["model"] == name for c in configs)
            for name in ["node_lstm", "joint_lstm", "lstm_gcn"]},
            "grid": {"lookbacks": LOOKBACKS, "hidden_sizes": HIDDEN_SIZES,
                     "lstm_layers": LSTM_LAYERS, "seasonal": SEASONAL,
                     "learning_rates": LEARNING_RATES, "graph_depths": GRAPH_DEPTHS}}, indent=2))
        return
    if args.shards < 1 or not 0 <= args.shard_index < args.shards:
        parser.error("Invalid shard index/count")
    torch.set_num_threads(4)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    counts, weeks, codes, adjacency, seasonal_features = read_data()
    splits = split_targets(len(weeks))
    args.output.mkdir(parents=True, exist_ok=True)
    if args.finalize:
        finalize(configs, counts, weeks, adjacency, seasonal_features, splits, device, args.output)
        return
    chosen = [c for c in configs if c["id"] % args.shards == args.shard_index]
    if args.ids:
        wanted = {int(x) for x in args.ids.split(",")}
        chosen = [c for c in chosen if c["id"] in wanted]
    result_path = args.output / f"results_shard{args.shard_index}.jsonl"
    completed = set()
    if result_path.exists():
        for line in result_path.read_text().splitlines():
            record = json.loads(line)
            if record.get("status") == "ok":
                completed.add(record["id"])
    remaining = [c for c in chosen if c["id"] not in completed]
    print(f"device={device} configs={len(chosen)} remaining={len(remaining)}", flush=True)
    total_seconds = 0.0
    for completed_now, config in enumerate(remaining, 1):
        try:
            record = train_one(config, counts, weeks, adjacency, seasonal_features,
                               splits, device, args.output)
            total_seconds += record["seconds"]
        except Exception as exc:
            record = {**config, "status": "error", "error": repr(exc)}
        with result_path.open("a") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        eta = (total_seconds / completed_now) * (len(remaining) - completed_now)
        print(f"{completed_now}/{len(remaining)} id={config['id']} model={config['model']} "
              f"lookback={config['lookback']} depth={config['graph_depth']} "
              f"val_mae={record.get('validation', {}).get('mae', 'error')} "
              f"seconds={record.get('seconds', 'NA')} eta_min={eta/60:.1f}", flush=True)


if __name__ == "__main__":
    main()
