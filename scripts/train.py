"""SFT the student model on pairs streamed from Neon.

Filter knobs default to the current prompt_version so cross-revision pairs don't
contaminate the training set. Override `--prompt-version` to mix or pin.
"""
from __future__ import annotations

import argparse

from melilo.train.sft import TrainConfig, run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="checkpoints/melilo-v0")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument(
        "--prompt-version",
        default=None,
        help="Filter pairs by this prompt_version. Defaults to settings.prompt_version.",
    )
    parser.add_argument("--task-type", default=None)
    parser.add_argument("--source-type", default=None)
    parser.add_argument(
        "--reviewed-only",
        action="store_true",
        help="Train only on pairs flagged human_reviewed = TRUE.",
    )
    args = parser.parse_args()

    run(
        TrainConfig(
            output_dir=args.output_dir,
            epochs=args.epochs,
            prompt_version=args.prompt_version,
            task_type=args.task_type,
            source_type=args.source_type,
            human_reviewed_only=args.reviewed_only,
        )
    )


if __name__ == "__main__":
    main()
