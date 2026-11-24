"""Repeat the validation-selected grid winners with fixed alternative seeds."""

import argparse
import json
import statistics
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import grid_search as grid  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=grid.ROOT / "runs/grid_v1")
    parser.add_argument("--seeds", default="42,43,44,45,46")
    args = parser.parse_args()
    seeds = [int(value) for value in args.seeds.split(",")]
    torch.set_num_threads(4)
    counts, weeks, codes, adjacency, seasonal = grid.read_data()
    splits = grid.split_targets(len(weeks))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    selected = json.loads((args.output / "summary.json").read_text())["best_by_model"]
    all_targets = torch.arange(max(grid.LOOKBACKS), len(weeks))
    test_start = len(splits["train"]) + len(splits["validation"])
    results = {}
    for name, choice in selected.items():
        config = choice["config"]
        x, last, y = grid.make_windows(counts, seasonal, all_targets, config)
        x, last, y = x.to(device), last.to(device), y.to(device)
        results[name] = []
        for seed in seeds:
            grid.SEED = seed
            destination = args.output / "repeats" / f"seed_{seed}"
            record = grid.train_one(config, counts, weeks, adjacency, seasonal,
                                    splits, device, destination)
            model = grid.ForecastModel(config, len(codes)).to(device)
            model.load_state_dict(torch.load(destination / record["checkpoint"],
                                             map_location=device, weights_only=True))
            test = grid.metrics(model, x, last, y, adjacency.to(device), test_start, len(y))
            results[name].append({"seed": seed, "best_epoch": record["best_epoch"],
                                  "validation": record["validation"], "test": test})
            print(name, seed, "val_mae", round(record["validation"]["mae"], 4),
                  "test_mae", round(test["mae"], 4), flush=True)
    summary = {
        "seeds": seeds,
        "selection": "Architectures were selected once by the 360-run grid; seeds were not used for model selection.",
        "results": results,
        "mean_test_mae": {name: statistics.mean(x["test"]["mae"] for x in rows)
                          for name, rows in results.items()},
        "std_test_mae": {name: statistics.stdev(x["test"]["mae"] for x in rows)
                         for name, rows in results.items()},
    }
    (args.output / "repeats_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print("saved", args.output / "repeats_summary.json")


if __name__ == "__main__":
    main()
