import argparse
import json
from pathlib import Path

from dengue_gcn.grid import configurations, run_grid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("runs/gcn_grid_v1"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({"configurations": len(configurations())}, indent=2))
        return
    run_grid(args.output)


if __name__ == "__main__":
    main()
