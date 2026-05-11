"""SFT the student model on a pairs JSONL file (local path)."""
from __future__ import annotations

import argparse

from melilo.train.sft import TrainConfig, run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", required=True, help="Local path to pairs JSONL")
    parser.add_argument("--output-dir", default="checkpoints/melilo-v0")
    parser.add_argument("--epochs", type=int, default=1)
    args = parser.parse_args()

    run(TrainConfig(pairs_path=args.pairs, output_dir=args.output_dir, epochs=args.epochs))


if __name__ == "__main__":
    main()
