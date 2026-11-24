import csv
import itertools
import json
from pathlib import Path

import torch

from .config import (
    BATCH_SIZE, FIRST_TARGET, GCN_LAYERS, HIDDEN_SIZES, LEARNING_RATES,
    LOOKBACKS, LSTM_LAYERS, MAX_EPOCHS, PATIENCE, SEASONAL_FEATURES, Experiment,
)
from .data import load_weekly_data, make_examples, split_examples
from .training import evaluate, fit, test_checkpoint


def configurations():
    combinations = itertools.product(
        LOOKBACKS, HIDDEN_SIZES, LSTM_LAYERS, SEASONAL_FEATURES,
        LEARNING_RATES, GCN_LAYERS,
    )
    return [Experiment(index, *values) for index, values in enumerate(combinations)]


def save_leaderboard(results, output):
    with (output / "leaderboard.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "rank", "id", "lookback", "hidden", "lstm_layers", "seasonal",
            "learning_rate", "gcn_layers", "best_epoch", "validation_mae",
            "validation_rmse", "validation_mae_ge10", "seconds",
        ])
        for rank, result in enumerate(sorted(results, key=lambda row: row["validation"]["mae"]), 1):
            config = result["config"]
            validation = result["validation"]
            writer.writerow([
                rank, config["id"], config["lookback"], config["hidden"],
                config["lstm_layers"], config["seasonal"], config["learning_rate"],
                config["gcn_layers"], result["best_epoch"], validation["mae"],
                validation["rmse"], validation["mae_ge10"], result["seconds"],
            ])


def run_grid(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data = load_weekly_data()
    spans = split_examples(data)
    configs = configurations()
    records = output / "results.jsonl"
    completed = {}
    if records.exists():
        for line in records.read_text().splitlines():
            result = json.loads(line)
            completed[result["config"]["id"]] = result
    remaining = [config for config in configs if config.id not in completed]
    print(f"device={device} completed={len(completed)} remaining={len(remaining)}", flush=True)
    elapsed = 0.0
    for number, config in enumerate(remaining, 1):
        result = fit(config, data, spans, device, output)
        with records.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
        completed[config.id] = result
        elapsed += result["seconds"]
        eta_minutes = elapsed / number * (len(remaining) - number) / 60
        print(
            f"{len(completed)}/{len(configs)} lookback={config.lookback} "
            f"hidden={config.hidden} gcn_layers={config.gcn_layers} "
            f"validation_mae={result['validation']['mae']:.4f} "
            f"eta_min={eta_minutes:.1f}", flush=True,
        )
    if len(completed) != len(configs):
        raise ValueError("Grid search is incomplete")

    results = list(completed.values())
    save_leaderboard(results, output)
    best = min(results, key=lambda row: row["validation"]["mae"])
    selected = Experiment(**best["config"])
    test = test_checkpoint(selected, output / best["checkpoint"], data, spans, device)
    examples = make_examples(data, selected.lookback, selected.seasonal).to(device)
    adjacency = data.adjacency.to(device)
    baseline = {
        name: evaluate(None, examples, adjacency, spans[name])
        for name in ["validation", "test"]
    }
    first_target = FIRST_TARGET
    summary = {
        "configurations": len(configs),
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "weeks": len(data.weeks),
        "municipalities": len(data.municipalities),
        "split_weeks": {
            name: [data.weeks[first_target + span.start], data.weeks[first_target + span.stop - 1]]
            for name, span in spans.items()
        },
        "grid": {
            "lookbacks": LOOKBACKS,
            "hidden_sizes": HIDDEN_SIZES,
            "lstm_layers": LSTM_LAYERS,
            "seasonal_features": SEASONAL_FEATURES,
            "learning_rates": LEARNING_RATES,
            "gcn_layers": GCN_LAYERS,
            "max_epochs": MAX_EPOCHS,
            "patience": PATIENCE,
            "batch_size": BATCH_SIZE,
        },
        "best": {**best, "test": test},
        "persistence": baseline,
        "total_gpu_seconds": round(sum(result["seconds"] for result in results), 2),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
